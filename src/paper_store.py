"""
论文级结构化存储：SQLite 持久化，支持方向/方法/理论分类、质量评分、引用卡片生成。
每个 paper 对应一篇本地论文的完整结构化元数据。
"""

from __future__ import annotations

import json
import re
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

METHOD_CATEGORIES: Dict[str, List[str]] = {
    "质量管理": ["CMMI", "PDCA", "六西格玛", "DMAIC", "FURPS+", "鱼骨图", "5Why", "5M1E", "QFD", "FMEA", "SPC", "8D", "帕累托分析"],
    "系统分析": ["层次分析法", "AHP", "模糊综合评价", "德尔菲法", "SWOT", "PEST", "标杆分析法", "平衡计分卡", "KPI"],
    "项目管理": ["WBS", "关键路径法", "CPM", "挣值管理", "EVM", "Scrum", "DevOps", "敏捷", "看板"],
    "数据分析": ["SPSS", "问卷调查", "案例研究", "文献研究", "访谈法", "扎根理论", "内容分析", "回归分析"],
    "流程优化": ["ESIA", "BPR", "价值流图", "VSM", "精益", "看板管理"],
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


def upsert_citation_card(card: Dict[str, Any], db_path: Optional[Path] = None) -> str:
    """插入或更新一张引用卡片。"""
    import sqlite3

    path = db_path or PAPER_DB_PATH
    conn = sqlite3.connect(str(path))
    now = time.time()
    card_id = card.get("card_id") or f"CITE-{uuid.uuid4().hex[:8].upper()}"

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
        card.get("formatted", ""),
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


def _expand_method_terms(method: str) -> List[str]:
    """将前端方法名展开为多个搜索词，覆盖数据库中可能存储的短名。"""
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
        d[field.replace("_json", "")] = json.loads(val) if isinstance(val, str) else (val or [])
        del d[field]
    return d
