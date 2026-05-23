"""Real literature hunter.

Finds real, externally verifiable academic works for the current thesis
context. The module intentionally does not ask an LLM to invent citations:
all returned metadata must come from public scholarly indexes.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
USER_AGENT = "ThesisMind/1.0 (mailto:admin@thesismind.local)"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokenize(text: str) -> Set[str]:
    tokens: Set[str] = set()
    for word in re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower()):
        if word not in {
            "the", "and", "for", "with", "from", "this", "that", "study",
            "research", "analysis", "model", "based", "using", "paper",
        }:
            tokens.add(word.strip("-"))
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]+", text)
    for chunk in cjk_chunks:
        for size in (2, 3, 4):
            for i in range(0, max(0, len(chunk) - size + 1)):
                token = chunk[i : i + size]
                if token not in {"研究", "分析", "方法", "问题", "基于", "本文"}:
                    tokens.add(token)
    return tokens


def _abstract_from_inverted_index(index: Any, max_words: int = 220) -> str:
    if not isinstance(index, dict):
        return ""
    positions: List[Tuple[int, str]] = []
    for word, pos_list in index.items():
        if not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            if isinstance(pos, int):
                positions.append((pos, str(word)))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions[:max_words])


def _authors_from_work(work: Dict[str, Any], max_authors: int = 5) -> List[str]:
    authors = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = _clean_text(author.get("display_name"))
        if name:
            authors.append(name)
        if len(authors) >= max_authors:
            break
    return authors


def _source_from_work(work: Dict[str, Any]) -> str:
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    name = _clean_text(source.get("display_name"))
    if name:
        return name
    host = work.get("host_venue") or {}
    return _clean_text(host.get("display_name"))


def _best_url(work: Dict[str, Any]) -> str:
    doi = _clean_text(work.get("doi"))
    if doi:
        return doi
    primary = work.get("primary_location") or {}
    landing = _clean_text(primary.get("landing_page_url"))
    if landing:
        return landing
    return _clean_text(work.get("id"))


_OPENALEX_TYPE_MARKER = {
    "journal-article": "[J]",
    "book": "[M]",
    "book-chapter": "[M]",
    "proceedings-article": "[C]",
    "dissertation": "[D]",
    "standard": "[S]",
    "report": "[R]",
    "patent": "[P]",
    "other": "[J]",
}


def _format_gbt7714(work: Dict[str, Any]) -> str:
    authors = _authors_from_work(work, max_authors=3)
    author_text = ", ".join(authors) if authors else "Unknown"
    if len(work.get("authorships") or []) > 3:
        author_text += ", et al"
    title = _clean_text(work.get("display_name"))
    year = str(work.get("publication_year") or "").strip()
    venue = _source_from_work(work)
    doi = _clean_text(work.get("doi"))
    tail = f" DOI: {doi}." if doi else ""
    marker = _OPENALEX_TYPE_MARKER.get(work.get("type", ""), "[J]")
    if venue:
        return f"{author_text}. {title}{marker}. {venue}, {year}.{tail}".strip()
    return f"{author_text}. {title}{marker}. {year}.{tail}".strip()


def _build_queries(payload: Dict[str, Any], limit: int = 6) -> List[str]:
    topic = _clean_text(payload.get("topic"))
    direction_name = _clean_text(payload.get("direction_name") or payload.get("direction"))
    methods = [_clean_text(m) for m in payload.get("methods") or [] if _clean_text(m)]
    project_context = _clean_text(payload.get("project_context"))[:900]
    section_title = _clean_text(payload.get("section_title"))

    base_parts = [p for p in [topic, direction_name] if p]
    queries: List[str] = []
    if base_parts:
        queries.append(" ".join(base_parts))
        queries.append(" ".join(base_parts + ["project management"]))
    # Section-specific queries to diversify results per subsection
    if section_title:
        queries.insert(0, " ".join([section_title] + base_parts))
        queries.append(section_title)
    if project_context:
        terms = list(_tokenize(project_context))
        queries.append(" ".join(base_parts + terms[:8]))
    for method in methods[:4]:
        queries.append(" ".join([p for p in [topic, direction_name, method] if p]))
        queries.append(f"{method} project management empirical study")

    cleaned: List[str] = []
    seen = set()
    for query in queries:
        q = _clean_text(query)
        if len(q) < 3:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(q[:240])
        if len(cleaned) >= limit:
            break
    return cleaned or ["project management empirical study"]


def _openalex_search(query: str, per_page: int = 12, timeout: int = 12) -> List[Dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "search": query,
            "per-page": max(1, min(per_page, 25)),
        }
    )
    req = urllib.request.Request(
        f"{OPENALEX_WORKS_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []
    results = data.get("results")
    return results if isinstance(results, list) else []


def _score_work(
    work: Dict[str, Any],
    context_tokens: Set[str],
    method_tokens: Set[str],
    current_year: int,
) -> Tuple[float, str]:
    title = _clean_text(work.get("display_name"))
    abstract = _abstract_from_inverted_index(work.get("abstract_inverted_index"))
    concepts = " ".join(
        _clean_text(c.get("display_name"))
        for c in work.get("concepts") or []
        if isinstance(c, dict)
    )
    haystack = f"{title} {abstract} {concepts}"
    work_tokens = _tokenize(haystack)
    if not title or not work_tokens:
        return 0.0, "缺少标题或摘要信息"

    overlap = len(context_tokens & work_tokens)
    topic_score = min(45.0, overlap * 4.5)
    method_overlap = len(method_tokens & work_tokens)
    method_score = min(20.0, method_overlap * 6.0)
    cited_by = int(work.get("cited_by_count") or 0)
    authority_score = min(20.0, math.log10(cited_by + 1) * 8.0)
    year = int(work.get("publication_year") or 0)
    if year >= current_year - 5:
        recency_score = 15.0
    elif year >= current_year - 10:
        recency_score = 10.0
    elif cited_by >= 200:
        recency_score = 8.0
    else:
        recency_score = 4.0

    score = topic_score + method_score + authority_score + recency_score
    reasons = []
    if overlap:
        reasons.append(f"主题命中 {overlap} 个关键词")
    if method_overlap:
        reasons.append(f"方法相关命中 {method_overlap} 个关键词")
    if cited_by:
        reasons.append(f"OpenAlex 被引 {cited_by} 次")
    if year:
        reasons.append(f"出版年份 {year}")
    return round(score, 1), "；".join(reasons) or "与当前论文主题有一定相关性"


def hunt_real_literature(
    payload: Dict[str, Any],
    limit: int = 5,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Search public scholarly indexes and return 3-5 real citations."""
    limit = max(3, min(5, int(limit or 5)))
    topic = _clean_text(payload.get("topic"))
    direction = _clean_text(payload.get("direction_name") or payload.get("direction"))
    methods = [_clean_text(m) for m in payload.get("methods") or [] if _clean_text(m)]
    project_context = _clean_text(payload.get("project_context"))
    context_text = " ".join([topic, direction, project_context, " ".join(methods)])
    context_tokens = _tokenize(context_text)
    method_tokens = _tokenize(" ".join(methods))
    queries = _build_queries(payload)

    if log:
        log(f"真实文献猎手：生成 {len(queries)} 个检索式")

    candidates: Dict[str, Dict[str, Any]] = {}
    query_errors = 0
    for index, query in enumerate(queries, 1):
        if log:
            log(f"检索 OpenAlex {index}/{len(queries)}：{query}")
        works = _openalex_search(query, per_page=12)
        if not works:
            query_errors += 1
            continue
        for work in works:
            title = _clean_text(work.get("display_name"))
            openalex_id = _clean_text(work.get("id"))
            doi = _clean_text(work.get("doi"))
            if not title or not openalex_id:
                continue
            key = (doi or openalex_id or title).lower()
            if key in candidates:
                continue
            if not (doi or openalex_id or _best_url(work)):
                continue
            candidates[key] = work

    current_year = time.localtime().tm_year
    scored = []
    for work in candidates.values():
        score, why = _score_work(work, context_tokens, method_tokens, current_year)
        if score <= 0:
            continue
        scored.append((score, why, work))
    scored.sort(key=lambda item: item[0], reverse=True)

    citations: List[Dict[str, Any]] = []
    seen_titles = set()
    for score, why, work in scored:
        title = _clean_text(work.get("display_name"))
        norm_title = re.sub(r"\W+", "", title.lower())
        if not norm_title or norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)
        doi = _clean_text(work.get("doi"))
        openalex_id = _clean_text(work.get("id"))
        url = _best_url(work)
        authors = _authors_from_work(work, max_authors=8)
        year = str(work.get("publication_year") or "")
        cited_by = int(work.get("cited_by_count") or 0)
        venue = _source_from_work(work)
        citation_id = uuid.uuid5(uuid.NAMESPACE_URL, doi or openalex_id or title).hex
        citations.append(
            {
                "id": citation_id,
                "card_id": citation_id,
                "title": title,
                "authors": ", ".join(authors),
                "year": year,
                "language": "en",
                "type": "期刊文章",
                "venue": venue,
                "doi": doi,
                "url": url,
                "openalex_id": openalex_id,
                "cited_by_count": cited_by,
                "relevance_score": score,
                "formatted": _format_gbt7714(work),
                "directions": [direction] if direction else [],
                "methods": methods,
                "reason": why,
                "source_path": url,
                "source": "real_literature_hunter",
                "verify_status": "OpenAlex 可验证",
            }
        )
        if len(citations) >= limit:
            break

    status = "found" if citations else "not_found"
    message = (
        f"真实文献猎手找到 {len(citations)} 篇可验证文献"
        if citations
        else "暂未找到足够相关且可验证的真实文献"
    )
    return {
        "status": status,
        "message": message,
        "citations": citations,
        "queries": queries,
        "candidate_count": len(candidates),
        "query_errors": query_errors,
        "source": "OpenAlex",
    }
