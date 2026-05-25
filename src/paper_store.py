"""
论文级结构化存储：SQLite 持久化，支持方向/方法/理论分类、质量评分、引用卡片生成。
每个 paper 对应一篇本地论文的完整结构化元数据。
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAPER_DB_PATH = PROJECT_ROOT / "knowledge_base" / "papers.sqlite3"

DIRECTION_MAP: Dict[str, str] = {
    "quality_management": "质量管理",
    "risk_management": "风险管理",
    "schedule_management": "进度管理",
    "requirements_management": "需求管理",
    "process_optimization": "流程优化",
    "cost_management": "成本管理",
    "supply_chain_logistics": "供应链与物流",
}

THEORY_FRAMEWORKS: Dict[str, List[str]] = {
    "质量管理理论": ["全面质量管理", "TQM", "ISO9000", "CMMI", "零缺陷", "质量成本", "朱兰三部曲"],
    "项目管理理论": ["PMBOK", "PRINCE2", "敏捷宣言", "精益项目管理", "项目治理"],
    "组织理论": ["组织变革", "学习型组织", "知识管理", "利益相关者理论", "制度理论"],
    "系统理论": ["系统动力学", "社会技术系统", "复杂适应系统", "软系统方法论"],
    "决策理论": ["多准则决策", "博弈论", "前景理论", "有限理性"],
}


def init_paper_db(db_path: Optional[Path] = None) -> None:
    """初始化论文存储数据库表结构。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            doc_id       TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            authors_json TEXT NOT NULL DEFAULT '[]',
            year         INTEGER,
            source       TEXT DEFAULT '',
            source_path  TEXT NOT NULL,
            abstract     TEXT DEFAULT '',
            keywords_json TEXT NOT NULL DEFAULT '[]',
            sections_json TEXT NOT NULL DEFAULT '[]',
            methods_json TEXT NOT NULL DEFAULT '[]',
            theory_frameworks_json TEXT NOT NULL DEFAULT '[]',
            direction_id TEXT DEFAULT '',
            direction_label TEXT DEFAULT '',
            quality_score REAL DEFAULT 0.0,
            localization_score REAL DEFAULT 0.0,
            reference_count INTEGER DEFAULT 0,
            word_count    INTEGER DEFAULT 0,
            language      TEXT DEFAULT 'zh',
            cleaned       INTEGER DEFAULT 0,
            indexed       INTEGER DEFAULT 0,
            created_at    REAL NOT NULL,
            updated_at    REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS citation_cards (
            card_id      TEXT PRIMARY KEY,
            paper_id     TEXT NOT NULL,
            formatted    TEXT NOT NULL,
            title        TEXT DEFAULT '',
            authors      TEXT DEFAULT '',
            year         TEXT DEFAULT '',
            language     TEXT DEFAULT 'zh',
            ref_type     TEXT DEFAULT '期刊文章',
            methods_json TEXT NOT NULL DEFAULT '[]',
            direction_id TEXT DEFAULT '',
            direction_label TEXT DEFAULT '',
            theory_tags_json TEXT NOT NULL DEFAULT '[]',
            verified     INTEGER DEFAULT 0,
            verification_note TEXT DEFAULT '',
            inserted_count INTEGER DEFAULT 0,
            quality_score REAL DEFAULT 0.0,
            source_section TEXT DEFAULT '',
            source_paper_title TEXT DEFAULT '',
            created_at   REAL NOT NULL,
            FOREIGN KEY (paper_id) REFERENCES papers(doc_id)
        );

        CREATE INDEX IF NOT EXISTS idx_papers_direction ON papers(direction_id);
        CREATE INDEX IF NOT EXISTS idx_papers_quality ON papers(quality_score DESC);
        CREATE INDEX IF NOT EXISTS idx_cards_paper ON citation_cards(paper_id);
        CREATE INDEX IF NOT EXISTS idx_cards_direction ON citation_cards(direction_id);
        CREATE INDEX IF NOT EXISTS idx_cards_methods ON citation_cards(methods_json);
        CREATE INDEX IF NOT EXISTS idx_cards_verified ON citation_cards(verified);
        CREATE INDEX IF NOT EXISTS idx_cards_quality ON citation_cards(quality_score DESC);
    """)
    conn.commit()
    conn.close()


def upsert_paper(paper: Dict[str, Any], db_path: Optional[Path] = None) -> str:
    """插入或更新一篇论文的结构化数据。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    conn = sqlite3.connect(str(path))
    now = time.time()
    doc_id = paper.get("doc_id") or f"PAPER-{uuid.uuid4().hex[:8].upper()}"

    conn.execute("""
        INSERT OR REPLACE INTO papers (
            doc_id, title, authors_json, year, source, source_path,
            abstract, keywords_json, sections_json, methods_json,
            theory_frameworks_json, direction_id, direction_label,
            quality_score, localization_score, reference_count, word_count,
            language, cleaned, indexed, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id,
        paper.get("title", ""),
        json.dumps(paper.get("authors", []), ensure_ascii=False),
        paper.get("year"),
        paper.get("source", ""),
        paper.get("source_path", ""),
        paper.get("abstract", ""),
        json.dumps(paper.get("keywords", []), ensure_ascii=False),
        json.dumps(paper.get("sections", []), ensure_ascii=False),
        json.dumps(paper.get("methods", []), ensure_ascii=False),
        json.dumps(paper.get("theory_frameworks", []), ensure_ascii=False),
        paper.get("direction_id", ""),
        paper.get("direction_label", ""),
        paper.get("quality_score", 0.0),
        paper.get("localization_score", 0.0),
        paper.get("reference_count", 0),
        paper.get("word_count", 0),
        paper.get("language", "zh"),
        paper.get("cleaned", 0),
        paper.get("indexed", 0),
        paper.get("created_at", now),
        now,
    ))
    conn.commit()
    conn.close()
    return doc_id


def _normalize_title_for_dedup(title: str) -> str:
    """Normalize title for dedup comparison — shared across all insert paths."""
    if not title:
        return ""
    s = title.lower().strip()
    s = re.sub(r'[，,、､]\s*', ', ', s)
    s = re.sub(r'[。．.]\s*', '. ', s)
    s = re.sub(r'([一-鿿])([a-zA-Z])', r'\1 \2', s)
    s = re.sub(r'([a-zA-Z])([一-鿿])', r'\1 \2', s)
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[\[\]【】（）()「」『』《》""\'\'""“”‘’]', '', s)
    return s.strip().rstrip(',.;;.，。．：:！!？?')


def upsert_citation_card(card: Dict[str, Any], db_path: Optional[Path] = None) -> str:
    """插入或更新一张引用卡片。按标题自动去重。"""
    import re
    import sqlite3

    path = db_path or PAPER_DB_PATH
    conn = sqlite3.connect(str(path))
    now = time.time()
    card_id = card.get("card_id") or f"CITE-{uuid.uuid4().hex[:8].upper()}"

    # Strip leading [N], [N,M], [N-M] and truncate at appendix boundary
    formatted = card.get("formatted", "")
    if formatted:
        formatted = re.sub(r"^\s*\[\s*(?:\d+(?:\s*[,，、\s-]\s*\d+)*)\s*\]\s*", "", formatted, count=1)
        # Truncate at appendix content (PDF parser bug)
        parts = re.split(r"(?:浙江大学)?附录[一二三四五六七八九十\d]*[：:\s]?", formatted, maxsplit=1)
        if len(parts) > 1 and len(parts[0].strip()) > 10:
            formatted = parts[0].strip()

    # 按标准化标题去重：如果已存在同标题卡片，跳过插入，返回已有 card_id
    title = card.get("title", "")
    if title:
        norm = _normalize_title_for_dedup(title)
        for row in conn.execute("SELECT card_id, title FROM citation_cards").fetchall():
            if _normalize_title_for_dedup(str(row[1] or "")) == norm:
                conn.close()
                return str(row[0])  # 已有卡片，返回已有 ID

    conn.execute("""
        INSERT OR REPLACE INTO citation_cards (
            card_id, paper_id, formatted, title, authors, year, language,
            ref_type, methods_json, direction_id, direction_label,
            theory_tags_json, verified, verification_note, inserted_count, quality_score,
            source_section, source_paper_title, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        card_id,
        card.get("paper_id", ""),
        formatted,
        card.get("title", ""),
        card.get("authors", ""),
        str(card.get("year", "")),
        card.get("language", "zh"),
        card.get("ref_type", "期刊文章"),
        json.dumps(card.get("methods", []), ensure_ascii=False),
        card.get("direction_id", ""),
        card.get("direction_label", ""),
        json.dumps(card.get("theory_tags", []), ensure_ascii=False),
        card.get("verified", 0),
        card.get("verification_note", ""),
        card.get("inserted_count", 0),
        card.get("quality_score", 0.0),
        card.get("source_section", ""),
        card.get("source_paper_title", ""),
        now,
    ))
    conn.commit()
    conn.close()
    return card_id


def get_papers_by_direction(direction_id: str, limit: int = 20,
                            min_quality: float = 0.0,
                            db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """按研究方向查询论文。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM papers
        WHERE direction_id = ? AND quality_score >= ?
        ORDER BY quality_score DESC
        LIMIT ?
    """, (direction_id, min_quality, limit)).fetchall()
    conn.close()
    return [_paper_row_to_dict(r) for r in rows]


_METHOD_ALIAS_CACHE: Optional[Dict[str, List[str]]] = None


def _load_method_alias_map() -> Dict[str, List[str]]:
    """Load method name → aliases from cards DB, caching in module state."""
    global _METHOD_ALIAS_CACHE
    if _METHOD_ALIAS_CACHE is not None:
        return _METHOD_ALIAS_CACHE
    try:
        from pathlib import Path as _Path
        cards_db = _Path(__file__).resolve().parent.parent / "knowledge_base" / "cards.sqlite3"
        if not cards_db.exists():
            return {}
        import sqlite3 as _sqlite3, json as _json
        conn = _sqlite3.connect(str(cards_db))
        rows = conn.execute("SELECT name, aliases FROM cards WHERE type='method_card'").fetchall()
        result = {}
        for name, aliases_json in rows:
            if name:
                aliases = _json.loads(aliases_json) if aliases_json else []
                result[name] = aliases
        conn.close()
        _METHOD_ALIAS_CACHE = result
        return result
    except Exception:
        return {}

def _expand_method_terms(method: str) -> List[str]:
    """将前端方法名展开为多个搜索词，覆盖数据库中可能存储的短名和别名。"""
    terms = {method}
    # 去掉常见后缀，生成短名搜索词
    for suffix in ["循环", "管理", "方法", "法", "分析", "模型", "体系", "理论",
                    "技术", "工具", "图", "表", "矩阵", "评价", "评估", "优化"]:
        if method.endswith(suffix) and len(method) > len(suffix) + 1:
            terms.add(method[:-len(suffix)])
    # 去掉括号内容
    import re as _re
    simple = _re.sub(r"[（(][^)）]*[)）]", "", method).strip()
    if simple and simple != method:
        terms.add(simple)
    # 从卡片别名库中补充同义词
    alias_map = _load_method_alias_map()
    for card_aliases in alias_map.values():
        if method in card_aliases:
            terms.update(card_aliases)
    if method in alias_map:
        terms.update(alias_map[method])
    return list(terms)


def get_cards_by_direction_and_methods(
    direction_id: str,
    methods: List[str],
    limit: int = 20,
    verified_only: bool = False,
    db_path: Optional[Path] = None,
    max_per_source: int = 0,
) -> List[Dict[str, Any]]:
    """按方向和方法筛选引用卡片。

    max_per_source > 0 时启用来源多样性：每篇来源论文最多贡献 max_per_source 张卡片。
    """
    import sqlite3

    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # 拉取更大池子
    fetch_limit = max(limit * 3, 200) if max_per_source > 0 else limit
    if direction_id:
        query = "SELECT * FROM citation_cards WHERE direction_id = ?"
        params: List[Any] = [direction_id]
    else:
        query = "SELECT * FROM citation_cards WHERE 1=1"
        params: List[Any] = []

    if methods:
        method_clauses = []
        for m in methods:
            for term in _expand_method_terms(m):
                method_clauses.append("methods_json LIKE ?")
                params.append(f"%{term}%")
        query += f" AND ({' OR '.join(method_clauses)})"

    if verified_only:
        query += " AND verified = 1"

    query += " ORDER BY quality_score DESC LIMIT ?"
    params.append(fetch_limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    cards = [_card_row_to_dict(r) for r in rows]

    if max_per_source > 0 and len(cards) > limit:
        cards = _diversify_cards(cards, limit, max_per_source)
    return cards[:limit]


def _diversify_cards(
    cards: List[Dict[str, Any]], limit: int, max_per_source: int
) -> List[Dict[str, Any]]:
    """Round-robin 选卡，每篇来源论文最多 max_per_source 张。"""
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for c in cards:
        src = c.get("source_paper_title", "") or c.get("paper_id", "")
        buckets.setdefault(src, []).append(c)

    result: List[Dict[str, Any]] = []
    seen_titles: set = set()
    # 轮询各来源
    while len(result) < limit and buckets:
        for src in list(buckets.keys()):
            if src not in buckets:
                continue
            taken = sum(1 for c in result if (c.get("source_paper_title") or c.get("paper_id")) == src)
            if taken >= max_per_source:
                del buckets[src]
                continue
            if not buckets[src]:
                del buckets[src]
                continue
            card = buckets[src].pop(0)
            if card["title"] not in seen_titles:
                seen_titles.add(card["title"])
                result.append(card)
            if len(result) >= limit:
                break

    return result


def search_cards(
    direction_id: str = "",
    method: str = "",
    keyword: str = "",
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """多条件检索引用卡片。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    conditions = []
    params: List[Any] = []

    if direction_id:
        conditions.append("direction_id = ?")
        params.append(direction_id)
    if method:
        method_terms = _expand_method_terms(method)
        method_clauses = []
        for term in method_terms:
            method_clauses.append("methods_json LIKE ?")
            params.append(f"%{term}%")
        conditions.append("(" + " OR ".join(method_clauses) + ")")
    if keyword:
        conditions.append("(title LIKE ? OR formatted LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    query = "SELECT * FROM citation_cards"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY quality_score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_card_row_to_dict(r) for r in rows]


def get_paper_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """获取论文库统计信息。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return {"papers": 0, "cards": 0}
    conn = sqlite3.connect(str(path))
    paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    card_count = conn.execute("SELECT COUNT(*) FROM citation_cards").fetchone()[0]
    dir_stats = {}
    for row in conn.execute(
        "SELECT direction_id, COUNT(*) as cnt FROM papers WHERE direction_id != '' GROUP BY direction_id"
    ):
        dir_stats[row[0]] = row[1]
    conn.close()
    return {
        "papers": paper_count,
        "cards": card_count,
        "direction_stats": dir_stats,
    }


def list_all_papers(
    direction_id: str = "",
    keyword: str = "",
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """分页列出所有论文，支持可选筛选。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return {"papers": [], "total": 0}
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    where = []
    params = []
    if direction_id:
        where.append("direction_id = ?")
        params.append(direction_id)
    if keyword:
        where.append("(title LIKE ? OR abstract LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    query = "SELECT * FROM papers"
    if where:
        query += " WHERE " + " AND ".join(where)

    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total = conn.execute(count_query, params).fetchone()[0]

    query += " ORDER BY year DESC, quality_score DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    papers = [_paper_row_to_dict(r) for r in rows]
    conn.close()
    return {"papers": papers, "total": total}


def get_paper_by_id(doc_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """按 doc_id 获取单篇论文。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    row = conn.execute("SELECT * FROM papers WHERE doc_id = ?", (doc_id,)).fetchone()
    conn.close()
    return _paper_row_to_dict(row) if row else None


def delete_paper(doc_id: str, db_path: Optional[Path] = None) -> bool:
    """删除论文及其关联的 citation cards。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return False
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("DELETE FROM citation_cards WHERE paper_id = ?", (doc_id,))
    cur = conn.execute("DELETE FROM papers WHERE doc_id = ?", (doc_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def _paper_row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for field in ["authors_json", "keywords_json", "sections_json", "methods_json", "theory_frameworks_json"]:
        val = d.get(field)
        d[field.replace("_json", "")] = json.loads(val) if isinstance(val, str) else (val or [])
        del d[field]
    return d


def _card_row_to_dict(row: Any) -> Dict[str, Any]:
    d = dict(row)
    for field in ["methods_json", "theory_tags_json"]:
        val = d.get(field)
        parsed = json.loads(val) if isinstance(val, str) else (val or [])
        # Filter out internal sentinel for "LLM checked, no methods found"
        if isinstance(parsed, list):
            parsed = [x for x in parsed if x != "__none__"]
        d[field.replace("_json", "")] = parsed
        del d[field]
    return d


def update_card_methods(
    card_id: str,
    methods: List[str],
    theories: Optional[List[str]] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Update a citation card's methods_json and theory_tags_json."""
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return
    conn = sqlite3.connect(str(path))
    conn.execute(
        "UPDATE citation_cards SET methods_json = ?, theory_tags_json = ? WHERE card_id = ?",
        (json.dumps(methods, ensure_ascii=False),
         json.dumps(theories or [], ensure_ascii=False),
         card_id),
    )
    conn.commit()
    conn.close()


def count_citations_without_methods(db_path: Optional[Path] = None) -> int:
    """Count citation cards that have empty methods_json."""
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return 0
    conn = sqlite3.connect(str(path))
    cur = conn.execute(
        "SELECT COUNT(*) FROM citation_cards WHERE methods_json = '[]' OR methods_json IS NULL"
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_citations_without_methods(
    limit: int = 500, offset: int = 0, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Get citation cards with empty methods_json for batch classification."""
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT card_id, title, formatted FROM citation_cards "
        "WHERE methods_json = '[]' OR methods_json IS NULL "
        "LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_citations_without_methods_enriched(
    limit: int = 500, offset: int = 0, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Get unclassified citation cards with enriched data for LLM classification.

    Includes: card_id, title, direction_label, source_section, paper_abstract.
    """
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT cc.card_id, cc.title, cc.direction_label, cc.source_section, "
        "p.abstract AS paper_abstract "
        "FROM citation_cards cc "
        "LEFT JOIN papers p ON cc.paper_id = p.doc_id "
        "WHERE cc.methods_json = '[]' OR cc.methods_json IS NULL "
        "ORDER BY cc.quality_score DESC "
        "LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Method keyword index for pre-filtering ──

_method_keyword_index: Optional[Dict[str, List[str]]] = None
_direction_method_candidates: Optional[Dict[str, List[Dict[str, Any]]]] = None


def _load_method_registry() -> List[Dict[str, Any]]:
    """Load all methods from cards.sqlite3 with their names, aliases, domains, phases."""
    cards_db = PROJECT_ROOT / "knowledge_base" / "cards.sqlite3"
    if not cards_db.exists():
        return []
    conn = sqlite3.connect(str(cards_db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, aliases, domains, phase, category FROM cards"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "name": r["name"],
            "aliases": json.loads(r["aliases"]) if r["aliases"] else [],
            "domains": json.loads(r["domains"]) if r["domains"] else [],
            "phase": json.loads(r["phase"]) if r["phase"] else [],
            "category": r["category"],
        })
    return result


def build_method_keyword_index() -> Dict[str, List[str]]:
    """Build a keyword→method mapping from the method registry.

    Each method name and its aliases become search keywords.
    Returns {method_name: [keyword1, keyword2, ...]}.
    """
    global _method_keyword_index
    if _method_keyword_index is not None:
        return _method_keyword_index

    methods = _load_method_registry()
    index: Dict[str, List[str]] = {}
    for m in methods:
        keywords = [m["name"]]
        for alias in m["aliases"]:
            if alias and alias != m["name"]:
                keywords.append(alias)
        # Generate short-form keywords by stripping common suffixes
        for kw in list(keywords):
            for suffix in ["循环", "管理", "方法", "法", "分析", "模型", "体系",
                           "理论", "技术", "工具", "图", "表", "矩阵", "评价",
                           "评估", "优化", "设计"]:
                if kw.endswith(suffix) and len(kw) > len(suffix) + 1:
                    short = kw[:-len(suffix)]
                    if short not in keywords:
                        keywords.append(short)
        index[m["name"]] = keywords
    _method_keyword_index = index
    return index


def build_direction_method_candidates() -> Dict[str, List[Dict[str, Any]]]:
    """Build direction→relevant methods mapping for LLM prompt context.

    Returns {direction_id: [{name, aliases, phase}, ...]}.
    """
    global _direction_method_candidates
    if _direction_method_candidates is not None:
        return _direction_method_candidates

    methods = _load_method_registry()
    candidates: Dict[str, List[Dict[str, Any]]] = {}

    # Domain-specific methods
    for m in methods:
        for domain in m["domains"]:
            if domain not in candidates:
                candidates[domain] = []
            candidates[domain].append({
                "name": m["name"],
                "aliases": m["aliases"][:3] if m["aliases"] else [],
                "phase": m["phase"],
            })

    # Universal methods (no domain) — add to all directions
    universal = []
    for m in methods:
        if not m["domains"]:
            universal.append({
                "name": m["name"],
                "aliases": m["aliases"][:3] if m["aliases"] else [],
                "phase": m["phase"],
            })

    for domain in list(candidates.keys()):
        candidates[domain].extend(universal)

    _direction_method_candidates = candidates
    return candidates


def _direction_label_to_id(label: str) -> Optional[str]:
    """Convert Chinese direction label to domain ID."""
    for k, v in DIRECTION_MAP.items():
        if v == label:
            return k
    return None


def get_method_candidates_for_direction(direction_label: str) -> List[Dict[str, Any]]:
    """Get relevant method candidates for a given research direction."""
    candidates = build_direction_method_candidates()
    domain_id = _direction_label_to_id(direction_label)
    if domain_id and domain_id in candidates:
        return candidates[domain_id]
    # Fallback: return all universal methods + all domain methods
    all_methods = []
    seen = set()
    for domain_methods in candidates.values():
        for m in domain_methods:
            if m["name"] not in seen:
                seen.add(m["name"])
                all_methods.append(m)
    return all_methods


def keyword_prefilter_citations(
    max_cards: Optional[int] = None, db_path: Optional[Path] = None
) -> int:
    """Fast keyword-based pre-classification of citation titles.

    Scans unclassified citation titles against method name keywords.
    If a title contains a method keyword, the method is assigned directly
    without LLM call.

    Returns: number of citations classified.
    """
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return 0

    index = build_method_keyword_index()
    if not index:
        return 0

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # Get unclassified citations
    limit_clause = f"LIMIT {int(max_cards)}" if max_cards else ""
    rows = conn.execute(
        f"SELECT card_id, title FROM citation_cards "
        f"WHERE methods_json = '[]' OR methods_json IS NULL "
        f"ORDER BY quality_score DESC "
        f"{limit_clause}"
    ).fetchall()

    total_updated = 0
    for row in rows:
        card_id = row["card_id"]
        title = row["title"] or ""
        matched_methods = []

        for method_name, keywords in index.items():
            for kw in keywords:
                if len(kw) >= 3 and kw in title:
                    matched_methods.append(method_name)
                    break  # one keyword match per method is enough

        if matched_methods:
            # Deduplicate: remove shorter names if longer variant matched
            # e.g., if both "六西格玛DMAIC" and "六西格玛管理" matched, keep both
            conn.execute(
                "UPDATE citation_cards SET methods_json = ? WHERE card_id = ?",
                (json.dumps(matched_methods, ensure_ascii=False), card_id),
            )
            total_updated += 1

    conn.commit()
    conn.close()
    return total_updated


# ── Scan-verify helpers ──

def count_unverified_citations(db_path: Optional[Path] = None) -> int:
    """Count citation cards where verified = 0."""
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return 0
    conn = sqlite3.connect(str(path))
    count = conn.execute(
        "SELECT COUNT(*) FROM citation_cards WHERE verified = 0"
    ).fetchone()[0]
    conn.close()
    return count


def get_unverified_citations_rich(
    limit: int = 100, offset: int = 0, db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """Fetch unverified citation cards with all fields needed for LLM scan-verify."""
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT card_id, formatted, title, authors, year, ref_type, language, "
        "direction_id, direction_label, source_section, source_paper_title "
        "FROM citation_cards "
        "WHERE verified = 0 "
        "ORDER BY quality_score DESC "
        "LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_card_verified(
    card_id: str,
    verified: int,
    verification_note: str = "",
    methods: Optional[List[str]] = None,
    theories: Optional[List[str]] = None,
    direction_id: str = "",
    direction_label: str = "",
    db_path: Optional[Path] = None,
) -> None:
    """Atomically update verification status, methods, theories, and direction."""
    path = db_path or PAPER_DB_PATH
    if not path.exists():
        return
    conn = sqlite3.connect(str(path))
    conn.execute(
        "UPDATE citation_cards SET verified = ?, verification_note = ?, "
        "methods_json = ?, theory_tags_json = ?, direction_id = ?, direction_label = ? "
        "WHERE card_id = ?",
        (
            verified,
            verification_note,
            json.dumps(methods or [], ensure_ascii=False),
            json.dumps(theories or [], ensure_ascii=False),
            direction_id,
            direction_label,
            card_id,
        ),
    )
    conn.commit()
    conn.close()
