"""
Citation parser — multi-format citation parsing and GB/T 7714 validation.

Supports: GB/T 7714, APA, MLA, Chicago, IEEE, BibTeX extraction.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# ── GB/T 7714-2015 format patterns ──────────────────────────────────────────

# Type markers in GB/T 7714
_TYPE_MARKERS: Dict[str, str] = {
    "[J]": "期刊文章",
    "[M]": "图书",
    "[C]": "会议论文",
    "[D]": "学位论文",
    "[S]": "标准",
    "[R]": "报告",
    "[P]": "专利",
    "[N]": "报纸",
    "[EB/OL]": "电子资源",
    "[EB]": "电子资源",
}

# Required fields per GB/T 7714 ref_type
_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "期刊文章": ["authors", "title", "year", "journal"],
    "图书": ["authors", "title", "year", "publisher"],
    "会议论文": ["authors", "title", "year", "proceedings"],
    "学位论文": ["authors", "title", "year", "institution"],
    "标准": ["authors", "title", "year", "publisher"],
    "报告": ["authors", "title", "year", "institution"],
    "专利": ["authors", "title", "year", "patent_number"],
    "报纸": ["authors", "title", "year", "newspaper"],
    "电子资源": ["authors", "title", "year", "url"],
    "其他": ["authors", "title", "year"],
}

# GB/T 7714 field extraction patterns
_GB_AUTHORS_RE = re.compile(
    r"^([^\d\.\[\]]+?)(?:\.|，|,)"
    r"\s*(.+?)(?:\[[JMCDSRPNAEB]|\[EB/OL\]?|\.\s*[A-Z])",
)
_GB_YEAR_RE = re.compile(r"(\d{4})")
_GB_DOI_RE = re.compile(r"DOI[:\s]*(\S+)", re.IGNORECASE)

# APA patterns
_APA_AUTHOR_RE = re.compile(
    r"^([A-Z][a-z]+(?:\s+[A-Z]\.)*)\s*\((\d{4})\)"
)
_APA_TITLE_RE = re.compile(r"\)\.\s*(.+?)\.(?:\s*[A-Z][a-z]+)")

# Common fields that suggest a citation is real
_CITATION_INDICATORS = [
    # GB/T 7714 type markers
    "[J]", "[M]", "[C]", "[D]", "[S]", "[R]", "[P]", "[N]",
    "[EB/OL]", "[EB]", "[A]", "[Z]",
    # Publishing keywords
    "出版社", "出版", "Press", "Publishing",
    "期刊", "Journal", "学报",
    "会议", "Conference", "Proceedings",
    "大学", "University", "College",
    "硕士", "博士", "学位", "Dissertation", "Thesis",
    "卷", "Vol", "vol",
    "页码", "pp", "PP",
    "DOI", "doi",
    "ISBN", "ISSN",
    # Chinese academic terms
    "有限公司", "统计局", "研究所", "研究院",
    # English journal indicators
    "IEEE", "ACM", "Springer", "Elsevier", "Wiley",
]

# Patterns that strongly suggest text is a citation
_CITATION_PATTERNS = [
    r"\[\d+\]\s*\S",              # [1] Author...
    r"\[\s*[JMCDSRPNA]\s*\]",     # [J], [M], etc. type markers
    r"\d{4}[,，]\s*\d+[\(（]\d+[\)）]",  # 2019, 46(01)
    r"\d{4}[,，]\s*\d+\(\d+\)",   # 2019, 46(01) ASCII parens
    r"[：:]\s*\d+[-–]\d+",        # : 21-28 (pages)
    r"[Jj]ournal\s+of",           # Journal of ...
    r"\bVol\.?\s*\d+",           # Vol. 46
    r"\bpp?\.?\s*\d+",           # pp. 21-28
]

# Fields that suggest text is NOT a citation
_NON_CITATION_PATTERNS = [
    r"^(第[一二三四五六七八九十\d]+章)",  # chapter headers
    r"^(摘要|Abstract|关键词|Keywords|引言|绪论|绪论|结论|Conclusion)",
    r"^(https?://)",  # raw URLs
    r"^[A-Z][a-z]+\s+\d{1,2},\s+\d{4}$",  # dates like "January 1, 2024"
]


# ── Public API ──────────────────────────────────────────────────────────────

def looks_like_citation(text: str) -> bool:
    """Quick pre-check: does this text look like a citation reference?"""
    text = text.strip()
    if len(text) < 15:
        return False
    for pat in _NON_CITATION_PATTERNS:
        if re.match(pat, text):
            return False
    # Check keyword indicators (case-insensitive)
    indicators_found = sum(1 for ind in _CITATION_INDICATORS if ind.lower() in text.lower())
    if indicators_found >= 1:
        return True
    # Check pattern-based indicators
    for pat in _CITATION_PATTERNS:
        if re.search(pat, text):
            return True
    return False


def detect_ref_type(text: str) -> str:
    """Detect GB/T 7714 reference type from text markers."""
    # Check for type markers in brackets
    for marker, ref_type in sorted(_TYPE_MARKERS.items(), key=lambda x: -len(x[0])):
        if marker in text:
            return ref_type
    # Heuristic detection
    if any(kw in text for kw in ["[J]", "Journal", "期刊", "学报"]):
        return "期刊文章"
    if any(kw in text for kw in ["[M]", "出版社", "Press", "出版"]):
        return "图书"
    if any(kw in text for kw in ["[C]", "Conference", "会议", "Proceedings"]):
        return "会议论文"
    if any(kw in text for kw in ["[D]", "硕士", "博士", "学位", "Dissertation", "Thesis"]):
        return "学位论文"
    if any(kw in text for kw in ["[S]", "标准"]):
        return "标准"
    if any(kw in text for kw in ["[P]", "专利"]):
        return "专利"
    if any(kw in text for kw in ["[EB/OL]", "[EB]", "http"]):
        return "电子资源"
    if any(kw in text for kw in ["[N]", "报纸"]):
        return "报纸"
    return "其他"


def extract_year(text: str) -> str:
    """Extract publication year from citation text."""
    # Try to find a year that looks like a publication year
    matches = _GB_YEAR_RE.findall(text)
    if not matches:
        return ""
    # Filter: publication years are usually 1900-2030
    valid = [y for y in matches if 1900 <= int(y) <= 2030]
    if valid:
        return valid[0]
    return matches[0]


def extract_authors(text: str) -> str:
    """Extract authors from citation text using heuristics."""
    # GB/T 7714: authors come first, before the title
    # Try to split at common delimiters
    for delim in [".[J]", ".[M]", ".[C]", ".[D]", ".[S]", ".[R]", ".[P]", ".[N]",
                   ".[EB/OL]", ".[EB]", "[J]", "[M]", "[C]", "[D]", "[EB/OL]", "[EB]"]:
        if delim in text:
            prefix = text.split(delim)[0].strip()
            # Remove leading number like "[1]"
            prefix = re.sub(r"^\[\d+\]\s*", "", prefix)
            # Remove trailing period
            prefix = prefix.rstrip(".")
            if len(prefix) >= 2:
                return prefix
    return ""


def extract_doi(text: str) -> str:
    """Extract DOI from citation text."""
    m = _GB_DOI_RE.search(text)
    if m:
        return m.group(1)
    return ""


def validate_gbt7714(card: Dict[str, Any]) -> Tuple[bool, List[str], float]:
    """Validate a citation card against GB/T 7714-2015 completeness rules.

    Falls back to formatted text inspection when structured fields are empty.
    Returns (is_valid, issues, completeness_score).
    """
    ref_type = card.get("ref_type", "其他")
    formatted = card.get("formatted", "")
    required = _REQUIRED_FIELDS.get(ref_type, _REQUIRED_FIELDS["其他"])
    issues = []
    missing = []

    for field in required:
        value = str(card.get(field, "")).strip()
        if not value:
            # Fallback: try to detect from formatted text
            detected = _detect_field_in_formatted(formatted, field, ref_type)
            if not detected:
                missing.append(field)

    if missing:
        issues.append(f"缺少必填字段: {', '.join(missing)}")

    # Year format check
    year = str(card.get("year", "") or extract_year(formatted))
    if year:
        try:
            y = int(year)
            if y < 1900 or y > 2030:
                issues.append(f"年份 {year} 不在合理范围 (1900-2030)")
        except ValueError:
            issues.append(f"年份格式错误: {year}")

    # Authors check (from formatted if structured field empty)
    authors = str(card.get("authors", "")).strip()
    if not authors:
        authors = extract_authors(formatted)
    if authors and len(authors) < 2:
        issues.append("作者名过短，可能不完整")

    # Title check
    title = str(card.get("title", "")).strip()
    if title and len(title) < 3:
        issues.append("题名过短，可能不完整")

    completeness = max(0.0, 1.0 - (len(missing) / max(1, len(required))))
    return len(issues) == 0, issues, completeness


def _detect_field_in_formatted(formatted: str, field: str, ref_type: str = "") -> bool:
    """Try to detect if a required field is present in the formatted citation text."""
    if not formatted:
        return False

    if field == "authors":
        # Authors typically appear at the beginning, before title or type marker
        # Check: starts with Chinese names (2-4 chars + punctuation) or English names
        return bool(
            extract_authors(formatted) or
            re.match(r"^\[\d+\]\s*\S{2,10}[,，\.]", formatted) or
            re.match(r"^\S{2,20}\s+[A-Z]\.", formatted) or  # English author pattern
            re.match(r"^[一-鿿]{2,20}[\.。]", formatted)  # Chinese name/org before .
        )

    if field == "journal":
        # Journal name usually appears after [J] marker or before year/volume
        return bool(
            re.search(r"\[J\][\.。，]?\s*(\S.{2,50}?),", formatted) or
            re.search(r"[Jj]ournal\s+of\s+\S+", formatted)
        )

    if field == "publisher":
        # Publisher: after [M] or "出版" or press/publishing house
        return bool(
            re.search(r"(?:出版社|出版|Press|Publishing|Publishers)", formatted)
        )

    if field == "institution":
        # Institution: after [D] (thesis) or "大学"/"学院"
        return bool(
            re.search(r"\[D\][\.。，]?\s*(.{2,40}?),", formatted) or
            re.search(r"(?:大学|学院|研究院|研究所)", formatted)
        )

    if field == "proceedings":
        # Conference proceedings: after [C] marker
        return bool(
            re.search(r"\[C\][\.。，]?\s*//?\s*(.{2,60}?),", formatted) or
            re.search(r"(?:Proceedings|Conference|国际会议|学术会议|年会)", formatted)
        )

    if field == "patent_number":
        return bool(re.search(r"(?:专利号|Patent\s*(?:No|Number))", formatted, re.IGNORECASE))

    if field == "newspaper":
        return bool(re.search(r"\[N\][\.。，]?", formatted) or re.search(r"(?:日报|晚报|晨报|时报|新闻)", formatted))

    if field == "title":
        # Title appears after authors and before [type marker]
        # GB/T 7714 pattern: after ". " and before "[J]" or "[M]" etc.
        return bool(
            re.search(r"[\.。]\s*\S.{3,100}?\s*\[", formatted) or
            len(formatted.strip()) > 10  # any reasonable citation has text
        )

    if field == "year":
        return bool(extract_year(formatted))

    if field == "url":
        return bool(re.search(r"https?://", formatted))

    return False


def compute_completeness_score(card: Dict[str, Any]) -> float:
    """Compute field completeness score (0.0-1.0)."""
    ref_type = card.get("ref_type", "其他")
    required = _REQUIRED_FIELDS.get(ref_type, _REQUIRED_FIELDS["其他"])

    filled = 0
    for field in required:
        value = card.get(field, "")
        if str(value).strip():
            filled += 1

    # Bonus fields
    bonus_fields = ["doi", "issn", "pages", "volume", "issue"]
    bonus_filled = sum(1 for f in bonus_fields if str(card.get(f, "")).strip())

    base = filled / max(1, len(required))
    bonus = min(0.1, bonus_filled * 0.02)
    return min(1.0, base + bonus)


def build_parse_result(
    raw_text: str,
    parsed: Dict[str, Any],
    validation: Optional[Tuple[bool, List[str], float]] = None,
) -> Dict[str, Any]:
    """Build a structured parse result for frontend display."""
    if validation is None:
        valid, issues, completeness = validate_gbt7714(parsed)
    else:
        valid, issues, completeness = validation

    is_citation = looks_like_citation(raw_text)
    doi = parsed.get("doi", "") or extract_doi(raw_text)
    detected_type = parsed.get("ref_type") or detect_ref_type(raw_text)

    return {
        "raw_text": raw_text[:500],
        "parsed": {
            "formatted": parsed.get("formatted", raw_text.strip()),
            "title": parsed.get("title", ""),
            "authors": parsed.get("authors", ""),
            "year": parsed.get("year", ""),
            "ref_type": detected_type,
            "language": parsed.get("language", "zh"),
            "journal": parsed.get("journal", ""),
            "publisher": parsed.get("publisher", ""),
            "doi": doi,
            "pages": parsed.get("pages", ""),
            "volume": parsed.get("volume", ""),
            "issue": parsed.get("issue", ""),
        },
        "validation": {
            "is_valid": valid,
            "is_citation": is_citation,
            "issues": issues,
            "completeness": round(completeness, 2),
            "ref_type": detected_type,
            "has_doi": bool(doi),
        },
    }


def build_llm_parse_prompt(blocks: List[str]) -> str:
    """Build the LLM prompt for parsing citation blocks."""
    numbered = "\n\n".join(f"[{i+1}] {b}" for i, b in enumerate(blocks))
    return (
        f"你是学术引用解析专家。请解析以下参考文献，提取结构化字段。\n\n"
        f"每条引用的字段：\n"
        f"- formatted: 完整的格式化引用文本（保留原始格式）\n"
        f"- title: 文献题名\n"
        f"- authors: 作者（多个用分号分隔）\n"
        f"- year: 出版年份（如 \"2024\"）\n"
        f"- ref_type: 期刊文章/学位论文/会议论文/图书/标准/报告/专利/报纸/电子资源/其他\n"
        f"- language: zh（中文）或 en（英文）\n"
        f"- journal: 期刊名（期刊文章必填）\n"
        f"- publisher: 出版社（图书必填）\n"
        f"- institution: 授予单位（学位论文必填）\n"
        f"- doi: DOI 编号（如有）\n"
        f"- pages: 页码（如有）\n"
        f"- volume: 卷号（如有）\n"
        f"- issue: 期号（如有）\n\n"
        f"规则：\n"
        f"1. 支持 GB/T 7714、APA、MLA、Chicago、IEEE 等任何引用格式\n"
        f"2. 无法确定的字段留空字符串\n"
        f"3. 如果文本不是参考文献，所有字段留空\n"
        f"4. 有多条的用空行分隔输入，输出为JSON数组\n\n"
        f"参考文献文本：\n{numbered}\n\n"
        f"只输出JSON数组（不要markdown代码块）：\n"
        f'[{{"formatted": "...", "title": "...", "authors": "...", "year": "...", '
        f'"ref_type": "期刊文章", "language": "zh", "journal": "...", '
        f'"publisher": "", "institution": "", "doi": "", "pages": "", "volume": "", "issue": ""}}]'
    )
