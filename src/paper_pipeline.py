"""
论文库完整流水线：清洗 → 抽取 → 分类 → 入库 → 卡片 → 验证引用真实性 → 向量化
"""

from __future__ import annotations

import json
import hashlib
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from md_cleaner import clean_all_md_files, KB_ROOT, KB_CLEANED_ROOT
from paper_extractor import extract_paper, DIRECTION_LABELS
from paper_store import (
    init_paper_db, upsert_paper, upsert_citation_card, get_paper_stats,
)
from vector_store import LocalVectorStore

from anthropic import Anthropic
from llm_config import load_llm_config

# Prompt for citation verification gating
_VERIFY_PROMPT = """你是一位学术文献审核专家。你的任务是在互联网知识范围内，验证一条参考文献引用的真实性。

请判断作者、标题、期刊/会议/出版社的组合是否指向一篇真实的学术文献。格式小问题（缺少空格、DOI格式异常等）不代表文献不存在——请区分「文献虚构」和「文献真实但格式不规范」。

回复严格 JSON，不要包含其他文字：
- 文献真实可确认：{"status": "verified"}
- 文献真实但格式有问题：{"status": "format_error", "note": "格式问题（20字内）"}
- 明确无法查到或虚构：{"status": "fake", "note": "原因（20字内）"}"""

_VERIFY_CONCURRENCY = 20

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_full_pipeline(
    task_id: str = "",
    progress_callback=None,
    force_reindex: bool = False,
) -> Dict[str, Any]:
    """执行完整流水线。"""
    started = time.time()
    logs: List[str] = []

    def log(msg: str) -> None:
        logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if progress_callback:
            progress_callback(msg)

    # === Phase 1: 清洗 ===
    log("Phase 1/5: MD 数据清洗...")
    cleaned = clean_all_md_files()
    log(f"  清洗完成：{cleaned} 个文件")
    yield {"phase": "clean", "count": cleaned}

    # === Phase 2: 结构化抽取 ===
    log("Phase 2/5: 结构化抽取...")
    src_dir = KB_CLEANED_ROOT if KB_CLEANED_ROOT.exists() else KB_ROOT / "converted"
    md_files = list(src_dir.rglob("*.md"))
    log(f"  发现 {len(md_files)} 个 MD 文件")

    init_paper_db()
    papers: List[Dict[str, Any]] = []
    for i, path in enumerate(md_files):
        paper = extract_paper(path)
        if paper:
            upsert_paper(paper)
            papers.append(paper)
        if (i + 1) % 30 == 0:
            log(f"  已提取 {i + 1}/{len(md_files)}：{len(papers)} 篇通过质量检查")

    log(f"  结构化抽取完成：{len(papers)} 篇论文入库")
    yield {"phase": "extract", "papers": len(papers)}

    # === Phase 3: 生成引用卡片 ===
    log("Phase 3/5: 生成引用卡片...")
    all_cards: List[Dict[str, Any]] = []
    for paper in papers:
        refs = paper.get("references_raw", [])
        paper_card_count = 0
        for ref in refs:
            if paper_card_count >= _MAX_CARDS_PER_SOURCE:
                break
            card = _build_citation_card(paper, ref)
            if card:
                all_cards.append(card)
                paper_card_count += 1
    log(f"  构建了 {len(all_cards)} 张候选卡片")

    # === Phase 3.5: 引用真实性验证（新论文必须过这一关） ===
    verified_cards = _verify_citation_batch(all_cards, log)

    # Upsert only verified/passed cards
    for card in verified_cards:
        upsert_citation_card(card)

    log(f"  引用卡片入库完成：{len(verified_cards)} 张")
    yield {"phase": "cards", "cards": len(verified_cards)}

    # === Phase 4: 向量化索引 ===
    if force_reindex:
        log("Phase 4/5: 重新向量化索引...")
        _rebuild_vector_index(papers, log)
        log("  向量索引重建完成")
    else:
        log("Phase 4/5: 向量索引已存在，跳过重建")
    yield {"phase": "vectorize"}

    # === Phase 5: 统计 ===
    stats = get_paper_stats()
    elapsed = time.time() - started
    log(f"Phase 5/5: 流水线完成，总耗时 {elapsed:.1f}s")
    log(f"  论文: {stats['papers']} 篇，卡片: {stats['cards']} 张")
    yield {"phase": "done", "stats": stats, "logs": logs, "elapsed": elapsed}


def _is_foundational_book(formatted: str, ref_type: str) -> bool:
    """识别经典/基础性参考著作（专著、标准、指南等）。"""
    if ref_type not in ("图书", "M", "专著", "标准"):
        return False
    patterns = [
        r"PMBOK|PRINCE2|CMMI|ISO\s*\d+|IEC\s*\d+",
        r"朱兰|戴明|Deming|Juran|Crosby|克劳士比|休哈特|Shewhart",
        r"知识体系|知识指南|手册|标准|规范|指南|蓝皮书|白皮书",
        r"GB/T|GB\s|国家标准|行业标准",
    ]
    return any(re.search(p, formatted, re.IGNORECASE) for p in patterns)


def _compute_card_quality(
    formatted: str, ref_type: str, paper_methods: List[str]
) -> float:
    """基于引用卡片自身属性计算质量分 (0-1)，不盲从来源论文分数。"""
    score = 0.0
    is_book = ref_type in ("图书", "M", "专著")
    is_foundational = _is_foundational_book(formatted, ref_type)

    # 1. 文献类型 (0-0.25)
    type_scores = {
        "期刊文章": 0.25, "J": 0.25, "期刊": 0.25,
        "会议论文": 0.22, "C": 0.22,
        "图书": 0.23, "M": 0.23, "专著": 0.23,
        "学位论文": 0.20, "D": 0.20,
        "标准": 0.20,
        "报告": 0.12, "R": 0.12,
        "专利": 0.10,
        "其他": 0.08,
    }
    score += type_scores.get(ref_type, 0.08)

    # 2. 完整性 (0-0.30)
    comp = 0.0
    if re.search(r"[一-鿿]{2,4}|[A-Z][a-z]+,\s*[A-Z]\.", formatted):
        comp += 0.06
    if len(formatted.strip()) > 30:
        comp += 0.04
    if re.search(r"(19|20)\d{2}", formatted):
        comp += 0.06
    if re.search(r"\[[JMDCS]\]|出版社|大学|学报|期刊|Press|Springer|IEEE", formatted):
        comp += 0.08
    if re.search(r"DOI|doi\.org|https?://", formatted):
        comp += 0.06
    score += min(0.30, comp)

    # 3. 经典著作加成 (0-0.08)
    if is_foundational:
        score += 0.08

    # 4. 方法相关性 (0-0.20)
    if paper_methods:
        haystack = formatted.lower()
        hits = sum(1 for m in paper_methods if m.lower() in haystack)
        score += min(0.20, hits * 0.06)

    # 5. 长度适中 (0-0.10)
    length = len(formatted.strip())
    if 50 <= length <= 500:
        score += 0.10
    elif 30 <= length <= 600:
        score += 0.05

    # 6. 时效性 (0-0.10) — 经典著作不因年份而受罚
    ym = re.search(r"((?:19|20)\d{2})", formatted)
    if ym:
        year_val = int(ym.group(1))
        if year_val >= 2023:
            score += 0.10
        elif year_val >= 2020:
            score += 0.08
        elif year_val >= 2015:
            score += 0.05
        elif year_val >= 2000:
            score += 0.03
        if is_foundational and year_val < 2020:
            # 经典著作时效性地板：至少 +0.05
            score += max(0, 0.05 - (0.08 if year_val >= 2020 else 0.05 if year_val >= 2015 else 0.03 if year_val >= 2000 else 0))

    # 7. 无噪声信号 (0-0.05)
    noise = 0.0
    if re.search(r"_{5,}", formatted):
        noise -= 0.05
    if re.search(r"(经验年限|重要程度比较)", formatted):
        noise -= 0.05
    score += noise

    return round(max(0.05, min(1.0, score)), 2)


_MAX_CARDS_PER_SOURCE = 80


def _verify_citation_batch(cards: List[Dict[str, Any]], log) -> List[Dict[str, Any]]:
    """批量调用 LLM 验证引用真实性。返回通过验证的卡片（fake 被过滤）。"""
    config = load_llm_config()
    if not config.api_key:
        log("  WARNING: No API key, skipping citation verification")
        return cards

    client = Anthropic(api_key=config.api_key, base_url=config.base_url, timeout=60)
    model = config.model
    log(f"  正在验证 {len(cards)} 条引用真实性 ({model}, {_VERIFY_CONCURRENCY}并发)...")

    def _verify_one(card: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Returns card with verified set, or None if fake."""
        formatted = card.get("formatted", "")
        authors = card.get("authors", "") or "(未知)"
        year = card.get("year", "")
        ref_type = card.get("ref_type", "其他")
        user_msg = f"""请验证以下参考文献：

作者：{authors}
年份：{year}
类型：{ref_type}
引用格式：{formatted[:500]}"""

        try:
            response = client.messages.create(
                model=model, max_tokens=256,
                thinking={"type": "disabled"},
                system=_VERIFY_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = ""
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    text += block.text
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            result = json.loads(text)
        except Exception:
            # Retry once
            try:
                response = client.messages.create(
                    model=model, max_tokens=256,
                    thinking={"type": "disabled"},
                    system=_VERIFY_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                )
                text = ""
                for block in response.content:
                    if getattr(block, "type", "") == "text":
                        text += block.text
                text = text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[-1]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                result = json.loads(text)
            except Exception:
                # On double failure, admit the card (conservative)
                card["verified"] = 0
                card["verification_note"] = ""
                return card

        status = result.get("status", "fake")
        if status == "fake":
            return None  # Drop the card
        elif status == "format_error":
            card["verified"] = -2
            card["verification_note"] = result.get("note", "")[:200]
        else:  # verified
            card["verified"] = 1
            card["verification_note"] = ""
        return card

    kept: List[Dict[str, Any]] = []
    dropped = 0
    verified_count = 0
    format_err_count = 0

    with ThreadPoolExecutor(max_workers=_VERIFY_CONCURRENCY) as executor:
        futures = {executor.submit(_verify_one, c): i for i, c in enumerate(cards)}
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                dropped += 1
            else:
                kept.append(result)
                if result.get("verified") == 1:
                    verified_count += 1
                elif result.get("verified") == -2:
                    format_err_count += 1

    log(f"  验证完成: ✓{verified_count} ~{format_err_count} ✗{dropped} (保留 {len(kept)})")
    return kept


def _strip_ref_number(text: str) -> str:
    """去除引用文本前的序号，如 '[1] ', '[58]', '①' 等。"""
    import re as _re
    return _re.sub(r"^\[?\d{1,3}\]?\s*", "", text).strip()


def _clean_citation_text(text: str) -> str:
    """修复引用文本中的换行和常见 PDF 提取瑕疵。"""
    import re as _re
    # 1. 去除页面残留（如 "浙江大学参考文献", "## Page 81", "复旦大学"水印重复）
    text = _re.sub(r"\n*(?:#+\s*Page\s+\d+\s*)?(?:浙江|复旦|上海交大|北京|清华|华中科大|武汉|哈尔滨|南京|西安|四川|中山|华南|东南|天津|南开|山东|中国)[^\n]{0,30}(?:大学|学院)?[^\n]{0,20}参考文[献献][^\n]*\n*", "", text)
    # 去除大学水印重复（如 "复旦大学复旦大学..."）
    text = _re.sub(r"(复旦|交通|清华|北大|浙大|同济|北航|武汉|中山|华南|东南|南开|山东|川大|厦大){5,}", "", text)
    # 2. 连接被换行截断的引用行
    text = _re.sub(r"([,\d])\s*\n\s*(\d|[\(（])", r"\1\2", text)
    text = _re.sub(r"([一-鿿])\s*\n\s*(?=[一-鿿\d])", r"\1", text)
    text = _re.sub(r"([a-z])\s*\n\s*([a-z(])", r"\1\2", text)
    # 3. 修复连续双点（PDF 丢字常见：j..hzjjykj → j.hzjjykj）
    text = _re.sub(r"\.\.", ".", text)
    # 4. 合并连续空格
    text = _re.sub(r"  +", " ", text)
    return text.strip()


def _is_citation_garbage(text: str) -> bool:
    """检测是否是非引用的垃圾文本（问卷选项、部门调查等混入参考文献区）。"""
    patterns = [
        r"\(?(?:单选|多选|可多选|不定项选)\)?",
        r"[A-Ea-e][.、）\)]\s*.{1,30}\s+[B-Eb-e][.、）\)]",
        r"(?:非常(?:满意|了解|需要|及时|愿意|同意|符合|好|高|强|大))"
        r".{0,30}(?:比较(?:满意|了解|需要|及时|愿意|同意|符合|好|高|强|大))",
        r"(?:研发部|质量部|生产部|管理部|销售部|财务部|人事部).{0,10}"
        r"(?:研发部|质量部|生产部|管理部|销售部|财务部|人事部)",
        r"(?:很不满意|不满意|一般|满意|很满意).{0,30}(?:很不满意|不满意|一般|满意|很满意)",
        r"您的?(?:部门|职位|岗位|年龄|性别|学历|工作年限)",
    ]
    for pat in patterns:
        if re.search(pat, text):
            return True
    return False


def _build_citation_card(
    paper: Dict[str, Any], ref: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """从论文和引用条目构建引用卡片。"""
    formatted = _clean_citation_text(_strip_ref_number(ref.get("formatted", "")))
    if len(formatted) < 15:
        return None
    if _is_citation_garbage(formatted):
        return None

    ref_type = ref.get("type", "其他")
    paper_methods = paper.get("methods", [])
    card_quality = _compute_card_quality(formatted, ref_type, paper_methods)

    return {
        "card_id": f"CITE-{uuid.uuid4().hex[:8].upper()}",
        "paper_id": paper["doc_id"],
        "formatted": formatted,
        "title": ref.get("title", formatted[:120]),
        "authors": "",
        "year": str(paper.get("year", "")),
        "language": paper.get("language", "zh"),
        "ref_type": ref_type,
        "methods": paper_methods,
        "direction_id": paper.get("direction_id", ""),
        "direction_label": paper.get("direction_label", ""),
        "theory_tags": paper.get("theory_frameworks", []),
        "verified": 0,
        "inserted_count": 0,
        "quality_score": card_quality,
        "source_section": "参考文献",
        "source_paper_title": paper.get("title", ""),
    }


def _rebuild_vector_index(papers: List[Dict[str, Any]], log) -> None:
    """重建向量索引。清除旧数据后重新索引。"""
    store = LocalVectorStore()
    try:
        # 清空旧数据
        store.connection.execute("DELETE FROM chunks")
        store.connection.execute("DELETE FROM documents")
        store.connection.commit()

        total_chunks = 0
        for i, paper in enumerate(papers):
            source_path = paper["source_path"]
            # 读取清洗后的文本
            paper_path = PROJECT_ROOT / source_path
            if not paper_path.exists():
                paper_path = KB_CLEANED_ROOT / Path(source_path).name
            if not paper_path.exists():
                continue

            try:
                text = paper_path.read_text(encoding="utf-8")
            except Exception:
                continue

            # 插入文档记录
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            store.connection.execute(
                "INSERT INTO documents (path, title, content_hash, metadata_json) VALUES (?, ?, ?, ?)",
                (
                    source_path,
                    paper["title"],
                    content_hash,
                    json.dumps({
                        "direction": paper["direction_id"],
                        "methods": paper["methods"],
                        "quality_score": paper["quality_score"],
                    }, ensure_ascii=False),
                ),
            )
            doc_id = store.connection.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

            # 分块并插入
            from vector_store import embed_text
            chunks = _split_text(text, max_tokens=400)
            for ci, chunk in enumerate(chunks):
                try:
                    embedding = embed_text(chunk)
                except Exception:
                    embedding = [0.0] * 512
                store.connection.execute(
                    "INSERT INTO chunks (document_id, chunk_index, content, vector_json, token_count) VALUES (?, ?, ?, ?, ?)",
                    (doc_id, ci, chunk, json.dumps(embedding), len(chunk)),
                )
                total_chunks += 1

            if (i + 1) % 50 == 0:
                log(f"  已索引 {i + 1}/{len(papers)} 篇，{total_chunks} 个块")

        store.connection.commit()
        log(f"  向量索引完成：{len(papers)} 篇论文，{total_chunks} 个块")
    finally:
        store.close()


def _split_text(text: str, max_tokens: int = 400) -> List[str]:
    """将文本分割为适宜大小的块。"""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) < max_tokens:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [text]
