"""
从清洗后的 Markdown 论文中结构化抽取：标题、作者、年份、来源、摘要、关键词、
正文章节、研究方法、参考文献列表、质量评分。
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 领域概念强匹配关键词（纯学科术语，方法名从注册中心动态补充）
_DIRECTION_DOMAIN_CONCEPTS: Dict[str, List[str]] = {
    "quality_management": [
        "质量管理", "质量改进", "质量改善", "质量控制", "质量保证", "质量优化",
        "质量体系", "质量标准",
    ],
    "risk_management": [
        "风险管理", "风险评估", "风险控制", "风险分析", "风险应对", "安全隐患",
        "风控体系", "反欺诈", "信息安全",
    ],
    "schedule_management": [
        "进度管理", "工期优化", "进度控制", "进度计划", "排产", "交付周期",
        "工期延误",
    ],
    "requirements_management": [
        "需求管理", "需求分析", "需求变更", "需求工程", "产品需求", "需求优先级",
    ],
    "process_optimization": [
        "流程优化", "流程改善", "流程改进", "流程再造", "过程改进", "开发流程",
        "业务流程",
    ],
    "cost_management": [
        "成本管理", "成本控制", "成本优化", "投资管理", "降本增效", "成本分析",
    ],
    "supply_chain_logistics": [
        "供应链", "物流管理", "配送优化", "库存管理", "采购管理", "供应商管理",
        "仓储", "运输优化",
    ],
}

def _build_direction_strong_keywords() -> Dict[str, List[str]]:
    """从注册中心动态构建方向强匹配关键词（领域概念 + 方法名/别名）。"""
    from src.method_registry import get_registry as _dsk_reg
    _reg = _dsk_reg()
    _domains_map = _reg.get_domain_to_names()
    _aliases_map = _reg.get_aliases()
    _result: Dict[str, List[str]] = {}
    for _dir_id, _concepts in _DIRECTION_DOMAIN_CONCEPTS.items():
        _kws = list(_concepts)
        for _method_name in _domains_map.get(_dir_id, []):
            if _method_name not in _kws:
                _kws.append(_method_name)
            for _alias in _aliases_map.get(_method_name, []):
                if _alias not in _kws:
                    _kws.append(_alias)
        _result[_dir_id] = _kws
    return _result

DIRECTION_STRONG_KEYWORDS: Dict[str, List[str]] = _build_direction_strong_keywords()

def _get_method_keywords() -> Dict[str, List[str]]:
    """从方法注册中心动态加载方法名→关键词映射。"""
    from src.method_registry import get_method_keywords
    return get_method_keywords()

DIRECTION_LABELS = {
    "quality_management": "质量管理",
    "risk_management": "风险管理",
    "schedule_management": "进度管理",
    "requirements_management": "需求管理",
    "process_optimization": "流程优化",
    "cost_management": "成本管理",
    "supply_chain_logistics": "供应链与物流",
}


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    """解析 YAML frontmatter，返回 dict。"""
    fm: Dict[str, Any] = {}
    # 正常多行 YAML: ---\n...\n---
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        # 丢失开头 --- 但保留结尾 ---: key: val\n...\n---
        m = re.match(r"^([a-z_]+:.+?)\n---", text, re.DOTALL)
    if not m:
        # 单行 YAML（旧版清洗 bug）: ---key:val...---
        m = re.match(r"^---(.+?)---", text)
    if not m:
        return fm

    raw = m.group(1).strip()
    if yaml and "\n" in raw:
        try:
            fm = yaml.safe_load(raw) or {}
        except Exception:
            pass
    if not fm:
        # 回退：逐行或逐键解析 key: value 对
        segments = raw.split("\n") if "\n" in raw else [raw]
        for line in segments:
            line = line.strip()
            # 可能多个 key:value 被连在一起，按模式拆分
            parts = re.findall(r"([a-z_]+):\s*([^:\n]+?)(?=[a-z_]+:|$)", line)
            for key, val in parts:
                key = key.strip()
                val = val.strip().rstrip(",")
                if key == "methodologies" or key == "tags":
                    fm[key] = [v.strip() for v in val.split(",") if v.strip()]
                else:
                    fm[key] = val
    return fm


def extract_paper(file_path: Path, doc_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """从一篇清洗后的 MD 论文中抽取结构化数据。"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    if len(text) < 200:
        return None

    frontmatter = _parse_frontmatter(text)

    title = _extract_title(text, file_path.stem, frontmatter)
    authors = _extract_authors(text, frontmatter, file_path.stem)
    year = _extract_year(text, frontmatter)
    source = _extract_source(text, file_path)
    abstract = _extract_abstract(text)
    keywords = _extract_keywords(text)
    sections = _extract_sections(text)
    methods = _extract_methods(text, title, abstract, frontmatter)
    references = _extract_references(text)
    direction_id, direction_label = _classify_direction(title, abstract, keywords, file_path, frontmatter)
    theory_frameworks = _classify_theory(title, abstract, methods)
    quality_score = _compute_quality_score(title, authors, abstract, keywords, references, methods)
    localization_score = _compute_localization_score(title, abstract, text)

    path_hash = hashlib.sha256(str(file_path).encode()).hexdigest()[:12].upper()
    return {
        "doc_id": doc_id or f"PAPER-{path_hash}",
        "title": title,
        "authors": authors,
        "year": year,
        "source": source,
        "source_path": str(file_path.relative_to(PROJECT_ROOT)),
        "abstract": abstract,
        "keywords": keywords,
        "sections": sections,
        "methods": methods,
        "theory_frameworks": theory_frameworks,
        "direction_id": direction_id,
        "direction_label": direction_label,
        "quality_score": round(quality_score, 4),
        "localization_score": round(localization_score, 4),
        "reference_count": len(references),
        "word_count": len(text),
        "language": "zh" if _is_chinese_dominant(text) else "en",
        "references_raw": references,
    }


def _extract_title(text: str, fallback: str, fm: Dict[str, Any]) -> str:
    """提取论文题目。优先使用 frontmatter，其次 regex。"""
    # 优先使用 frontmatter
    fm_title = fm.get("title", "").strip()
    if fm_title and 5 < len(fm_title) < 100 and re.search(r"[一-鿿]", fm_title):
        return fm_title

    head = text[:800]
    patterns = [
        r"中文论文题目[：:]\s*(.+?)(?:\n|$)",
        r"(?:论文)?题目[：:]\s*(.+?)(?:\n|$)",
        r"(?:题\s*目)[：:]\s*(.+?)(?:\n|$)",
        r"^#\s+(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, head, re.MULTILINE)
        if m:
            t = m.group(1).strip()
            # 至少包含一个中文字符
            if 5 < len(t) < 100 and re.search(r"[一-鿿]", t):
                return t
    first_line = text.split("\n")[0].strip().lstrip("#").strip()
    if 5 < len(first_line) < 80 and any(
        kw in first_line for kw in ["研究", "管理", "分析", "优化", "改进", "改善"]
    ):
        return first_line
    return fallback


def _extract_authors(text: str, fm: Dict[str, Any], stem: str = "") -> List[str]:
    """提取作者。"""
    head = text[:2000]
    patterns = [
        r"申请人姓名[：:]\s*([一-鿿]{2,3})(?:指导|合作|专业|所在|论文|学号|密级|完成)",
        r"(?:硕士|博士|研究生).{0,6}姓名[：:]\s*([一-鿿]{2,3})(?:指导|合作|专业|所在|论文|学号|密级|完成)",
        r"姓名[：:]\s*([一-鿿]{2,3})(?:指导|合作|专业|所在|论文|学号|密级|完成)",
        r"研究生[：:]\s*([一-鿿]{2,3})(?:指导|合作|专业|所在|论文|学号|密级|完成)",
        r"(?:作者|学位申请人|学生)[：:]\s*([一-鿿]{2,3})(?:指导|合作|专业|所在|论文|学号|密级|完成)",
    ]
    for pat in patterns:
        m = re.search(pat, head, re.MULTILINE)
        if m:
            name = m.group(1).strip()
            if 2 <= len(name) <= 4:
                return [name]

    # 从文件名末尾猜测作者名（排除常见后缀）
    skip_suffixes = {"答辩版", "终稿", "终稿版", "盲审版", "送审版", "初稿", "修改稿", "致谢", "致谢+昌飞"}
    parts = stem.split("_")
    for part in reversed(parts):
        part = part.strip()
        if part in skip_suffixes:
            continue
        # 也跳过数字开头或含ASCII的片段
        if re.match(r"^\d", part):
            continue
        if part.endswith("版"):
            continue
        if 2 <= len(part) <= 4 and re.fullmatch(r"[一-鿿]{2,4}", part):
            return [part]
    return []


def _extract_year(text: str, fm: Dict[str, Any]) -> int:
    """提取年份。"""
    head = text[:2000]
    # 提交日期
    m = re.search(r"(?:论文提交日期|完成日期|答辩日期|日期)\s*[：:]*\s*(\d{4})", head)
    if m:
        return int(m.group(1))
    # 任意四位数年份
    m = re.search(r"20(?:0\d|1\d|2[0-6])\s*年", head)
    if m:
        return int(m.group(0)[:4])
    return 0


def _extract_source(text: str, file_path: Path) -> str:
    """提取来源（学校/期刊）。"""
    head = text[:1500]
    # 大学名称
    m = re.search(r"([一-鿿]{2,12}(?:大学|学院|研究院))", head)
    if m:
        return m.group(1)
    # 从路径判断
    path_str = str(file_path)
    for uni in ["清华", "北大", "上交", "复旦", "浙大", "中科大", "同济", "北航", "北理工"]:
        if uni in path_str:
            return uni + "大学"
    return ""


def _extract_abstract(text: str) -> str:
    """提取摘要。跳过 TOC 中的条目，匹配真实摘要段落。"""
    # 找到所有 摘要/ABSTRACT 位置，选第一个后面有实质内容的
    candidates = []
    for m in re.finditer(r"(?:摘要|ABSTRACT|Abstract)", text):
        pos = m.end()
        # 跳过 ":：\n " 等分隔符
        while pos < len(text) and text[pos] in ":：\n\r ":
            pos += 1
        # 跳过 "II" "III" 等罗马数字页码
        if pos < len(text) and re.match(r"[IVX]+", text[pos:pos+10]):
            sub = text[pos:pos+10]
            pos += len(re.match(r"[IVX]+\s*", text[pos:pos+10]).group())
        after = text[pos:pos+80].strip()
        # TOC 条目通常后跟省略号或很短
        if after and len(after) > 15 and not re.match(r"^[.\s…]{10,}", after):
            candidates.append(pos)
        # 也通过后方关键词来确认
        kw_pos = text.find("关键词", pos, pos+2000)
        if kw_pos > 0:
            between = text[pos:kw_pos].strip()
            if len(between) > 30:
                candidates.append(pos)

    if not candidates:
        return ""

    pos = candidates[0]
    # 提取到关键词或下一个标题
    end_patterns = [
        r"\n\s*(?:关键词|关键字|Key\s*words|Keywords)\s*[：:]",
        r"\n\s*(?:ABSTRACT|Abstract)",
        r"\n\n[^\n]{2,20}\n",
        r"\n\n##\s",
    ]
    end_pos = len(text)
    for ep in end_patterns:
        m = re.search(ep, text[pos:pos+2000], re.IGNORECASE)
        if m:
            end_pos = min(end_pos, pos + m.start())
    if end_pos == len(text):
        end_pos = min(len(text), pos + 2000)

    abstract = text[pos:end_pos].strip()
    abstract = re.sub(r"\s+", " ", abstract)
    if 30 < len(abstract) < 3000:
        return abstract[:1500]
    return ""


def _extract_keywords(text: str) -> List[str]:
    """提取关键词。"""
    head = text[:2000]
    patterns = [
        r"(?:关键词|关键字|Keywords?)\s*[：:]\s*(.+?)(?:\n|$)",
        r"【关键词】(.*?)(?:【|\n)",
    ]
    for pat in patterns:
        m = re.search(pat, head, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            # 分割
            keywords = re.split(r"[；;，,\s]+", raw)
            return [k.strip() for k in keywords if 1 < len(k.strip()) < 20][:10]
    return []


def _extract_sections(text: str) -> List[Dict[str, str]]:
    """提取章节结构。"""
    sections = []
    pattern = r"^(?:第[一二三四五六七八九十\d]+章|(?:[1-9]\d*\.?\s*|（[一二三四五六七八九十]）)).+"
    for m in re.finditer(pattern, text, re.MULTILINE):
        title = m.group(0).strip()
        if 3 < len(title) < 60:
            sections.append({"title": title, "position": m.start()})
    return sections


def _extract_methods(text: str, title: str, abstract: str, fm: Dict[str, Any]) -> List[str]:
    """从 frontmatter、题目、摘要、正文中提取研究方法。"""
    found_methods = set()

    _mk = _get_method_keywords()

    # 1) Frontmatter methodologies 字段（最可靠）
    fm_methods = fm.get("methodologies", "")
    if isinstance(fm_methods, list):
        fm_methods = " ".join(fm_methods)
    if fm_methods:
        for method, keywords in _mk.items():
            if any(kw.lower() in fm_methods.lower() for kw in keywords):
                found_methods.add(method)

    # 2) 全文搜索方法关键词
    search_text = f"{title} {abstract} {text[:10000]}"
    for method, keywords in _mk.items():
        if any(kw.lower() in search_text.lower() for kw in keywords):
            found_methods.add(method)

    return sorted(found_methods)


def _extract_references(text: str) -> List[Dict[str, str]]:
    """提取参考文献列表。"""
    ref_start = _find_reference_start(text)
    if ref_start < 0:
        return []

    ref_text = text[ref_start:]
    # 按编号分割
    entries = re.split(r"\n(?=\[\d+\]|\d+[.)]\s)", ref_text)

    # 合并碎片：过短的条目合并到前一条
    merged: List[str] = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        if len(entry) < 30 and merged:
            merged[-1] = merged[-1] + " " + entry
        elif len(entry) >= 20:
            merged.append(entry)

    refs = []
    for entry in merged:
        entry = entry.strip()
        if len(entry) < 20:
            continue
        # 过滤明显垃圾：全是空白/特殊字符、图片标记、纯URL
        if re.match(r"^[\s\W\d_]+$", entry):
            continue
        if "图片" in entry[:10] and len(entry) < 80:
            continue
        # 过滤 PDF 页眉页脚水印混入
        if _is_reference_garbage(entry):
            continue
        refs.append({
            "formatted": entry[:500],
            "title": _guess_ref_title(entry),
            "type": _guess_ref_type(entry),
        })
    return refs[:120]


def _is_reference_garbage(text: str) -> bool:
    """检测是否是非引用的垃圾文本（页眉水印、附录、问卷等混入参考文献区）。"""
    garbage_patterns = [
        # 大学水印（连续重复 > 5 次）
        r"(复旦|交通|清华|北大|浙大|中科大|同济|北航|北理工){5,}",
        # 论文声明
        r"(原创性声明|独创性声明|学位论文原创性|学位论文版权|保密论文|涉密论文)",
        # 附录
        r"^附录[一二三四五六七八九十\d]",
        # 问卷/访谈
        r"^(?:附[录\d]+\s*)?(?:调查问卷|访谈提纲|访谈问题|问卷设计|问卷调查表)",
        r"您对.{0,30}(?:满意|期望|建议|看法)",
        r"(?:非常满意|比较满意|一般|不满意|非常不满意).{0,20}(?:非常满意|比较满意)",
        # 单选/多选标记
        r"\(?(?:单选|多选|可多选|不定项选)\)?",
        # 多选题选项格式 (A. xxx B. xxx C. xxx)
        r"[A-Ea-e][.、）\)]\s*.{1,30}\s+[B-Eb-e][.、）\)]",
        # Likert 量表连续选项
        r"(?:非常(?:满意|了解|需要|及时|愿意|同意|符合|好|高|强|大))"
        r".{0,30}(?:比较(?:满意|了解|需要|及时|愿意|同意|符合|好|高|强|大))",
        # Likert 数字编码形式 (1=非常不同意 2=不同意 ...)
        r"\d\s*[=＝]\s*(?:非常|比较|一般|不太|很|较为|极其)",
        # 公司部门罗列（问卷常见）
        r"(?:研发部|质量部|生产部|管理部|销售部|财务部|人事部).{0,10}"
        r"(?:研发部|质量部|生产部|管理部|销售部|财务部|人事部)",
        # Page 标记
        r"^#{1,3}\s*Page\s+\d+",
        # 致谢
        r"^致\s*谢\s*$",
        # 纯粹的水印重复（同一字符/词重复 > 20 次）
        r"(.)\1{20,}",
        # 编号开头的问卷题目
        r"^(?:\d+[.、)]\s*|第[一二三四五六七八九十\d]+题[:：]?\s*)"
        r"(?:您|请|是否|如何|什么|哪些|请问|认为|觉得|了解|知道|同意)",
        r"(?:问题\d+|Q\d+|题目\d+)[:：\s]",
        # 评分/权重矩阵残留
        r"^(?:权重|得分|评分|均值|标准差|方差)\s*[\d.]+\s*",
        r"[\d.]+\s+(?:权重|得分|评分)\s*[\d.]+",
        # 纯数字统计表行（如 "1 3.45 2.18 4.01 3.92" 连续4+个数字）
        r"^[\d.]{1,6}\s+[\d.]{1,6}\s+[\d.]{1,6}\s+[\d.]{1,6}",
    ]
    for pat in garbage_patterns:
        if re.search(pat, text):
            return True
    return False


def _classify_direction(
    title: str, abstract: str, keywords: List[str], file_path: Path,
    fm: Dict[str, Any],
) -> Tuple[str, str]:
    """分类研究方向：frontmatter + 标题+摘要强匹配。"""
    # 优先使用 frontmatter 中的 research_direction
    fm_dir = fm.get("research_direction", "").strip()
    for dir_id, label in DIRECTION_LABELS.items():
        if dir_id in fm_dir.lower() or label in fm_dir:
            return dir_id, label

    search_text = f"{title} {abstract} {' '.join(keywords)}"
    path_str = str(file_path).lower()

    for dir_id, strong_kws in DIRECTION_STRONG_KEYWORDS.items():
        score = 0
        for kw in strong_kws:
            if kw in search_text:
                score += 2
            if kw in path_str:
                score += 1
        if score >= 2:
            return dir_id, DIRECTION_LABELS.get(dir_id, dir_id)

    return "", "未分类"


def _classify_theory(title: str, abstract: str, methods: List[str]) -> List[str]:
    """分类理论框架。"""
    search_text = f"{title} {abstract} {' '.join(methods)}"
    theories = []
    from paper_store import THEORY_FRAMEWORKS
    for framework, keywords in THEORY_FRAMEWORKS.items():
        if any(kw in search_text for kw in keywords):
            theories.append(framework)
    return theories


def _compute_quality_score(
    title: str,
    authors: List[str],
    abstract: str,
    keywords: List[str],
    references: List[Dict],
    methods: List[str],
) -> float:
    """计算论文质量评分 (0-1)。"""
    score = 0.0
    if title and len(title) > 5:
        score += 0.10
    if authors:
        score += 0.08
    if abstract and len(abstract) > 30:
        score += 0.20
    if len(abstract) > 200:
        score += 0.05
    if keywords:
        score += 0.07
    if len(references) >= 5:
        score += 0.10
    if len(references) >= 15:
        score += 0.10
    if methods:
        score += min(0.15, len(methods) * 0.03)
    # 标题含方法论加分
    if any(m in title for m in ["研究", "分析", "优化", "改进", "改善", "管理"]):
        score += 0.05
    # 摘要含深度方法论加分
    if abstract and any(m in abstract for m in ["方法", "模型", "框架", "体系", "流程", "机制"]):
        score += 0.05
    # 摘要长度反映论文扎实程度
    if len(abstract) > 500:
        score += 0.05
    return min(1.0, score)


def _compute_localization_score(title: str, abstract: str, text: str) -> float:
    """计算本地化评分 (0-1)：论文是否聚焦中国企业/行业场景。"""
    score = 0.0
    chinese_company_patterns = [
        r"[A-Z]公司", r"有限(?:责任)?公司", r"集团", r"股份",
        r"中国", r"国内", r"本土",
    ]
    search = f"{title} {abstract} {text[:5000]}"
    for pat in chinese_company_patterns:
        if re.search(pat, search):
            score += 0.15
    return min(1.0, score)


def _find_reference_start(text: str) -> int:
    """定位参考文献起始位置。"""
    patterns = [
        # 标准标题行
        r"^#{1,3}\s*参考文献\s*$",
        r"^参考文献\s*$",
        r"^【参考文献】\s*$",
        r"^References?\s*$",
        # PDF 转换后粘连在一行："浙江大学参考文献参考文献[1]..."
        r"参考文献参考文献\s*\[?\d+",
        # 参考文献后面紧挨着引用条目（无换行分隔）
        r"参考文献\s*\[\d+\]",
        r"参考文献\s*［\d+］",
        # 参考文献后面紧跟换行和引用
        r"参考文献\s*\n\s*\[\d+\]",
        r"参考文献\s*\n\s*［\d+］",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.MULTILINE | re.IGNORECASE)
        if m:
            # 找到"参考文献"这个词的位置，返回它之后的第一个引用
            ref_word = re.search(r'参考文献', m.group())
            if ref_word:
                return m.start() + ref_word.end()
            return m.end()
    return -1


def _guess_ref_title(entry: str) -> str:
    """从引用条目猜测文献标题。"""
    # 期刊格式: 作者. 题名[J]. 刊名
    m = re.search(r"[.)]\s*(.+?)(?:\[[JMCNDP]]|，?\d{4})", entry)
    if m:
        return m.group(1).strip()[:120]
    return entry[:120]


def _guess_ref_type(entry: str) -> str:
    """猜测引用类型。"""
    type_map = {
        "[J]": "期刊文章", "[M]": "图书", "[C]": "会议论文",
        "[D]": "学位论文", "[N]": "报纸", "[P]": "专利",
        "[EB/OL]": "电子资源", "[S]": "标准", "[R]": "报告",
    }
    for code, label in type_map.items():
        if code in entry:
            return label
    return "其他"


def _is_chinese_dominant(text: str) -> bool:
    """判断文本是否以中文为主。"""
    chinese_chars = len(re.findall(r"[一-鿿]", text[:2000]))
    return chinese_chars > 50
