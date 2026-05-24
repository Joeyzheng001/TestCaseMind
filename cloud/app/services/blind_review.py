"""Blind review service — risk checking engine for cloud."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _get_cards_db_path() -> Path:
    """Get risk cards database path. Configurable via env for cloud deployment."""
    env_path = os.getenv("THESISMIND_CARDS_DB")
    if env_path:
        return Path(env_path)
    # Fallback: look relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    return project_root / "knowledge_base" / "cards.sqlite3"


def check_blind_review(payload: dict) -> dict:
    """Run blind review risk check. Supports single-chapter or multi-chapter scan."""
    from src.risk_checker import run_risk_scan, run_method_risk_scan, run_formula_check, format_risk_report

    methods = payload.get("methods", [])
    severity_filter = payload.get("severity_filter")
    category_filter = payload.get("category_filter")

    chapters = payload.get("chapters")
    if chapters:
        all_results = []
        total_triggered = 0
        chapter_results = []
        for ch in chapters:
            content = ch.get("content", "")
            if not content.strip():
                continue
            if methods:
                scan = run_method_risk_scan(content, methods, chapter_title=ch.get("title", ""))
            else:
                scan = run_risk_scan(
                    content,
                    chapter_title=ch.get("title", ""),
                    chapter_number=ch.get("number", ""),
                    severity_filter=severity_filter,
                    category_filter=category_filter,
                )
            triggered = [r for r in scan.get("results", []) if r["triggered"]]
            all_results.extend(scan.get("results", []))
            total_triggered += len(triggered)
            chapter_results.append({
                "chapter_title": ch.get("title", ""),
                "chapter_number": ch.get("number", ""),
                "total_risks": scan.get("total_risks", 0),
                "triggered": len(triggered),
                "results": scan.get("results", []),
            })

        if methods:
            for ch_result in chapter_results:
                ch_title = ch_result.get("chapter_title", "")
                ch_content = next(
                    (c.get("content", "") for c in chapters if c.get("title", "") == ch_title),
                    "",
                )
                if ch_content.strip():
                    formula_result = run_formula_check(ch_content, methods, chapter_title=ch_title)
                    for fr in formula_result.get("results", []):
                        all_results.append(fr)
                        if fr.get("triggered"):
                            total_triggered += 1
                    ch_result.setdefault("formula_check", formula_result)

        seen_ids = set()
        unique_results = []
        for r in all_results:
            if r["risk_id"] not in seen_ids:
                seen_ids.add(r["risk_id"])
                unique_results.append(r)

        critical_count = len([r for r in unique_results if r.get("triggered") and r.get("severity") == "critical"])
        high_count = len([r for r in unique_results if r.get("triggered") and r.get("severity") == "high"])

        return {
            "status": "ok",
            "total_risks": len(unique_results),
            "triggered": total_triggered,
            "critical_count": critical_count,
            "high_count": high_count,
            "results": unique_results,
            "chapter_results": chapter_results,
            "summary": f"全文扫描触发 {total_triggered} 项风险（致命 {critical_count}，高 {high_count}）",
        }

    # Single chapter scan
    content = payload.get("content", "")
    if not content:
        return {"status": "error", "message": "请提供待检查的内容"}

    chapter_title = payload.get("chapter_title", "")
    chapter_number = payload.get("chapter_number", "")

    if methods:
        scan = run_method_risk_scan(content, methods, chapter_title=chapter_title)
        formula_result = run_formula_check(content, methods, chapter_title=chapter_title)
        scan["results"].extend(formula_result.get("results", []))
        scan["triggered"] = len([r for r in scan["results"] if r.get("triggered")])
        scan["total_risks"] = len(scan["results"])
        scan["formula_check"] = formula_result
        scan["summary"] = f"方法风险检查 {scan['total_risks']} 项，触发 {scan['triggered']} 项"
    else:
        scan = run_risk_scan(
            content,
            chapter_title=chapter_title,
            chapter_number=chapter_number,
            severity_filter=severity_filter,
            category_filter=category_filter,
        )

    return {
        **scan,
        "formatted_report": format_risk_report(scan),
    }
