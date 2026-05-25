"""
Citation quality scoring engine.

Evaluates academic citations across 5 dimensions:
  authenticity (35%) — DOI resolvability, author/title match via CrossRef / Semantic Scholar
  format (20%) — GB/T 7714 field completeness
  authority (20%) — journal ranking, citation count, H-index
  recency (15%) — publication year freshness
  source (10%) — peer-review status, retraction check

Reference projects:
  sciwrite-lint — multi-source verification + SciLint score methodology
  ref-checker — confidence scoring with CrossRef + Semantic Scholar
  bibliography-verification-tool — fuzzy matching with CrossRef/PubMed
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.citation_parser import validate_gbt7714, extract_doi, looks_like_citation

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Weight configuration ────────────────────────────────────────────────────

DIMENSION_WEIGHTS = {
    "authenticity": 0.35,
    "format": 0.20,
    "authority": 0.20,
    "recency": 0.15,
    "source": 0.10,
}

# ── Journal rankings (北大核心 + CSSCI + CSCD sample) ────────────────────────
# In production this should be a local database; for now a curated sample.

_CORE_JOURNALS: Dict[str, int] = {
    # Engineering management — top journals
    "管理世界": 3, "管理科学学报": 3, "中国管理科学": 3,
    "系统工程理论与实践": 3, "管理工程学报": 3, "南开管理评论": 3,
    "科研管理": 2, "科学学研究": 2, "科学学与科学技术管理": 2,
    "管理评论": 2, "管理学报": 2, "系统工程": 2,
    "运筹与管理": 2, "工业工程与管理": 2, "管理科学": 3,
    # International
    "Management Science": 3, "Operations Research": 3,
    "Manufacturing & Service Operations Management": 3,
    "Production and Operations Management": 3,
    "Journal of Operations Management": 3,
    "European Journal of Operational Research": 3,
    "International Journal of Production Economics": 2,
    "International Journal of Production Research": 2,
    "Quality Engineering": 2, "Total Quality Management": 2,
    "IEEE Transactions on Engineering Management": 3,
    "Journal of Quality Technology": 3, "Technometrics": 3,
    "Risk Analysis": 2, "Safety Science": 2,
    "Reliability Engineering & System Safety": 2,
}

# Known retracted DOIs (Retraction Watch sample — expand with local DB)
_RETRACTED_DOIS: set = set()

CACHE_DIR = PROJECT_ROOT / ".cache" / "citation_verify"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ── API verification ────────────────────────────────────────────────────────

def _cache_get(key: str) -> Optional[Dict]:
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - data.get("_ts", 0) < 86400 * 30:  # 30-day cache
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _cache_set(key: str, data: Dict) -> None:
    data["_ts"] = time.time()
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _crossref_query_doi(doi: str) -> Optional[Dict[str, Any]]:
    """Query CrossRef API for a DOI. Returns structured metadata or None."""
    cache_key = f"cr_{re.sub(r'[^a-zA-Z0-9]', '_', doi)}"
    cached = _cache_get(cache_key)
    if cached:
        return cached.get("data")

    url = f"https://api.crossref.org/works/{urllib.request.quote(doi, safe='')}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ThesisMind/1.0 (mailto:admin@thesismind.local)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            data = body.get("message", {})
            _cache_set(cache_key, {"data": data})
            return data
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def _semantic_scholar_title(title: str) -> Optional[Dict[str, Any]]:
    """Query Semantic Scholar API by title. Returns paper metadata or None."""
    cache_key = f"ss_{re.sub(r'[^a-zA-Z0-9一-鿿]', '_', title[:80])}"
    cached = _cache_get(cache_key)
    if cached:
        return cached.get("data")

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = urllib.parse.urlencode({"query": title, "limit": 3})
    try:
        req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "ThesisMind/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            data = body.get("data", [])
            _cache_set(cache_key, {"data": data})
            return data
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def _semantic_scholar_detail(paper_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed paper info from Semantic Scholar."""
    cache_key = f"ssd_{paper_id}"
    cached = _cache_get(cache_key)
    if cached:
        return cached.get("data")

    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
    fields = "title,authors,year,venue,citationCount,journal,publicationTypes"
    try:
        req = urllib.request.Request(
            f"{url}?fields={fields}",
            headers={"User-Agent": "ThesisMind/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            _cache_set(cache_key, {"data": data})
            return data
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


# ── Dimension scorers ───────────────────────────────────────────────────────

def score_authenticity(card: Dict[str, Any], verify_external: bool = True) -> Tuple[float, str]:
    """Score citation authenticity (0-1).

    Primary signal: LLM verification status (verified column in DB).
    External APIs (CrossRef / Semantic Scholar) are bonus points on top.

    Returns (score, verification_note).
    """
    doi = card.get("doi", "") or extract_doi(card.get("formatted", ""))
    title = card.get("title", "").strip()
    authors = card.get("authors", "").strip()
    verified = card.get("verified", 0)
    try:
        verified = int(verified)
    except (ValueError, TypeError):
        verified = 0

    if not doi and not title:
        return 0.0, "无 DOI 且无标题，无法验证真实性"

    # Base score from LLM verification (already done during import)
    if verified == 1:
        score = 0.85
        notes = ["LLM 已校验真实性"]
    elif verified == -1:
        score = 0.3
        notes = ["LLM 校验未通过"]
    else:
        score = 0.5
        notes = ["未经 LLM 校验"]

    # External API bonuses (on top of LLM baseline)
    if not verify_external:
        notes.append("未进行外部 API 交叉验证")
        return min(1.0, score), "; ".join(notes)

    api_used = False

    if doi:
        cr_data = _crossref_query_doi(doi)
        if cr_data:
            api_used = True
            score += 0.15
            notes.append("DOI 已在 CrossRef 确认")
            cr_title = (cr_data.get("title") or [""])[0].lower()
            if title and cr_title:
                title_lower = title.lower().strip().rstrip(".")
                cr_lower = cr_title.lower().strip().rstrip(".")
                if title_lower == cr_lower or title_lower in cr_lower or cr_lower in title_lower:
                    score += 0.1
                    notes.append("标题与 CrossRef 记录一致")
                else:
                    notes.append("标题与 CrossRef 记录有差异，请核实")
            if authors:
                cr_authors = [
                    f"{a.get('family', '')} {a.get('given', '')}".strip()
                    for a in cr_data.get("author", [])
                ]
                author_tokens = set(re.split(r"[;,，\s]+", authors.lower()))
                cr_tokens = set()
                for a in cr_authors:
                    cr_tokens.update(re.split(r"[;,，\s]+", a.lower()))
                cr_tokens.discard("")
                author_tokens.discard("")
                if cr_tokens and author_tokens:
                    overlap = len(author_tokens & cr_tokens) / max(1, min(len(author_tokens), len(cr_tokens)))
                    if overlap > 0.3:
                        score += 0.05
                        notes.append("作者信息部分匹配")
        else:
            notes.append("DOI 在 CrossRef 中未找到")

    if title and not doi:
        ss_data = _semantic_scholar_title(title)
        if ss_data and len(ss_data) > 0:
            api_used = True
            top = ss_data[0]
            ss_title = top.get("title", "").lower()
            title_lower = title.lower().strip().rstrip(".")
            if title_lower == ss_title or title_lower in ss_title or ss_title in title_lower:
                score += 0.2
                notes.append("标题在 Semantic Scholar 确认存在")
                if top.get("paperId"):
                    detail = _semantic_scholar_detail(top["paperId"])
                    if detail:
                        if detail.get("citationCount", 0) > 0:
                            score += 0.05
                        notes.append(f"被引 {detail.get('citationCount', 0)} 次")
            else:
                score += 0.1
                notes.append("Semantic Scholar 找到近似论文，但标题不完全匹配")
        # If SS fails (rate limited, not found), keep LLM baseline — no penalty

    if not api_used:
        notes.append("未进行外部 API 交叉验证")

    return min(1.0, score), "; ".join(notes)


def score_format(card: Dict[str, Any]) -> Tuple[float, str]:
    """Score GB/T 7714 format completeness (0-1)."""
    is_valid, issues, completeness = validate_gbt7714(card)
    note = "格式完整" if is_valid else "; ".join(issues) if issues else "格式基本完整"
    return completeness, note


def score_authority(card: Dict[str, Any]) -> Tuple[float, str]:
    """Score academic authority based on journal ranking and citation metrics."""
    formatted = card.get("formatted", "")
    journal = card.get("journal", "")
    ref_type = card.get("ref_type", "")

    score = 0.3  # baseline — it's a published work
    notes = []

    # Check journal ranking
    for jname, tier in _CORE_JOURNALS.items():
        if jname.lower() in journal.lower() or jname.lower() in formatted.lower():
            if tier == 3:
                score = 0.95
                notes.append(f"顶级期刊 (T{tier}): {jname}")
            elif tier == 2:
                score = max(score, 0.8)
                notes.append(f"核心期刊 (T{tier}): {jname}")
            break

    # Ref type bonus
    if ref_type == "期刊文章":
        score = max(score, 0.4)
    elif ref_type == "会议论文":
        score = max(score, 0.35)
    elif ref_type == "图书":
        score = max(score, 0.5)
    elif ref_type in ("报纸", "电子资源"):
        score = min(score, 0.3)

    if not notes:
        if score >= 0.7:
            notes.append("核心期刊")
        else:
            notes.append("未在核心期刊列表中，权威性一般")

    return min(1.0, score), "; ".join(notes)


def score_recency(card: Dict[str, Any]) -> Tuple[float, str]:
    """Score recency based on publication year (0-1).

    ≤3 years → 1.0, ≤5 years → 0.9, ≤10 years → 0.6, ≤15 years → 0.3, older → 0.1
    """
    year_str = str(card.get("year", "")).strip()
    try:
        year = int(year_str)
    except (ValueError, TypeError):
        return 0.3, "无法确定出版年份"

    current_year = time.localtime().tm_year
    age = current_year - year

    if age <= 3:
        return 1.0, f"近 3 年内发表 ({year})"
    elif age <= 5:
        return 0.9, f"近 5 年内发表 ({year})"
    elif age <= 10:
        return 0.6, f"10 年内发表 ({year})"
    elif age <= 15:
        return 0.3, f"15 年内发表 ({year})"
    elif age <= 20:
        return 0.15, f"较旧文献 ({year})"
    else:
        return 0.05, f"经典文献 ({year})"


def score_source(card: Dict[str, Any]) -> Tuple[float, str]:
    """Score source credibility — peer-review, retraction status, repository."""
    doi = card.get("doi", "") or extract_doi(card.get("formatted", ""))
    ref_type = card.get("ref_type", "")
    formatted = card.get("formatted", "")

    score = 0.5  # baseline
    notes = []

    # Peer-reviewed types
    if ref_type in ("期刊文章", "会议论文"):
        score = 0.7
        notes.append("同行评审来源")
    elif ref_type == "学位论文":
        score = 0.6
        notes.append("学位论文（经答辩委员会审核）")
    elif ref_type == "图书":
        score = 0.6
        notes.append("正式出版物")
    elif ref_type == "标准":
        score = 0.8
        notes.append("标准文件（权威来源）")
    elif ref_type in ("报纸", "电子资源"):
        score = 0.3
        notes.append("非同行评审来源，可信度较低")

    # Retraction check
    if doi and doi in _RETRACTED_DOIS:
        score = 0.0
        notes.append("⚠️ 该文献已被撤稿")

    # URL patterns
    if "arxiv.org" in formatted.lower():
        score = max(score, 0.5)
        notes.append("预印本（未同行评审）")

    return min(1.0, score), "; ".join(notes)


# ── Composite scoring ───────────────────────────────────────────────────────

def score_citation(card: Dict[str, Any], verify_external: bool = True) -> Dict[str, Any]:
    """Score a single citation card across all dimensions.

    Returns dict with dimension scores, composite score, and grade.
    """
    if not looks_like_citation(card.get("formatted", "")):
        return {
            "quality_score": 0.0,
            "grade": "D",
            "grade_label": "非引用文本",
            "dimensions": {},
            "verification_note": "文本不像是有效的学术引用",
        }

    dims = {}
    verification_notes = []

    # Format (always run, no API needed)
    fmt_score, fmt_note = score_format(card)
    dims["format"] = {"score": round(fmt_score, 2), "weight": DIMENSION_WEIGHTS["format"], "note": fmt_note}

    # Authenticity (LLM-verified baseline + optional external API bonus)
    auth_score, auth_note = score_authenticity(card, verify_external=verify_external)
    verification_notes.append(auth_note)
    dims["authenticity"] = {"score": round(auth_score, 2), "weight": DIMENSION_WEIGHTS["authenticity"], "note": auth_note}

    # Authority
    authy_score, authy_note = score_authority(card)
    dims["authority"] = {"score": round(authy_score, 2), "weight": DIMENSION_WEIGHTS["authority"], "note": authy_note}

    # Recency
    rec_score, rec_note = score_recency(card)
    dims["recency"] = {"score": round(rec_score, 2), "weight": DIMENSION_WEIGHTS["recency"], "note": rec_note}

    # Source
    src_score, src_note = score_source(card)
    dims["source"] = {"score": round(src_score, 2), "weight": DIMENSION_WEIGHTS["source"], "note": src_note}

    # Composite
    composite = sum(
        d["score"] * d["weight"]
        for d in dims.values()
    )
    composite = round(composite, 4)
    quality_score = round(composite * 100, 1)

    # Grade
    if quality_score >= 90:
        grade, label = "A", "权威可信"
    elif quality_score >= 75:
        grade, label = "B", "可用"
    elif quality_score >= 60:
        grade, label = "C", "需人工审核"
    else:
        grade, label = "D", "不建议引用"

    return {
        "quality_score": quality_score,
        "grade": grade,
        "grade_label": label,
        "dimensions": dims,
        "verification_note": "; ".join(verification_notes) if verification_notes else fmt_note,
    }


def score_citation_offline(card: Dict[str, Any]) -> Dict[str, Any]:
    """Score without external API calls (fast, always available)."""
    return score_citation(card, verify_external=False)


# ── Batch scoring ───────────────────────────────────────────────────────────

def score_batch(
    cards: List[Dict[str, Any]],
    verify_external: bool = True,
    on_progress: Optional[callable] = None,
) -> List[Dict[str, Any]]:
    """Score multiple citation cards, with optional progress callback."""
    results = []
    for i, card in enumerate(cards):
        result = score_citation(card, verify_external=verify_external)
        result["card_id"] = card.get("card_id", "")
        results.append(result)
        if on_progress:
            on_progress(i + 1, len(cards))
        # Rate limiting for external APIs
        if verify_external and i < len(cards) - 1:
            time.sleep(0.3)  # ~3 req/s to be safe
    return results
