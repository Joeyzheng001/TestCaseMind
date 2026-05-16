"""
方法卡阶段化注入模块。
根据章节类型、用户选定方法、学科和领域，从 cards 库检索方法卡，
按 inject_policy 控制注入内容和 token 量。
"""

from __future__ import annotations

import json
import sqlite3
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_DB = PROJECT_ROOT / "knowledge_base" / "cards.sqlite3"

# 章节类型 → applicable_sections 映射
CHAPTER_TYPE_TO_SECTION = {
    "chapter_1": ["chapter_1_introduction"],
    "chapter_2": ["chapter_2_literature_review"],
    "chapter_3": ["chapter_3_methodology"],
    "chapter_4": ["chapter_4_problem_analysis", "chapter_4_solution_design"],
    "chapter_5": ["chapter_5_evaluation"],
    "chapter_6": ["chapter_6_conclusion"],
}

# 按阶段分组的注入小节
STAGE_INJECT_MAP = {
    "chapter_planning": [
        "方法定位", "适用场景", "不适用场景", "适用章节",
    ],
    "chapter_generation": [
        "方法定位", "定义", "适用场景", "输入数据", "输出结果",
        "操作步骤", "常见错误", "示例表达", "生成约束",
    ],
    "risk_check": [
        "常见错误", "生成约束",
    ],
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(CARDS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def classify_chapter_type(chapter_title: str) -> str:
    """从章节标题推断章节类型。"""
    title = chapter_title.lower()
    if any(w in title for w in ["绪论", "引言", "背景", "引言", "introduction"]):
        return "chapter_1"
    if any(w in title for w in ["文献", "综述", "现状", "研究现状", "literature", "review"]):
        return "chapter_2"
    if any(w in title for w in ["方法", "研究设计", "method", "methodology"]):
        return "chapter_3"
    if any(w in title for w in ["改进", "方案", "优化", "设计", "解决", "solution"]):
        return "chapter_4"
    if any(w in title for w in ["效果", "评价", "验证", "评估", "实证", "evaluation", "result"]):
        return "chapter_5"
    if any(w in title for w in ["结论", "展望", "总结", "conclusion"]):
        return "chapter_6"
    return "chapter_4"  # 默认按方案章节处理


def search_method_cards(
    methods: List[str],
    discipline: str = "mem",
    domain: Optional[str] = None,
    chapter_type: Optional[str] = None,
    phase: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """
    从 SQLite 检索匹配的方法卡。按方法名精确匹配 + 学科/领域/阶段过滤。
    返回匹配度排序的卡片列表。
    """
    conn = _connect()
    try:
        # 收集所有匹配的方法卡 ID
        all_ids: set = set()
        method_id_map: Dict[str, str] = {}  # alias → canonical_id

        # 构建别名 → id 映射
        try:
            rows = conn.execute("SELECT id, name, aliases FROM cards WHERE status = 'reviewed'").fetchall()
        except sqlite3.OperationalError:
            return []
        for row in rows:
            card_id = row["id"]
            aliases = json.loads(row["aliases"]) if row["aliases"] else []
            for alias in aliases:
                if alias.lower() not in method_id_map:
                    method_id_map[alias.lower()] = card_id
            method_id_map[row["name"].lower()] = card_id

        # 匹配用户选择的方法名
        for method_name in methods:
            key = method_name.lower()
            if key in method_id_map:
                all_ids.add(method_id_map[key])

        if not all_ids:
            return []

        # 查询完整卡片
        placeholders = ",".join("?" for _ in all_ids)
        query = f"""
            SELECT * FROM cards
            WHERE id IN ({placeholders})
            AND status = 'reviewed'
            AND scope = 'platform'
        """
        rows = conn.execute(query, list(all_ids)).fetchall()

        # 解析并过滤
        results = []
        for row in rows:
            card = dict(row)
            # 反序列化 JSON 字段
            for field in ["phase", "disciplines", "domains", "applicable_sections",
                          "aliases", "pairs_with", "requires", "conflicts_with",
                          "data_type", "outputs", "risk_tags"]:
                val = card.get(field)
                if isinstance(val, str):
                    try:
                        card[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass

            # 过滤
            if discipline and discipline not in card.get("disciplines", []):
                continue
            if domain and domain not in card.get("domains", []):
                continue
            if chapter_type:
                target_sections = CHAPTER_TYPE_TO_SECTION.get(chapter_type, [])
                if target_sections and not any(
                    s in card.get("applicable_sections", []) for s in target_sections
                ):
                    continue
            if phase and phase not in card.get("phase", []):
                continue

            # 计算匹配度 (alias 匹配数 + 学科/领域/章节命中)
            score = 1
            if domain and domain in card.get("domains", []):
                score += 1
            if chapter_type:
                target_sections = CHAPTER_TYPE_TO_SECTION.get(chapter_type, [])
                if target_sections and any(
                    s in card.get("applicable_sections", []) for s in target_sections
                ):
                    score += 1
            if phase and phase in card.get("phase", []):
                score += 1
            card["_match_score"] = score
            results.append(card)

        results.sort(key=lambda c: c["_match_score"], reverse=True)
        return results[:limit]
    finally:
        conn.close()


def render_card_for_stage(
    card: Dict[str, Any],
    stage: str = "chapter_generation",
) -> str:
    """
    从卡片中提取指定阶段需要的内容，生成注入文本。
    """
    inject_policy = card.get("inject_policy", {})
    if isinstance(inject_policy, str):
        try:
            inject_policy = json.loads(inject_policy)
        except (json.JSONDecodeError, TypeError):
            inject_policy = {}

    allowed_sections = inject_policy.get("inject_sections", [])
    max_tokens_estimate = inject_policy.get("max_tokens", 800)

    # 也可以用 STAGE_INJECT_MAP 作为 fallback
    if not allowed_sections:
        allowed_sections = STAGE_INJECT_MAP.get(stage, ["定义", "常见错误", "生成约束"])

    body = card.get("body_markdown", "")
    name = card.get("name", "")

    # 提取允许的小节
    output_parts = [f"## {name}"]

    for section_name in allowed_sections:
        pattern = rf"^## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\Z)"
        m = re.search(pattern, body, re.DOTALL | re.MULTILINE)
        if m:
            section_text = m.group(1).strip()
            output_parts.append(f"### {section_name}")
            output_parts.append(section_text)
            output_parts.append("")

    rendered = "\n".join(output_parts)

    # 粗略 token 控制: 中文字符数 ≈ tokens
    if len(rendered) > max_tokens_estimate * 2:
        rendered = rendered[: max_tokens_estimate * 2] + "\n...[截断]"

    return rendered


def build_method_context(
    chapter: Dict[str, Any],
    selected_methods: List[str],
    discipline: str = "mem",
    domain: Optional[str] = None,
    stage: str = "chapter_generation",
    max_cards: int = 5,
) -> str:
    """
    主入口：构建方法上下文，注入到 local_expand prompt 中。

    返回一个可直接嵌入 prompt 的字符串。
    """
    chapter_title = chapter.get("title", "")
    chapter_type = classify_chapter_type(chapter_title)

    cards = search_method_cards(
        methods=selected_methods,
        discipline=discipline,
        domain=domain,
        chapter_type=chapter_type,
        limit=max_cards,
    )

    if not cards:
        return ""

    injected = []
    total_chars = 0
    max_total = 3000  # 总字符上限

    for card in cards:
        rendered = render_card_for_stage(card, stage=stage)
        if total_chars + len(rendered) > max_total:
            break
        injected.append(rendered)
        total_chars += len(rendered)

    if not injected:
        return ""

    header = "[方法知识卡] 以下是与本章相关的方法规范，请严格遵循其中的操作步骤、常见错误和生成约束：\n\n"
    return header + "\n---\n".join(injected)


def list_method_aliases() -> Dict[str, str]:
    """返回所有方法别名 → 规范名称的映射。"""
    conn = _connect()
    try:
        try:
            rows = conn.execute(
                "SELECT id, name, short_name, aliases FROM cards WHERE status = 'reviewed'"
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        mapping = {}
        for row in rows:
            name = row["name"]
            for alias in [name, row["short_name"], *json.loads(row["aliases"] or "[]")]:
                if alias and alias not in mapping:
                    mapping[alias] = name
        return mapping
    finally:
        conn.close()
