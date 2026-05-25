"""
方法卡 Schema 校验 & 构建工具。
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_ROOT = PROJECT_ROOT / "cards"
METHODS_ROOT = CARDS_ROOT / "methods"
RISKS_ROOT = CARDS_ROOT / "risks"

# ── v1.1 方法卡必填字段 ──────────────────────────────────────
METHOD_REQUIRED_FRONTMATTER = [
    "id",
    "type",
    "name",
    "short_name",
    "aliases",
    "category",
    "phase",
    "disciplines",
    "domains",
    "applicable_sections",
    "pairs_with",
    "requires",
    "conflicts_with",
    "difficulty",
    "data_type",
    "outputs",
    "risk_tags",
    "inject_policy",
    "embedding_fields",
    "source_type",
    "scope",
    "status",
    "version",
]

METHOD_BODY_SECTIONS = [
    "方法定位",
    "定义",
    "适用场景",
    "不适用场景",
    "输入数据",
    "输出结果",
    "操作步骤",
    "优缺点",
    "适用章节",
    "常见错误",
    "可搭配方法",
    "示例表达",
    "生成约束",
    "参考文献",
]

# ── v1.0 盲审风险卡必填字段 ──────────────────────────────────
RISK_REQUIRED_FRONTMATTER = [
    "id",
    "type",
    "name",
    "severity",
    "category",
    "check_stage",
    "disciplines",
    "applicable_chapters",
    "trigger_conditions",
    "check_questions",
    "fix_strategy",
    "inject_policy",
    "embedding_fields",
    "source_type",
    "scope",
    "status",
    "version",
]

RISK_BODY_SECTIONS = [
    "风险定位",
    "严重程度",
    "触发条件",
    "检查问题",
    "修复策略",
    "可配合的风险检查",
    "示例表达",
    "生成约束",
]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()[:10]
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _json_dumps(obj: Any, **kwargs: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=_json_default, **kwargs)

# ── v1.1 必填字段 ──────────────────────────────────────────
REQUIRED_FRONTMATTER = [
    "id",
    "type",
    "name",
    "short_name",
    "aliases",
    "category",
    "phase",
    "disciplines",
    "domains",
    "applicable_sections",
    "pairs_with",
    "requires",
    "conflicts_with",
    "difficulty",
    "data_type",
    "outputs",
    "risk_tags",
    "inject_policy",
    "embedding_fields",
    "source_type",
    "scope",
    "status",
    "version",
]

REQUIRED_BODY_SECTIONS = [
    "方法定位",
    "定义",
    "适用场景",
    "不适用场景",
    "输入数据",
    "输出结果",
    "操作步骤",
    "优缺点",
    "适用章节",
    "常见错误",
    "可搭配方法",
    "示例表达",
    "生成约束",
    "参考文献",
]

VALID_CATEGORIES = {"quantitative", "qualitative", "hybrid", "framework", "model", "process"}
VALID_PHASES = {"discover", "solve", "verify", "validate"}
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced"}
VALID_EVIDENCE = {"low", "medium", "high"}
VALID_SOURCE_TYPES = {"builtin", "uploaded_paper", "user_created", "cross_discipline"}
VALID_SCOPES = {"platform", "user", "organization"}
VALID_STATUSES = {"draft", "reviewed", "deprecated"}


def parse_card(file_path: Path) -> Dict[str, Any]:
    """Parse a Markdown + YAML frontmatter card into structured dict."""
    text = file_path.read_text(encoding="utf-8")
    # Extract YAML frontmatter between --- markers
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not m:
        raise ValueError(f"{file_path.name}: 未找到 YAML frontmatter")

    frontmatter = yaml.safe_load(m.group(1))
    body = m.group(2).strip()

    return {"frontmatter": frontmatter, "body": body, "source_path": str(file_path)}


def validate_card(card: Dict[str, Any], card_type: str = "method_card") -> List[str]:
    """Validate a card against its schema. Returns list of issues."""
    issues = []
    fm = card.get("frontmatter", {})
    body = card.get("body", "")

    if card_type == "method_card":
        required_fm = METHOD_REQUIRED_FRONTMATTER
        required_body = METHOD_BODY_SECTIONS
    elif card_type == "risk_card":
        required_fm = RISK_REQUIRED_FRONTMATTER
        required_body = RISK_BODY_SECTIONS
    else:
        return [f"未知卡片类型: {card_type}"]

    # Required frontmatter fields
    for field in required_fm:
        if field not in fm or fm[field] is None:
            issues.append(f"缺少必填字段: {field}")

    # Type check
    expected_type = card_type
    if fm.get("type") != expected_type:
        issues.append(f"type 应为 {expected_type}，实际为 {fm.get('type')}")

    # Enum checks
    if card_type == "method_card":
        category = fm.get("category", "")
        if category and category not in VALID_CATEGORIES:
            issues.append(f"无效 method category: {category}，合法值: {VALID_CATEGORIES}")

        phase = fm.get("phase", [])
        if isinstance(phase, list):
            for p in phase:
                if p not in VALID_PHASES:
                    issues.append(f"无效 phase: {p}，合法值: {VALID_PHASES}")

        difficulty = fm.get("difficulty", "")
        if difficulty and difficulty not in VALID_DIFFICULTIES:
            issues.append(f"无效 difficulty: {difficulty}")

    status = fm.get("status", "")
    if status and status not in VALID_STATUSES:
        issues.append(f"无效 status: {status}")

    source_type = fm.get("source_type", "")
    if source_type and source_type not in VALID_SOURCE_TYPES:
        issues.append(f"无效 source_type: {source_type}")

    # inject_policy sub-fields
    inject = fm.get("inject_policy", {})
    if isinstance(inject, dict):
        if "stages" not in inject:
            issues.append("inject_policy 缺少 stages")
        if "max_tokens" not in inject:
            issues.append("inject_policy 缺少 max_tokens")
        if "inject_sections" not in inject:
            issues.append("inject_policy 缺少 inject_sections")

    # embedding_fields
    emb_fields = fm.get("embedding_fields", [])
    if isinstance(emb_fields, list) and "name" not in emb_fields:
        issues.append("embedding_fields 至少需要包含 'name'")

    # Body sections (warnings only, not blocking)
    body_warnings = []
    for section in required_body:
        if f"## {section}" not in body:
            body_warnings.append(f"正文缺少小节: ## {section}")

    # Risk-specific: severity must be valid
    if card_type == "risk_card":
        valid_severities = {"critical", "high", "medium", "low"}
        if fm.get("severity", "") not in valid_severities:
            issues.append(f"severity 无效: {fm.get('severity')}，合法值: {valid_severities}")

    return issues


def build_searchable_text(fm: Dict[str, Any], body: str) -> str:
    """Construct searchable_text from embedding_fields."""
    emb_fields = fm.get("embedding_fields", [])

    # Build field map
    field_map = {
        "name": fm.get("name", ""),
        "short_name": fm.get("short_name", ""),
        "aliases": "、".join(fm.get("aliases", [])),
        "category": fm.get("category", ""),
        "phase": "、".join(fm.get("phase", [])),
        "disciplines": "、".join(fm.get("disciplines", [])),
        "domains": "、".join(fm.get("domains", [])),
        "applicable_sections": "、".join(fm.get("applicable_sections", [])),
        "outputs": "、".join(fm.get("outputs", [])),
        "data_type": "、".join(fm.get("data_type", [])),
        "risk_tags": "、".join(fm.get("risk_tags", [])),
        "difficulty": fm.get("difficulty", ""),
        "pairs_with": "、".join(fm.get("pairs_with", [])),
    }

    lines = []
    for field_name in emb_fields:
        value = field_map.get(field_name)
        if value:
            lines.append(f"{field_name}: {value}")

    # Append body summary if requested
    if "body_summary" in emb_fields:
        body_summary = _extract_body_summary(body)
        if body_summary:
            lines.append(f"正文摘要: {body_summary}")

    return "\n".join(lines)


def _extract_body_summary(body: str, max_chars: int = 500) -> str:
    """Extract key sentences from body sections for summary."""
    key_sections = ["## 定义", "## 适用场景", "## 常见错误", "## 生成约束"]
    snippets = []
    for section in key_sections:
        m = re.search(
            rf"^{re.escape(section)}\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL | re.MULTILINE
        )
        if m:
            text = m.group(1).strip()[:150]
            snippets.append(text)
    summary = " ".join(snippets)
    return summary[:max_chars]


# ── Build pipeline ──────────────────────────────────────────

CARDS_JSONL = PROJECT_ROOT / "cards" / "cards.jsonl"
CARDS_DB = PROJECT_ROOT / "knowledge_base" / "cards.sqlite3"


def build_cards(jsonl_path: Optional[Path] = None, db_path: Optional[Path] = None):
    """Full build pipeline: parse cards → validate → JSONL → SQLite."""
    jsonl_path = jsonl_path or CARDS_JSONL
    db_path = db_path or CARDS_DB

    card_files = sorted(METHODS_ROOT.glob("method_*.md"))
    if not card_files:
        return {"status": "error", "message": "No method cards found"}

    records = []
    errors = []
    for file_path in card_files:
        try:
            card = parse_card(file_path)
            issues = validate_card(card)
            if issues:
                errors.append({"file": file_path.name, "issues": issues})
                continue
            records.append(card_to_jsonl_record(card))
        except Exception as exc:
            errors.append({"file": file_path.name, "error": str(exc)})

    # Write JSONL
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(_json_dumps(rec) + "\n")

    # Write SQLite
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_cards_schema(conn)
    _upsert_cards(conn, records)
    _build_method_relations(conn, records)
    conn.close()

    try:
        from src.consistency_engine import _invalidate_methods_pattern_cache
        _invalidate_methods_pattern_cache()
    except Exception:
        pass

    return {
        "status": "ok",
        "cards_processed": len(records),
        "cards_failed": len(errors),
        "jsonl": str(jsonl_path),
        "sqlite": str(db_path),
        "errors": errors,
    }


def _init_cards_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            short_name TEXT,
            category TEXT,
            phase TEXT,
            disciplines TEXT,
            domains TEXT,
            applicable_sections TEXT,
            aliases TEXT,
            pairs_with TEXT,
            requires TEXT,
            conflicts_with TEXT,
            difficulty TEXT,
            data_type TEXT,
            outputs TEXT,
            risk_tags TEXT,
            source_type TEXT,
            scope TEXT,
            status TEXT,
            version TEXT,
            frontmatter_json TEXT,
            body_markdown TEXT,
            body_summary TEXT,
            searchable_text TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS method_relations (
            source_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            PRIMARY KEY (source_id, relation_type, target_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS card_risk_relations (
            card_id TEXT NOT NULL,
            risk_id TEXT NOT NULL,
            relation_type TEXT NOT NULL DEFAULT 'tagged',
            PRIMARY KEY (card_id, risk_id)
        )
    """)
    conn.commit()


def _upsert_cards(conn: sqlite3.Connection, records: List[Dict[str, Any]]):
    stmt = """
        INSERT OR REPLACE INTO cards (
            id, type, name, short_name, category, phase, disciplines, domains,
            applicable_sections, aliases, pairs_with, requires, conflicts_with,
            difficulty, data_type, outputs, risk_tags, source_type, scope, status,
            version, frontmatter_json, body_markdown, body_summary, searchable_text, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for rec in records:
        conn.execute(
            stmt,
            (
                rec["id"], rec["type"], rec["name"], rec.get("short_name", ""),
                rec.get("category", ""), json.dumps(rec.get("phase", []), ensure_ascii=False),
                json.dumps(rec.get("disciplines", []), ensure_ascii=False), json.dumps(rec.get("domains", []), ensure_ascii=False),
                json.dumps(rec.get("applicable_sections", []), ensure_ascii=False), json.dumps(rec.get("aliases", []), ensure_ascii=False),
                json.dumps(rec.get("pairs_with", []), ensure_ascii=False), json.dumps(rec.get("requires", []), ensure_ascii=False),
                json.dumps(rec.get("conflicts_with", []), ensure_ascii=False), rec.get("difficulty", ""),
                json.dumps(rec.get("data_type", []), ensure_ascii=False), json.dumps(rec.get("outputs", []), ensure_ascii=False),
                json.dumps(rec.get("risk_tags", []), ensure_ascii=False), rec.get("source_type", ""),
                rec.get("scope", ""), rec.get("status", ""), rec.get("version", ""),
                rec.get("frontmatter_json", ""), rec.get("body_markdown", ""),
                rec.get("body_summary", ""), rec.get("searchable_text", ""),
                rec.get("updated_at", ""),
            ),
        )
    conn.commit()


def _build_method_relations(conn: sqlite3.Connection, records: List[Dict[str, Any]]):
    conn.execute("DELETE FROM method_relations")
    for rec in records:
        source_id = rec["id"]
        for target in rec.get("pairs_with", []):
            conn.execute(
                "INSERT OR IGNORE INTO method_relations VALUES (?, ?, ?)",
                (source_id, "pairs_with", target),
            )
        for target in rec.get("requires", []):
            conn.execute(
                "INSERT OR IGNORE INTO method_relations VALUES (?, ?, ?)",
                (source_id, "requires", target),
            )
    conn.commit()


def card_to_jsonl_record(card: Dict[str, Any]) -> Dict[str, Any]:
    """Convert parsed card to JSONL record."""
    fm = card["frontmatter"]
    body = card["body"]
    searchable = build_searchable_text(fm, body)
    body_summary = _extract_body_summary(body)

    return {
        "id": fm["id"],
        "type": fm["type"],
        "name": fm["name"],
        "short_name": fm.get("short_name", ""),
        "category": fm.get("category", ""),
        "phase": fm.get("phase", []),
        "disciplines": fm.get("disciplines", []),
        "domains": fm.get("domains", []),
        "applicable_sections": fm.get("applicable_sections", []),
        "aliases": fm.get("aliases", []),
        "pairs_with": fm.get("pairs_with", []),
        "requires": fm.get("requires", []),
        "conflicts_with": fm.get("conflicts_with", []),
        "difficulty": fm.get("difficulty", ""),
        "data_type": fm.get("data_type", []),
        "outputs": fm.get("outputs", []),
        "risk_tags": fm.get("risk_tags", []),
        "source_type": fm.get("source_type", "builtin"),
        "scope": fm.get("scope", "platform"),
        "status": fm.get("status", "draft"),
        "version": str(fm.get("version", "1.0.0")),
        "frontmatter_json": _json_dumps(fm, sort_keys=True),
        "body_markdown": body,
        "body_summary": body_summary,
        "searchable_text": searchable,
        "updated_at": fm.get("updated_at") or datetime.now().isoformat()[:10],
    }


# ── Risk card build pipeline ─────────────────────────────────

def risk_card_to_jsonl_record(card: Dict[str, Any]) -> Dict[str, Any]:
    """Convert parsed risk card to JSONL record."""
    fm = card["frontmatter"]
    body = card["body"]
    searchable = _build_risk_searchable(fm, body)

    return {
        "id": fm["id"],
        "type": "risk_card",
        "name": fm["name"],
        "severity": fm.get("severity", "medium"),
        "category": fm.get("category", ""),
        "check_stage": fm.get("check_stage", "post_generation"),
        "disciplines": fm.get("disciplines", []),
        "applicable_chapters": fm.get("applicable_chapters", []),
        "trigger_conditions": fm.get("trigger_conditions", []),
        "check_questions": fm.get("check_questions", []),
        "fix_strategy": fm.get("fix_strategy", []),
        "related_method_tags": fm.get("related_method_tags", []),
        "source_type": fm.get("source_type", "builtin"),
        "scope": fm.get("scope", "platform"),
        "status": fm.get("status", "draft"),
        "version": str(fm.get("version", "1.0.0")),
        "frontmatter_json": _json_dumps(fm, sort_keys=True),
        "body_markdown": body,
        "searchable_text": searchable,
        "updated_at": fm.get("updated_at") or datetime.now().isoformat()[:10],
    }


def _build_risk_searchable(fm: Dict[str, Any], body: str) -> str:
    lines = [
        f"风险名称: {fm.get('name', '')}",
        f"严重程度: {fm.get('severity', '')}",
        f"风险类别: {fm.get('category', '')}",
        f"检查阶段: {fm.get('check_stage', '')}",
        f"适用章节: {'、'.join(fm.get('applicable_chapters', []))}",
        f"触发条件: {'; '.join(fm.get('trigger_conditions', []))}",
    ]
    # Extract key sentences
    for section in ["## 触发条件", "## 检查问题", "## 修复策略"]:
        m = re.search(
            rf"^{re.escape(section)}\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL | re.MULTILINE
        )
        if m:
            lines.append(m.group(1).strip()[:300])
    return "\n".join(lines)


def _init_risks_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS risk_cards (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL DEFAULT 'risk_card',
            name TEXT NOT NULL,
            severity TEXT,
            category TEXT,
            check_stage TEXT,
            disciplines TEXT,
            applicable_chapters TEXT,
            trigger_conditions TEXT,
            check_questions TEXT,
            fix_strategy TEXT,
            related_method_tags TEXT,
            source_type TEXT,
            scope TEXT,
            status TEXT,
            version TEXT,
            frontmatter_json TEXT,
            body_markdown TEXT,
            searchable_text TEXT,
            updated_at TEXT
        )
    """)


def build_risks(jsonl_path: Optional[Path] = None, db_path: Optional[Path] = None):
    """Build risk cards: parse → validate → JSONL → SQLite."""
    jsonl_path = jsonl_path or CARDS_ROOT / "risks.jsonl"
    db_path = db_path or CARDS_DB

    risk_files = sorted(RISKS_ROOT.glob("risk_*.md"))
    if not risk_files:
        return {"status": "error", "message": "No risk cards found"}

    records = []
    errors = []
    for file_path in risk_files:
        try:
            card = parse_card(file_path)
            issues = validate_card(card, card_type="risk_card")
            if issues:
                errors.append({"file": file_path.name, "issues": issues})
                continue
            records.append(risk_card_to_jsonl_record(card))
        except Exception as exc:
            errors.append({"file": file_path.name, "error": str(exc)})

    # Write JSONL
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(_json_dumps(rec) + "\n")

    # Write SQLite
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_risks_table(conn)
    _upsert_risks(conn, records)
    conn.close()

    return {
        "status": "ok",
        "cards_processed": len(records),
        "cards_failed": len(errors),
        "jsonl": str(jsonl_path),
        "sqlite": str(db_path),
        "errors": errors,
    }


def _upsert_risks(conn: sqlite3.Connection, records: List[Dict[str, Any]]):
    stmt = """
        INSERT OR REPLACE INTO risk_cards (
            id, type, name, severity, category, check_stage, disciplines,
            applicable_chapters, trigger_conditions, check_questions, fix_strategy,
            related_method_tags, source_type, scope, status, version,
            frontmatter_json, body_markdown, searchable_text, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for rec in records:
        conn.execute(stmt, (
            rec["id"], rec["type"], rec["name"], rec.get("severity", ""),
            rec.get("category", ""), rec.get("check_stage", ""),
            _json_dumps(rec.get("disciplines", [])),
            _json_dumps(rec.get("applicable_chapters", [])),
            _json_dumps(rec.get("trigger_conditions", [])),
            _json_dumps(rec.get("check_questions", [])),
            _json_dumps(rec.get("fix_strategy", [])),
            _json_dumps(rec.get("related_method_tags", [])),
            rec.get("source_type", ""), rec.get("scope", ""),
            rec.get("status", ""), rec.get("version", ""),
            rec.get("frontmatter_json", ""), rec.get("body_markdown", ""),
            rec.get("searchable_text", ""), rec.get("updated_at", ""),
        ))
    conn.commit()
