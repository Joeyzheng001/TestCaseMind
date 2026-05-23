"""
Citation relevance / fitness scoring engine.

Scores how well a citation matches a specific chapter/section context.

Dimensions:
  topic (40%) — embedding cosine similarity between citation and section text
  method (25%) — overlap between citation methods and section methods
  keyword (20%) — keyword Jaccard + semantic overlap
  recency (15%) — year appropriateness for chapter context

Reference projects:
  SPECTER (Allen AI) — academic document embeddings for paper matching
  SECTOR — multi-dimensional text matching with semantic alignment
  semantic-scholar-skills — citation context tracing via Semantic Scholar API
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Weight configuration ────────────────────────────────────────────────────

RELEVANCE_WEIGHTS = {
    "topic": 0.45,
    "method": 0.20,
    "keyword": 0.20,
    "recency": 0.15,
}

# Chapter recency preferences: higher = prefers newer literature
_CHAPTER_RECENCY_PREF: Dict[str, float] = {
    "1": 0.3,  # 绪论: accepts classic/seminal papers
    "2": 0.6,  # 文献综述/理论基础: balanced
    "3": 0.9,  # 研究方法: prefers recent
    "4": 0.85,  # 实证分析: prefers recent
    "5": 0.7,  # 讨论: balanced
    "6": 0.5,  # 结论: accepts broader range
}

# ── Embedding helper ────────────────────────────────────────────────────────

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        model_name = "BAAI/bge-small-zh-v1.5"
        _embedding_model = SentenceTransformer(model_name)
        return _embedding_model
    except Exception:
        return None


def _embed_text(text: str) -> Optional[np.ndarray]:
    """Compute embedding vector for text. Returns None if model unavailable."""
    model = _get_embedding_model()
    if model is None:
        return None
    if not text or not text.strip():
        return None
    # BGE models benefit from "为这个句子生成表示以用于检索相关文章：" prefix for queries
    vec = model.encode(text.strip()[:2000], normalize_embeddings=True)
    return vec.astype(np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors."""
    return float(np.dot(a, b))


# ── Chinese text tokenization ───────────────────────────────────────────────

# Common Chinese academic n-grams that act as stopwords — too generic to signal
# topical match. Without filtering, they inflate keyword overlap for unrelated papers.
_CJK_STOP_TOKENS: set = {
    "研究", "分析", "方法", "基于", "进行", "影响", "本文", "表明",
    "问题", "提出", "结果", "相关", "具有", "存在", "不同", "通过",
    "一个", "主要", "以及", "实现", "发展", "应用", "提供", "方面",
    "利用", "采用", "较为", "我国", "目前", "作用", "过程", "形成",
    "型的", "中的", "的研", "等方", "及其", "特征", "机制", "之间",
    "一种", "用于", "可以", "这一", "重要", "需要", "可能",
    "模型", "技术", "系统", "数据", "理论", "实践", "管理",
    "水平", "能力", "体系", "效果", "模式", "策略", "关系",
    "显著", "明显", "有效", "综合", "整体", "比较", "关键",
}
# Grammatical/non-substantive 2-gram fragments that should never count as keywords.
_CJK_NOISE_PATTERNS: set = {
    "型的", "中的", "的研", "的相", "的影", "的作", "的应",
    "性的", "化的", "法的", "度的", "平的", "量的",
    "行了", "出了", "入了", "发了", "展了",
    "于其", "与其", "从某", "在某",
    "的模", "的技", "的系", "的数", "的理", "的策",
    "型的", "性的", "术的", "统的", "据的",
}


def _tokenize_keywords(text: str, filter_stop: bool = False) -> set:
    """Extract meaningful keyword tokens from Chinese/English text.

    Uses 2-gram and 3-gram CJK chunks plus English words 3+ chars.
    When filter_stop=True, removes common academic stopword n-grams.
    """
    if not text:
        return set()
    tokens = set()
    cjk = re.findall(r"[一-鿿]+", text)
    for chunk in cjk:
        for i in range(0, len(chunk) - 1):
            t = chunk[i:i + 2]
            if not filter_stop or (t not in _CJK_STOP_TOKENS and t not in _CJK_NOISE_PATTERNS):
                tokens.add(t)
        for i in range(0, len(chunk) - 2):
            t = chunk[i:i + 3]
            if not filter_stop or t not in _CJK_STOP_TOKENS:
                tokens.add(t)
    en_words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    tokens.update(en_words)
    return tokens


# ── Dimension scorers ───────────────────────────────────────────────────────

def score_topic(
    citation: Dict[str, Any],
    section_text: str,
    section_title: str = "",
) -> Tuple[float, str]:
    """Score topic similarity between citation and section content.

    Uses BGE embedding cosine similarity as primary signal.
    Falls back to keyword overlap if embedding model unavailable.
    """
    # Build citation text for embedding
    cit_parts = []
    title = citation.get("title", "")
    if title:
        cit_parts.append(title)
    formatted = citation.get("formatted", "")
    # Extract abstract-like content from formatted if available
    if formatted:
        cit_parts.append(formatted[:500])
    cit_text = " ".join(cit_parts)

    # Build section context
    section_parts = [section_title] if section_title else []
    if section_text:
        section_parts.append(section_text[:2000])
    sec_text = " ".join(section_parts)

    if not cit_text.strip() or not sec_text.strip():
        return 0.3, "引用或章节文本为空"

    # Try embedding similarity
    cit_vec = _embed_text(cit_text)
    sec_vec = _embed_text(sec_text)

    if cit_vec is not None and sec_vec is not None:
        sim = _cosine_similarity(cit_vec, sec_vec)
        # Scale: cosine 0.25→fair, 0.45→good, 0.6+→excellent
        scaled = min(1.0, max(0.1, (sim - 0.05) / 0.55))
        if scaled > 0.85:
            note = "主题高度相关"
        elif scaled > 0.55:
            note = "主题相关"
        elif scaled > 0.3:
            note = "主题部分相关"
        else:
            note = "主题关联较弱"
        return round(scaled, 3), note

    # Fallback: keyword overlap
    cit_tokens = _tokenize_keywords(cit_text, filter_stop=True)
    sec_tokens = _tokenize_keywords(sec_text, filter_stop=True)
    if not cit_tokens or not sec_tokens:
        return 0.2, "无法计算主题相似度"
    jaccard = len(cit_tokens & sec_tokens) / max(1, len(cit_tokens | sec_tokens))
    scaled = min(1.0, jaccard * 3)  # amplify since Jaccard is usually small
    return round(scaled, 3), f"关键词重叠度 {round(jaccard, 2)}"


def score_method(
    citation: Dict[str, Any],
    section_methods: List[str],
    section_text: str = "",
) -> Tuple[float, str]:
    """Score method overlap between citation and section.

    When section_methods are provided explicitly, uses Jaccard overlap.
    Otherwise falls back to checking if citation methods appear verbatim
    in the section text — useful when the draft mentions methods inline.
    Filters out __none__ placeholder values.
    """
    cit_methods = citation.get("methods", [])
    if isinstance(cit_methods, str):
        try:
            cit_methods = json.loads(cit_methods)
        except (json.JSONDecodeError, TypeError):
            cit_methods = [cit_methods]

    cit_set = {m.lower().strip() for m in cit_methods if m and m != "__none__"}

    if not cit_set:
        return 0.5, "引用无方法标签"

    if section_methods:
        sec_set = {m.lower().strip() for m in section_methods if m}
        if not sec_set:
            return 0.5, "无方法信息"
        overlap = cit_set & sec_set
        if not overlap:
            return 0.2, "引用方法与章节方法无交集"
        jaccard = len(overlap) / max(1, len(cit_set | sec_set))
        if jaccard > 0.5:
            note = f"方法高度匹配: {', '.join(overlap)}"
        elif jaccard > 0.2:
            note = f"方法部分匹配: {', '.join(overlap)}"
        else:
            note = f"方法有交集: {', '.join(overlap)}"
        return round(min(1.0, jaccard * 1.5), 3), note

    # No section_methods provided — check if citation methods appear in section text
    if not section_text or not section_text.strip():
        return 0.5, "无章节方法信息"

    sec_lower = section_text.lower()
    found = []
    for m in cit_set:
        # Check if method name (2+ chars) appears in section text
        if len(m) >= 3 and m in sec_lower:
            found.append(m)

    if not found:
        return 0.3, "引用方法未在章节中提及"

    coverage = len(found) / len(cit_set)
    scaled = max(0.3, min(1.0, 0.4 + coverage * 0.6))
    if coverage > 0.5:
        note = f"方法匹配: {', '.join(found[:3])}"
    else:
        note = f"部分方法匹配: {', '.join(found[:3])}"
    return round(scaled, 3), note


def score_keyword(
    citation: Dict[str, Any],
    section_keywords: List[str],
    section_text: str = "",
) -> Tuple[float, str]:
    """Score keyword overlap between citation and section.

    When section_keywords provided explicitly: computes coverage of those
    keywords in the citation text (section→citation direction).

    When only section_text available: computes coverage of citation's
    meaningful n-gram tokens in the section text (citation→section direction).
    This avoids the random-subset problem of picking 30 tokens from a large
    unordered set.
    """
    cit_text = citation.get("title", "") + " " + citation.get("formatted", "")[:500]

    if not cit_text.strip():
        return 0.5, "引用文本为空"

    if section_keywords:
        # Explicit keywords: check how many appear in citation
        cit_tokens = _tokenize_keywords(cit_text)
        kw_set = {kw.lower().strip() for kw in section_keywords if kw}
        if not cit_tokens or not kw_set:
            return 0.5, "无法提取关键词"
        matched = cit_tokens & kw_set
        coverage = len(matched) / max(1, len(kw_set))
        scaled = max(0.3, min(1.0, coverage * 6.0))
        if scaled > 0.7:
            note = f"关键词高度重叠 ({len(matched)}/{len(kw_set)})"
        elif scaled > 0.45:
            note = f"关键词部分重叠 ({len(matched)}/{len(kw_set)})"
        else:
            note = f"关键词低重叠 ({len(matched)}/{len(kw_set)})"
        return round(scaled, 3), note

    if not section_text or not section_text.strip():
        return 0.5, "无章节文本"

    # No explicit keywords: check how many citation tokens appear in section
    cit_tokens = _tokenize_keywords(cit_text, filter_stop=True)
    sec_tokens = _tokenize_keywords(section_text, filter_stop=True)

    if not cit_tokens or not sec_tokens:
        return 0.5, "无法提取关键词"

    matched = cit_tokens & sec_tokens
    n_matched = len(matched)
    coverage = n_matched / max(1, len(cit_tokens))

    # Require at least 2 substantive token matches to go above baseline.
    # Single-match is almost always a noise fragment (e.g., "模型的").
    if n_matched <= 1:
        scaled = 0.3 if n_matched == 0 else 0.35
    else:
        # Scale: 10% coverage → 0.4, 20% → 0.6, 40%+ → 1.0
        scaled = max(0.35, min(1.0, 0.2 + coverage * 2.0))
    scaled = round(scaled, 3)

    if scaled > 0.7:
        note = f"关键词高度相关 ({n_matched}/{len(cit_tokens)})"
    elif scaled > 0.45:
        note = f"关键词部分相关 ({n_matched}/{len(cit_tokens)})"
    else:
        note = f"关键词低相关 ({n_matched}/{len(cit_tokens)})"

    return scaled, note


def score_recency_fit(
    citation: Dict[str, Any],
    chapter_number: str = "",
) -> Tuple[float, str]:
    """Score how well the citation year fits the chapter context.

    Higher chapter numbers (methods/results) prefer newer papers.
    Lower chapter numbers (introduction/conclusion) accept older papers.
    """
    year_str = str(citation.get("year", "")).strip()
    try:
        year = int(year_str)
    except (ValueError, TypeError):
        return 0.3, "无法确定出版年份"

    import time
    current_year = time.localtime().tm_year
    age = current_year - year

    # Get chapter preference (default: balanced)
    pref = _CHAPTER_RECENCY_PREF.get(str(chapter_number), 0.5)

    if age <= 3:
        base = 1.0
    elif age <= 5:
        base = 0.85
    elif age <= 10:
        base = 0.5
    elif age <= 15:
        base = 0.25
    else:
        base = 0.1

    # Adjust by chapter preference: newer-focused chapters penalize older papers more
    if pref > 0.7 and age > 5:
        base *= 0.7
    elif pref < 0.4 and age > 10:
        base *= 1.2  # classic papers acceptable in intro/conclusion

    score = round(min(1.0, base), 3)

    ch_label = f"第{chapter_number}章" if chapter_number else "当前章节"
    return score, f"{ch_label}时效适配 ({year}, 距今{age}年)"


# ── Composite scoring ───────────────────────────────────────────────────────

def score_relevance(
    citation: Dict[str, Any],
    section_text: str = "",
    section_title: str = "",
    section_methods: Optional[List[str]] = None,
    section_keywords: Optional[List[str]] = None,
    chapter_number: str = "",
) -> Dict[str, Any]:
    """Score citation relevance to a specific section.

    Returns dict with dimension scores, composite, and grade.
    """
    if section_methods is None:
        section_methods = []
    if section_keywords is None:
        section_keywords = []

    dims = {}

    # Topic similarity
    topic_score, topic_note = score_topic(citation, section_text, section_title)
    dims["topic"] = {"score": topic_score, "weight": RELEVANCE_WEIGHTS["topic"], "note": topic_note}

    # Method match
    method_score, method_note = score_method(citation, section_methods, section_text)
    dims["method"] = {"score": method_score, "weight": RELEVANCE_WEIGHTS["method"], "note": method_note}

    # Keyword match
    kw_score, kw_note = score_keyword(citation, section_keywords, section_text)
    dims["keyword"] = {"score": kw_score, "weight": RELEVANCE_WEIGHTS["keyword"], "note": kw_note}

    # Recency fit
    rec_score, rec_note = score_recency_fit(citation, chapter_number)
    dims["recency"] = {"score": rec_score, "weight": RELEVANCE_WEIGHTS["recency"], "note": rec_note}

    # Composite
    composite = sum(d["score"] * d["weight"] for d in dims.values())
    relevance = round(composite * 100, 1)

    if relevance >= 85:
        grade = "★★★"
        label = "高度适配"
    elif relevance >= 65:
        grade = "★★☆"
        label = "适配"
    elif relevance >= 45:
        grade = "★☆☆"
        label = "部分适配"
    else:
        grade = "☆☆☆"
        label = "低适配"

    return {
        "relevance_score": relevance,
        "grade": grade,
        "grade_label": label,
        "dimensions": dims,
    }


def score_relevance_batch(
    citations: List[Dict[str, Any]],
    section_text: str = "",
    section_title: str = "",
    section_methods: Optional[List[str]] = None,
    section_keywords: Optional[List[str]] = None,
    chapter_number: str = "",
) -> List[Dict[str, Any]]:
    """Score relevance for multiple citations against the same section."""
    results = []
    for cit in citations:
        result = score_relevance(
            cit,
            section_text=section_text,
            section_title=section_title,
            section_methods=section_methods,
            section_keywords=section_keywords,
            chapter_number=chapter_number,
        )
        result["card_id"] = cit.get("card_id", "")
        results.append(result)
    return results
