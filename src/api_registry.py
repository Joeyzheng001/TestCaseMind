"""Central API and feature authorization registry.

Keeping this map outside the HTTP handler makes route authorization reviewable
and testable. New `/api/` endpoints should be registered here before handlers
are added in `web_server.py`.
"""

from __future__ import annotations

from typing import Dict, Optional, Set, Tuple


# Menu/action id -> required feature. None means the menu is intentionally public.
MENU_FEATURE_MAP: Dict[str, Optional[str]] = {
    # 01-07 basic workflow
    "setup": "workflow",
    "paper_info": "workflow",
    "methods": "workflow",
    "framework": "workflow",
    "outline": "workflow",
    "citations": "workflow",
    "writing": "workflow",
    # 08 paid add-ons
    "proposal": "advanced",
    "ppt_proposal": "advanced",
    "ppt_midterm": "advanced",
    "ppt_defense": "advanced",
    "table_generator": "advanced",
    # 09 VIP services
    "blind_review": "vip",
    "aigc_check": "vip",
    "aigc_reduce": "vip",
    # System administration
    "init_kb": "admin",
    "license_generate": "admin",
    "license_history": "admin",
    # Paper/citation management
    "paper_manager": "advanced",
    # License page is intentionally visible.
    "license": None,
    # API aliases
    "workflow": "workflow",
    "advanced": "advanced",
    "vip": "vip",
    "admin": "admin",
}


PUBLIC_API_RULES: Set[Tuple[str, str]] = {
    ("GET", "/api/config"),
    ("GET", "/api/license/status"),
    ("POST", "/api/license/activate"),
    ("POST", "/api/license/trial"),
}


API_PREFIX_MENU_MAP: Dict[str, str] = {
    "/api/methodologies": "methods",
    "/api/citation-cards": "paper_manager",
    "/api/tasks/": "workflow",
}


API_MENU_MAP: Dict[str, str] = {
    "/api/config": "setup",
    "/api/outlines": "outline",
    "/api/export/docx": "writing",
    "/api/export/pdf": "writing",
    "/api/projects": "paper_info",
    "/api/projects/create": "paper_info",
    "/api/projects/switch": "paper_info",
    "/api/project-context": "paper_info",
    "/api/framework": "framework",
    "/api/framework/save": "framework",
    "/api/outline": "outline",
    "/api/outline/save": "outline",
    "/api/subsections": "outline",
    "/api/citations/generate": "citations",
    "/api/citations/save": "citations",
    "/api/citations/dedup": "citations",
    "/api/expand": "writing",
    "/api/rewrite": "writing",
    "/api/drafts/save": "writing",
    "/api/chat": "workflow",
    "/api/chat/test": "workflow",
    "/api/method-supplement": "methods",
    "/api/method-assignments/save": "methods",
    "/api/methods/save": "methods",
    "/api/workspace": "writing",
    "/api/workspace/value": "writing",
    "/api/workspace/save": "writing",
    "/api/workspace/save-checklists": "writing",
    "/api/table/generate": "table_generator",
    "/api/table/generate-from-text": "table_generator",
    "/api/domain-templates/build": "init_kb",
    "/api/citation-index/build": "init_kb",
    "/api/proposal": "proposal",
    "/api/proposal/export": "proposal",
    "/api/proposal/save": "proposal",
    "/api/ppt/generate": "ppt_proposal",
    "/api/blind-review-check": "blind_review",
    "/api/aigc/check": "aigc_check",
    "/api/aigc/reduce": "aigc_reduce",
    "/api/knowledge-base/init": "init_kb",
    "/api/knowledge_base/init": "init_kb",
    "/api/papers/stats": "paper_manager",
    "/api/papers/list": "paper_manager",
    "/api/papers/detail": "paper_manager",
    "/api/papers/upload": "paper_manager",
    "/api/papers/pipeline/start": "paper_manager",
    "/api/papers/delete": "paper_manager",
    "/api/paper-library": "citations",
    "/api/paper-library/stats": "paper_manager",
    "/api/paper-library/papers": "paper_manager",
    "/api/paper-library/sync": "paper_manager",
    "/api/paper-library/add": "paper_manager",
    "/api/paper-library/remove": "paper_manager",
    "/api/paper-library/update": "paper_manager",
    "/api/best-practices": "workflow",
    "/api/license/generate": "license_generate",
    "/api/license/history": "license_history",
}


OUTLINE_TASK_KIND = "outline"
KB_INIT_TASK_KIND = "knowledge_base_init"
CITATION_GENERATE_TASK_KIND = "citation_generate"
PAPER_PIPELINE_TASK_KIND = "paper_pipeline"

TASK_PERMISSION_BY_KIND = {
    OUTLINE_TASK_KIND: "outline",
    KB_INIT_TASK_KIND: "init_kb",
    CITATION_GENERATE_TASK_KIND: "citations",
    PAPER_PIPELINE_TASK_KIND: "paper_manager",
}


def normalize_api_path(api_path: str) -> str:
    return (api_path or "/").split("?", 1)[0].rstrip("/") or "/"


def is_public_api(api_path: str, method: str = "GET") -> bool:
    return ((method or "GET").upper(), normalize_api_path(api_path)) in PUBLIC_API_RULES


def resolve_api_menu(api_path: str, method: str = "GET") -> Optional[str]:
    path = normalize_api_path(api_path)
    if is_public_api(path, method):
        return None
    for prefix, menu_id in API_PREFIX_MENU_MAP.items():
        if path.startswith(prefix):
            return menu_id
    return API_MENU_MAP.get(path)


def is_registered_api_path(api_path: str) -> bool:
    path = normalize_api_path(api_path)
    if path in API_MENU_MAP:
        return True
    if any(path == public_path for _, public_path in PUBLIC_API_RULES):
        return True
    return any(
        path == prefix.rstrip("/") or path.startswith(prefix)
        for prefix in API_PREFIX_MENU_MAP
    )
