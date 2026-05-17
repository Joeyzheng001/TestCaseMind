"""
研究方向模板构建器。

把本地向量库中的论文资料预处理成方向模板，供大纲生成优先使用。
模板关注章节命名、常用方法、典型资料来源，而不是临时把大量原文塞给模型。
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTOR_DB = PROJECT_ROOT / "knowledge_base" / "vector_store.sqlite3"
TEMPLATE_DIR = PROJECT_ROOT / "knowledge_base" / "templates" / "domain_templates"


# 领域概念关键词（纯学科术语，方法名从注册中心动态补充）
_DOMAIN_CONCEPT_KEYWORDS: Dict[str, List[str]] = {
    "quality_management": ["质量", "质量管理", "质量改进", "质量改善"],
    "risk_management": ["风险", "风险管理", "风险评估", "安全风险", "反欺诈"],
    "schedule_management": ["进度", "工期", "排产", "计划管理", "延误"],
    "requirements_management": ["需求管理", "需求分析", "产品需求", "需求变更"],
    "process_optimization": ["流程优化", "流程改善", "流程改进", "开发流程"],
    "cost_management": ["成本", "成本管理", "成本控制", "成本优化", "预算"],
    "supply_chain_logistics": ["供应链", "物流", "配送", "库存", "采购", "供应商"],
}

_DOMAIN_NAMES: Dict[str, str] = {
    "quality_management": "质量管理",
    "risk_management": "风险管理",
    "schedule_management": "进度管理",
    "requirements_management": "需求管理",
    "process_optimization": "流程优化",
    "cost_management": "成本管理",
    "supply_chain_logistics": "供应链与物流",
}

def _build_domain_rules() -> Dict[str, Dict[str, Any]]:
    """从注册中心动态构建 DOMAIN_RULES（领域概念 + 方法名/别名）。"""
    from src.method_registry import get_registry as _dr_reg
    _reg = _dr_reg()
    _domains_map = _reg.get_domain_to_names()
    _aliases_map = _reg.get_aliases()
    _rules: Dict[str, Dict[str, Any]] = {}
    for _domain_id, _name in _DOMAIN_NAMES.items():
        _kws = list(_DOMAIN_CONCEPT_KEYWORDS.get(_domain_id, []))
        for _method_name in _domains_map.get(_domain_id, []):
            if _method_name not in _kws:
                _kws.append(_method_name)
            for _alias in _aliases_map.get(_method_name, []):
                if _alias not in _kws:
                    _kws.append(_alias)
        _rules[_domain_id] = {"name": _name, "keywords": _kws}
    return _rules

DOMAIN_RULES: Dict[str, Dict[str, Any]] = _build_domain_rules()

def _get_method_keywords_list() -> List[str]:
    """从注册中心动态加载全部方法名作为关键词列表。"""
    from src.method_registry import get_all_method_names
    return get_all_method_names()


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", "", title or "")
    title = re.sub(r"[.．·。]{2,}\d*$", "", title)
    title = re.sub(r"\.{2,}.*$", "", title)
    title = re.sub(r"\d+$", "", title)
    title = re.sub(r"[_+\-—].*$", "", title)
    return title.strip()


def _iter_documents() -> Iterable[Dict[str, Any]]:
    if not VECTOR_DB.exists():
        return []
    connection = sqlite3.connect(VECTOR_DB)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT d.id, d.path, d.title, group_concat(c.content, '\n') AS sample
        FROM documents d
        LEFT JOIN chunks c ON c.document_id = d.id AND c.chunk_index <= 8
        GROUP BY d.id, d.path, d.title
        """
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


def _domains_for(text: str) -> List[str]:
    lowered = text.lower()
    domains = []
    for domain_id, rule in DOMAIN_RULES.items():
        if any(keyword.lower() in lowered for keyword in rule["keywords"]):
            domains.append(domain_id)
    return domains


def _extract_methods(text: str) -> List[str]:
    methods = []
    lowered = text.lower()
    _method_keywords = _get_method_keywords_list()
    for method in _method_keywords:
        if method.lower() in lowered:
            methods.append(method)
    return methods


def _extract_headings(text: str) -> Dict[str, List[str]]:
    chapter_pattern = re.compile(r"第[一二三四五六七八九十\d]+章\s*([^\n\r]{2,40})")
    section_pattern = re.compile(r"(?:^|\n)\s*\d+\.\d+\s+([^\n\r]{2,36})")
    chapters = [_clean_title(match.group(1)) for match in chapter_pattern.finditer(text or "")]
    sections = [_clean_title(match.group(1)) for match in section_pattern.finditer(text or "")]
    return {
        "chapters": [item for item in chapters if item][:12],
        "sections": [item for item in sections if item][:40],
    }


def build_domain_templates() -> Dict[str, Any]:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    aggregates: Dict[str, Dict[str, Any]] = {
        domain_id: {
            "domain_id": domain_id,
            "name": rule["name"],
            "source_count": 0,
            "sources": [],
            "chapter_counter": Counter(),
            "section_counter": Counter(),
            "method_counter": Counter(),
        }
        for domain_id, rule in DOMAIN_RULES.items()
    }

    for document in _iter_documents():
        title = _clean_title(document.get("title") or Path(document.get("path", "")).stem)
        path = document.get("path", "")
        sample = document.get("sample") or ""
        text = f"{title}\n{path}\n{sample[:6000]}"
        domains = _domains_for(text)
        if not domains:
            continue
        headings = _extract_headings(sample)
        methods = _extract_methods(text)

        for domain_id in domains:
            item = aggregates[domain_id]
            item["source_count"] += 1
            if len(item["sources"]) < 12:
                item["sources"].append({"title": title, "path": path})
            item["chapter_counter"].update(headings["chapters"])
            item["section_counter"].update(headings["sections"])
            item["method_counter"].update(methods)

    index = {"templates": []}
    for domain_id, item in aggregates.items():
        template = {
            "domain_id": domain_id,
            "name": item["name"],
            "source_count": item["source_count"],
            "sources": item["sources"],
            "chapter_naming_patterns": [
                {"title": title, "count": count}
                for title, count in item["chapter_counter"].most_common(24)
            ],
            "section_naming_patterns": [
                {"title": title, "count": count}
                for title, count in item["section_counter"].most_common(36)
            ],
            "method_patterns": [
                {"name": name, "count": count}
                for name, count in item["method_counter"].most_common(24)
            ],
        }
        path = TEMPLATE_DIR / f"{domain_id}.json"
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        index["templates"].append(
            {
                "domain_id": domain_id,
                "name": item["name"],
                "source_count": item["source_count"],
                "path": str(path.relative_to(PROJECT_ROOT)),
            }
        )

    (TEMPLATE_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return index


def load_domain_template(domain_id: str) -> Dict[str, Any]:
    path = TEMPLATE_DIR / f"{domain_id}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    result = build_domain_templates()
    print(json.dumps(result, ensure_ascii=False, indent=2))
