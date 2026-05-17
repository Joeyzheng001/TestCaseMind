"""
知识库管理器 — 分类存储、元数据提取、大纲索引。

解决核心问题：
- convert_references_to_markdown 只做转换，不打标签
- build_index 元数据太薄（只有 source / file_type）
- 检索时无法按研究方向/方法论过滤
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_ROOT = PROJECT_ROOT / "knowledge_base" / "references"
KB_CONVERTED_ROOT = KB_ROOT / "converted"
KB_OUTLINES_ROOT = PROJECT_ROOT / "knowledge_base" / "outlines"
CATALOG_PATH = PROJECT_ROOT / "knowledge_base" / "catalog.json"

PAPER_DIR_NAMES = {
    "质量管理", "风险管理", "进度管理", "成本管理", "流程优化",
    "绩效评价", "需求管理", "供应链物流", "通用项目管理", "其他",
}

METHODOLOGY_DIR_MAP: Dict[str, str] = {}
TEMPLATE_DIR_NAMES = {"模型规范类", "templates", "模板"}


def _ensure_methodology_map() -> Dict[str, str]:
    global METHODOLOGY_DIR_MAP
    if METHODOLOGY_DIR_MAP:
        return METHODOLOGY_DIR_MAP

    methodology_root = KB_ROOT / "方法论资料类"
    if not methodology_root.exists():
        return METHODOLOGY_DIR_MAP

    for path in sorted(methodology_root.iterdir()):
        if not path.is_dir():
            continue
        name = path.name.strip()
        clean = re.sub(r"^\d+\.", "", name).strip()
        METHODOLOGY_DIR_MAP[clean] = clean
        METHODOLOGY_DIR_MAP[name] = clean

    return METHODOLOGY_DIR_MAP


def detect_category(source_path: Path) -> Dict[str, Any]:
    """从文件路径推断分类信息。"""
    try:
        relative = source_path.relative_to(KB_ROOT)
    except ValueError:
        return {"category": "unknown", "research_direction": None, "methodology": None}

    parts = list(relative.parts)

    category = "other"
    direction = None
    methodology = None

    for part in parts:
        if part in PAPER_DIR_NAMES:
            category = "paper"
            direction = part
        elif part in {"方法论资料类"}:
            category = "methodology"
        elif part in TEMPLATE_DIR_NAMES:
            category = "template"

    if category == "methodology":
        for part in parts:
            clean = re.sub(r"^\d+\.", "", part).strip()
            if clean and clean != "方法论资料类":
                methodology = clean
                break

    return {
        "category": category,
        "research_direction": direction,
        "methodology": methodology,
    }


def extract_title_and_abstract(text: str) -> Tuple[str, str]:
    """从转换后的 MD 文本提取标题和摘要。"""
    lines = text.splitlines()
    title = ""
    abstract_lines: List[str] = []
    in_abstract = False
    abstract_started = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if not title and stripped.startswith("# "):
            title = stripped[2:].strip()
            continue

        low = stripped.lower()
        if re.match(r"^(摘要|abstract|摘\s*要)", low):
            in_abstract = True
            abstract_started = True
            continue

        if in_abstract:
            if re.match(r"^(关键词|keywords|关键[词字]|第[一二三四五六七八九十]章|目录|目 录|#)", stripped):
                in_abstract = False
                continue
            if len(stripped) > 10:
                abstract_lines.append(stripped)

    if not title:
        for line in lines:
            stripped = line.strip()
            if stripped and len(stripped) > 5:
                title = stripped[:120]
                break

    abstract = " ".join(abstract_lines)[:500] if abstract_lines else ""

    return title or "未命名", abstract


def detect_methodologies_in_text(text: str) -> List[str]:
    """在论文文本中检测提到的方法论。"""
    catalog = _ensure_methodology_map()
    if not catalog:
        return []

    text_lower = text.lower()
    found: Set[str] = set()

    for raw_name, clean_name in catalog.items():
        if len(raw_name) < 2:
            continue
        if raw_name.lower() in text_lower or clean_name.lower() in text_lower:
            found.add(clean_name)

    from src.method_registry import get_method_keywords
    keywords_map = get_method_keywords()

    for method_name, patterns in keywords_map.items():
        for pattern in patterns:
            if pattern in text_lower:
                found.add(method_name)
                break

    return sorted(found)


def extract_outline(text: str) -> Dict[str, Any]:
    """提取论文的章节目录结构。"""
    chapters: List[Dict[str, Any]] = []
    current_chapter: Optional[Dict[str, Any]] = None
    current_section: Optional[Dict[str, Any]] = None
    heading_pattern = re.compile(r"^(#{1,4})\s+(.+)")

    for line in text.splitlines():
        stripped = line.strip()
        m = heading_pattern.match(stripped)
        if not m:
            continue

        level = len(m.group(1))
        heading = m.group(2).strip()

        if re.search(r"page\s+\d+|参考文献|references|致谢|acknowledg", heading, re.I):
            continue

        if level == 1:
            if current_chapter:
                chapters.append(current_chapter)
            current_chapter = {"title": heading, "level": 1, "sections": []}
            current_section = None
        elif level == 2:
            section = {"title": heading, "level": 2, "subsections": []}
            if current_chapter:
                current_chapter["sections"].append(section)
                current_section = section
        elif level in (3, 4):
            subsection = {"title": heading, "level": level}
            if current_section:
                current_section["subsections"].append(subsection)
            elif current_chapter:
                current_chapter["sections"].append({"title": heading, "level": level, "subsections": []})

    if current_chapter:
        chapters.append(current_chapter)

    chapter_count = len(chapters)
    section_count = sum(len(ch.get("sections", [])) for ch in chapters)

    return {
        "chapter_count": chapter_count,
        "section_count": section_count,
        "chapters": chapters[:30],
    }


def build_rich_metadata(source_path: Path, text: str) -> Dict[str, Any]:
    """构建富元数据：分类 + 标签 + 方法论 + 大纲。"""
    category_info = detect_category(source_path)
    title, abstract = extract_title_and_abstract(text)
    methodologies = detect_methodologies_in_text(text)
    outline = extract_outline(text)

    metadata = {
        **category_info,
        "title": title,
        "abstract": abstract,
        "methodologies": methodologies,
        "outline": outline,
        "language": "zh" if any("一" <= c <= "鿿" for c in text[:200]) else "en",
        "char_count": len(text),
    }

    if category_info["category"] == "paper" and category_info["research_direction"]:
        metadata["tags"] = [category_info["research_direction"]] + methodologies
    elif category_info["category"] == "methodology" and category_info["methodology"]:
        metadata["tags"] = [category_info["methodology"], "方法论"]
    elif category_info["category"] == "template":
        metadata["tags"] = ["模板", "格式规范"]

    return metadata


def categorize_output_dir(category_info: Dict[str, Any]) -> Path:
    """根据分类信息确定转换后 MD 文件的输出子目录。"""
    category = category_info.get("category", "other")
    if category == "paper":
        direction = category_info.get("research_direction") or "其他"
        return KB_CONVERTED_ROOT / "papers" / direction
    elif category == "methodology":
        method = category_info.get("methodology") or "其他"
        safe = re.sub(r"[^\w一-鿿-]", "_", method)[:40]
        return KB_CONVERTED_ROOT / "methodologies" / safe
    elif category == "template":
        return KB_CONVERTED_ROOT / "templates"
    else:
        return KB_CONVERTED_ROOT / "other"


def build_outline_index() -> Dict[str, Any]:
    """构建大纲索引 — 按研究方向分类存储论文目录结构。"""
    KB_OUTLINES_ROOT.mkdir(parents=True, exist_ok=True)

    direction_outlines: Dict[str, List[Dict[str, Any]]] = {}
    papers_dir = KB_CONVERTED_ROOT / "papers"

    if not papers_dir.exists():
        return {"outlines_root": str(KB_OUTLINES_ROOT), "directions": {}, "total": 0}

    for direction_dir in sorted(papers_dir.iterdir()):
        if not direction_dir.is_dir():
            continue
        direction = direction_dir.name
        entries: List[Dict[str, Any]] = []

        for md_file in sorted(direction_dir.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            title, _ = extract_title_and_abstract(text)
            outline = extract_outline(text)
            methodologies = detect_methodologies_in_text(text)

            entries.append({
                "file": str(md_file.relative_to(PROJECT_ROOT)),
                "title": title,
                "methodologies": methodologies,
                "outline": outline,
            })

        if entries:
            direction_outlines[direction] = entries

            outline_file = KB_OUTLINES_ROOT / direction / "outlines.json"
            outline_file.parent.mkdir(parents=True, exist_ok=True)
            outline_file.write_text(
                json.dumps(entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    catalog = {
        "outlines_root": str(KB_OUTLINES_ROOT.relative_to(PROJECT_ROOT)),
        "directions": {
            d: {"count": len(entries), "file": f"outlines/{d}/outlines.json"}
            for d, entries in direction_outlines.items()
        },
        "total": sum(len(e) for e in direction_outlines.values()),
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return catalog


def query_outlines_by_direction(direction: str) -> List[Dict[str, Any]]:
    """按研究方向查询大纲。"""
    outline_file = KB_OUTLINES_ROOT / direction / "outlines.json"
    if not outline_file.exists():
        return []
    try:
        return json.loads(outline_file.read_text(encoding="utf-8"))
    except Exception:
        return []


def load_catalog() -> Dict[str, Any]:
    """加载知识库目录。"""
    if not CATALOG_PATH.exists():
        return {"directions": {}, "total": 0}
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"directions": {}, "total": 0}
