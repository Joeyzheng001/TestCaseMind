"""
统一方法注册中心 — 所有方法名、别名、分类、阶段、领域映射的唯一数据源。

从 cards.sqlite3 动态加载，在任何模块中替代硬编码的方法名字典。
修改方法卡片后只需重建 cards DB + 调用 reload()。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from threading import Lock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_DB_PATH = PROJECT_ROOT / "knowledge_base" / "cards.sqlite3"

_lock = Lock()
_registry: Optional["MethodRegistry"] = None


class MethodRegistry:
    """方法卡片的内存索引，一次性从 cards.sqlite3 加载全部。"""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or CARDS_DB_PATH
        self._names: List[str] = []
        self._aliases: Dict[str, List[str]] = {}          # canonical → [aliases]
        self._alias_to_canon: Dict[str, str] = {}          # alias → canonical
        self._categories: Dict[str, List[str]] = {}        # category → [names]
        self._name_to_category: Dict[str, str] = {}        # name → category
        self._phases: Dict[str, List[str]] = {}            # name → [phases]
        self._phase_to_names: Dict[str, List[str]] = {}    # phase → [names]
        self._domains: Dict[str, List[str]] = {}           # name → [domain_ids]
        self._domain_to_names: Dict[str, List[str]] = {}   # domain_id → [names]
        self._keywords: Dict[str, List[str]] = {}          # name → [search keywords]
        self._tool_names: Set[str] = set()                 # research tool methods
        self._catalog: List[Dict[str, Any]] = []           # full catalog for API
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with _lock:
            if self._loaded:
                return
            self._load()
            self._loaded = True

    def _load(self) -> None:
        if not self._db_path.exists():
            return

        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM cards WHERE type='method_card'"
        ).fetchall()
        conn.close()

        for r in rows:
            name = r["name"]
            self._names.append(name)
            aliases = self._safe_json(r["aliases"]) or []
            self._aliases[name] = aliases
            for a in aliases:
                a_key = a.strip().lower()
                if a_key not in self._alias_to_canon:
                    self._alias_to_canon[a_key] = name
            # Also map canonical name itself
            self._alias_to_canon[name.strip().lower()] = name

            category = (r["category"] or "").strip()
            if category:
                self._categories.setdefault(category, []).append(name)
                self._name_to_category[name] = category

            phases = self._safe_json(r["phase"]) or []
            self._phases[name] = phases
            for p in phases:
                self._phase_to_names.setdefault(p, []).append(name)

            domains = self._safe_json(r["domains"]) or []
            self._domains[name] = domains
            for d in domains:
                self._domain_to_names.setdefault(d, []).append(name)

            # Build search keywords: canonical name + aliases + short_name
            kw = [name]
            kw.extend(aliases)
            short = (r["short_name"] or "").strip()
            if short and short != name:
                kw.append(short)
            self._keywords[name] = list({k.strip() for k in kw if k.strip()})

            # Research tool detection from YAML frontmatter
            fm_json = r["frontmatter_json"] if "frontmatter_json" in r.keys() else None
            fm = self._safe_json(fm_json) or {}
            if fm.get("method_role") == "research_tool":
                self._tool_names.add(name)

            self._catalog.append({
                "id": r["id"],
                "name": name,
                "short_name": short or name,
                "aliases": aliases,
                "category": category or "",
                "phases": phases,
                "domains": domains,
                "pairs_with": self._safe_json(r["pairs_with"]) or [],
                "requires": self._safe_json(r["requires"]) or [],
                "conflicts_with": self._safe_json(r["conflicts_with"]) or [],
            })

    @staticmethod
    def _safe_json(val: Any) -> Any:
        if val is None or val == "":
            return None
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        return val

    # ── Public API ──────────────────────────────────────

    def get_all_names(self) -> List[str]:
        self._ensure_loaded()
        return list(self._names)

    def get_aliases(self) -> Dict[str, List[str]]:
        """canonical name → list of aliases (includes canonical name itself)."""
        self._ensure_loaded()
        return dict(self._aliases)

    def get_alias_map(self) -> Dict[str, str]:
        """any alias (lowercased) → canonical name."""
        self._ensure_loaded()
        return dict(self._alias_to_canon)

    def get_categories(self) -> Dict[str, List[str]]:
        """category → list of canonical names."""
        self._ensure_loaded()
        return {k: list(v) for k, v in self._categories.items()}

    def get_category_of(self, name: str) -> str:
        self._ensure_loaded()
        return self._name_to_category.get(name, "")

    def get_phases(self) -> Dict[str, List[str]]:
        """canonical name → list of phases."""
        self._ensure_loaded()
        return dict(self._phases)

    def get_phase_to_names(self) -> Dict[str, List[str]]:
        """phase → list of canonical names."""
        self._ensure_loaded()
        return {k: list(v) for k, v in self._phase_to_names.items()}

    def get_domains(self) -> Dict[str, List[str]]:
        """canonical name → list of domain IDs."""
        self._ensure_loaded()
        return dict(self._domains)

    def get_domain_to_names(self) -> Dict[str, List[str]]:
        """domain_id → list of canonical names."""
        self._ensure_loaded()
        return {k: list(v) for k, v in self._domain_to_names.items()}

    def get_keywords(self) -> Dict[str, List[str]]:
        """canonical name → list of search keywords (name + aliases + short_name)."""
        self._ensure_loaded()
        return dict(self._keywords)

    def get_tool_names(self) -> Set[str]:
        """Methods tagged as research tools (问卷调查法, 文献研究法, etc.)."""
        self._ensure_loaded()
        return set(self._tool_names)

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Full method catalog for API/frontend consumption."""
        self._ensure_loaded()
        return list(self._catalog)

    def resolve(self, name_or_alias: str) -> Optional[str]:
        """Resolve any name/alias to canonical name. Returns None if unknown."""
        self._ensure_loaded()
        return self._alias_to_canon.get(name_or_alias.strip().lower())

    def resolve_list(self, names: List[str]) -> List[str]:
        """Resolve a list of names/aliases to unique canonical names."""
        self._ensure_loaded()
        resolved: List[str] = []
        for n in names:
            canon = self.resolve(n)
            if canon and canon not in resolved:
                resolved.append(canon)
        return resolved


def get_registry(db_path: Optional[Path] = None) -> MethodRegistry:
    """Get or create the global method registry (lazy, thread-safe)."""
    global _registry
    if _registry is None:
        with _lock:
            if _registry is None:
                _registry = MethodRegistry(db_path)
    return _registry


def reload_registry(db_path: Optional[Path] = None) -> MethodRegistry:
    """Force reload from DB (call after rebuilding cards)."""
    global _registry
    with _lock:
        _registry = MethodRegistry(db_path)
    return _registry


# ── Convenience module-level functions (mirror old API) ──

def get_all_method_names() -> List[str]:
    return get_registry().get_all_names()

def get_method_aliases() -> Dict[str, List[str]]:
    return get_registry().get_aliases()

def get_method_alias_map() -> Dict[str, str]:
    return get_registry().get_alias_map()

def get_method_categories() -> Dict[str, List[str]]:
    return get_registry().get_categories()

def get_method_phases() -> Dict[str, List[str]]:
    return get_registry().get_phases()

def get_phase_to_methods() -> Dict[str, List[str]]:
    return get_registry().get_phase_to_names()

def get_method_domains() -> Dict[str, List[str]]:
    return get_registry().get_domains()

def get_domain_to_methods() -> Dict[str, List[str]]:
    return get_registry().get_domain_to_names()

def get_method_keywords() -> Dict[str, List[str]]:
    return get_registry().get_keywords()

def get_research_tool_methods() -> Set[str]:
    return get_registry().get_tool_names()

def get_method_catalog() -> List[Dict[str, Any]]:
    return get_registry().get_catalog()

def resolve_method(name: str) -> Optional[str]:
    return get_registry().resolve(name)

def resolve_methods(names: List[str]) -> List[str]:
    return get_registry().resolve_list(names)
