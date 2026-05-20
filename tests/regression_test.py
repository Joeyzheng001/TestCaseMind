#!/usr/bin/env python3
"""ThesisMind 全流程回归测试

覆盖：项目配置 → 方法论选择 → 框架生成 → 提纲生成 →
      引用生成 → 扩写 → 数据流与一致性校验

用法:
    python3 tests/regression_test.py [--base-url http://127.0.0.1:8222]
    python3 tests/regression_test.py --quick   # 跳过 LLM 步骤，仅测数据一致性

每次大改动、大版本发布前必须全部通过。
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 测试配置 ──
BASE_URL = "http://127.0.0.1:8222"
TIMEOUT = 30
LLM_TIMEOUT = 180  # LLM 调用可能需要较长时间

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭️  SKIP"
WARN = "⚠️  WARN"

_results: List[Dict] = []


def record(name: str, passed: bool, detail: str = "", skipped: bool = False):
    status = SKIP if skipped else (PASS if passed else FAIL)
    entry = {"name": name, "status": status, "passed": passed, "detail": detail, "skipped": skipped}
    _results.append(entry)
    print(f"  {status}  {name}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"         {line}")


def api(path: str, body: Optional[Dict] = None, method: Optional[str] = None, timeout: int = TIMEOUT) -> Dict:
    """调用 API 端点。"""
    url = f"{BASE_URL}{path}"
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method or ("POST" if body else "GET"))
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"_error": True, "status_code": e.code, "body": body}
    except Exception as e:
        return {"_error": True, "exception": str(e)}


def assert_ok(result: Dict, context: str = "") -> Tuple[bool, str]:
    """检查 API 是否返回了 ok / 成功状态。"""
    if result.get("_error"):
        return False, f"{context}: HTTP {result.get('status_code', '?')} — {result.get('body', result.get('exception', ''))}"
    if result.get("status") == "ok" or result.get("status") in ("queued",):
        return True, context
    # 部分接口不返回 status 字段，有数据即为成功
    if isinstance(result, dict) and len(result) > 0:
        return True, context
    return False, f"{context}: unexpected response {json.dumps(result, ensure_ascii=False)[:200]}"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 基础设施测试
# ═══════════════════════════════════════════════════════════════════════════════

def test_health():
    print("\n── 1. 基础设施 ──")
    r = api("/api/workspace")
    ok, detail = assert_ok(r, "GET /api/workspace")
    record("Server health check (workspace)", ok, detail)
    return ok


def test_config():
    r = api("/api/config")
    has_model = bool(r.get("model") or r.get("provider"))
    record("GET /api/config", has_model, f"provider={r.get('provider')}, model={r.get('model')}")
    return r


def test_license():
    r = api("/api/license/status")
    ok = "license" in r or "status" in r or "error" not in str(r).lower()
    record("GET /api/license/status", ok, json.dumps(r, ensure_ascii=False)[:150])
    return ok


def test_methodologies():
    r = api("/api/methodologies")
    items = r.get("items", r) if isinstance(r, dict) else r
    ok = isinstance(items, list) and len(items) > 0
    record("GET /api/methodologies", ok, f"{len(items)} methods loaded" if ok else "empty or error")
    return items


def test_projects():
    r = api("/api/projects")
    ok = isinstance(r, dict) and "projects" in r
    record("GET /api/projects", ok, f"{len(r.get('projects', []))} projects" if ok else "")
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 项目配置流程
# ═══════════════════════════════════════════════════════════════════════════════

def test_project_creation():
    print("\n── 2. 项目配置 ──")
    # 创建测试项目
    topic = f"回归测试项目_{int(time.time())}"
    r = api("/api/projects/create", {"topic": topic})
    ok, detail = assert_ok(r, "POST /api/projects/create")
    record("Create project", ok, detail)
    project_id = r.get("project", {}).get("id") if ok else None
    return project_id


def test_project_context(project_id: Optional[str]):
    if not project_id:
        record("Set project context", False, "No project_id from creation step", skipped=True)
        return

    # 切换到这个项目
    api("/api/projects/switch", {"project_id": project_id})

    # 设置项目背景和思路
    context = {
        "project_context": "## 项目背景\n这是自动化回归测试的项目背景描述。\n\n## 论文思路\n采用质量管理理论分析研发转产中的质量控制问题。",
        "topic": "回归测试项目",
    }
    r = api("/api/project-context", context)
    ok, detail = assert_ok(r, "POST /api/project-context")
    record("Set project context", ok, detail)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 方法论选择与一致性
# ═══════════════════════════════════════════════════════════════════════════════

def test_methodology_flow():
    print("\n── 3. 方法论选择 ──")
    methods_raw = api("/api/methodologies")
    methods = methods_raw.get("items", methods_raw) if isinstance(methods_raw, dict) else methods_raw
    if not isinstance(methods, list) or len(methods) < 3:
        record("Method selection flow", False, "Not enough methods loaded", skipped=True)
        return None, None

    # 从卡片库中挑选 3 个跨阶段方法
    discover_methods = [m for m in methods if "discover" in (m.get("phases") or [])]
    solve_methods = [m for m in methods if "solve" in (m.get("phases") or [])]
    validate_methods = [m for m in methods if "validate" in (m.get("phases") or [])]

    d_ids = [m["id"] for m in discover_methods[:2]]
    s_ids = [m["id"] for m in solve_methods[:2]]
    v_ids = [m["id"] for m in validate_methods[:2]]

    if not d_ids:
        record("Method selection flow", False, "No discover-phase methods", skipped=True)
        return None, None

    # 保存方法分配
    phase_methods = {"discover": d_ids, "solve": s_ids, "validate": v_ids}
    r = api("/api/method-assignments/save", {"phase_methods": phase_methods})
    ok1, _ = assert_ok(r, "POST /api/method-assignments/save")

    # 保存方法池
    for phase, ids in [("discover", d_ids), ("solve", s_ids), ("validate", v_ids)]:
        api("/api/method-pool/save", {"method_pool": ids, "phase": phase})

    record("Method assignment save", ok1, f"discover={len(d_ids)}, solve={len(s_ids)}, validate={len(v_ids)}")

    # ── 一致性校验 1: 跨阶段方法去重 ──
    # 找一个同时属于 discover 和 solve 的方法
    cross_phase = [m for m in methods if "discover" in (m.get("phases") or []) and "solve" in (m.get("phases") or [])]
    if cross_phase:
        cp_id = cross_phase[0]["id"]
        cross_phase_methods = {"discover": [cp_id], "solve": [cp_id], "validate": []}
        r_save = api("/api/method-assignments/save", {"phase_methods": cross_phase_methods})
        # 关键断言：重新读取工作区，该 method 应该在两个 phase 中都存在
        ws = api("/api/workspace")
        pm = ws.get("phase_methods", {})
        in_discover = cp_id in str(pm.get("discover", []))
        in_solve = cp_id in str(pm.get("solve", []))
        cross_ok = in_discover and in_solve
        record("Cross-phase method dedup", cross_ok,
               f"method={cp_id}, in_discover={in_discover}, in_solve={in_solve}" +
               (" — BUG: method lost from one phase!" if not cross_ok else ""))
    else:
        record("Cross-phase method dedup", True, "No cross-phase method available to test", skipped=True)

    # 恢复原来的方法分配
    api("/api/method-assignments/save", {"phase_methods": phase_methods})
    return d_ids, phase_methods


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 研究框架生成（需要 LLM）
# ═══════════════════════════════════════════════════════════════════════════════

def test_framework(phase_methods: Optional[Dict], quick: bool = False):
    print("\n── 4. 研究框架 ──")
    if quick:
        record("Framework generation", True, "Quick mode — skipped LLM call", skipped=True)
        return True

    if not phase_methods:
        record("Framework generation", False, "No phase_methods from methodology step", skipped=True)
        return True

    r = api("/api/framework", {
        "topic": "回归测试项目：质量管理研究",
        "direction_name": "质量管理",
        "phase_methods": phase_methods,
    }, timeout=LLM_TIMEOUT)

    ok, detail = assert_ok(r, "POST /api/framework")
    has_svg = bool(r.get("svg"))
    record("Framework generation", ok and has_svg, detail + (f" svg={len(r.get('svg',''))} chars" if has_svg else ""))

    if has_svg:
        # 保存框架
        r2 = api("/api/framework/save", {
            "svg": r["svg"],
            "topic": "回归测试项目",
            "direction": "质量管理",
            "phase_methods": phase_methods,
        })
        ok2, _ = assert_ok(r2, "POST /api/framework/save")
        record("Framework save", ok2)

    return ok and has_svg


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 提纲生成与保存（需要 LLM）
# ═══════════════════════════════════════════════════════════════════════════════

def test_outline(method_ids: Optional[List], phase_methods: Optional[Dict], quick: bool = False):
    print("\n── 5. 章节大纲 ──")
    if quick:
        record("Outline generation", True, "Quick mode — skipped LLM call", skipped=True)
        return None

    if not method_ids:
        record("Outline generation", False, "No methods from methodology step", skipped=True)
        return None

    # 先生成提纲
    r = api("/api/outline", {
        "topic": "回归测试项目：质量管理研究",
        "direction_name": "质量管理",
        "methods": method_ids,
        "phase_methods": phase_methods or {},
        "total_words": 30000,
        "project_context": "回归测试",
    }, timeout=LLM_TIMEOUT)

    ok, detail = assert_ok(r, "POST /api/outline")
    task_id = r.get("task_id") if ok else None
    record("Outline generation (async)", ok, detail)

    if task_id:
        # 轮询任务结果
        outline = None
        for attempt in range(20):
            time.sleep(3)
            tr = api(f"/api/tasks/{task_id}")
            if tr.get("status") == "completed":
                outline = tr.get("result", {}).get("outline")
                break
            elif tr.get("status") == "failed":
                record("Outline task result", False, tr.get("error", "Task failed"))
                return None

        if outline:
            # 保存提纲
            r2 = api("/api/outline/save", {
                "topic": "回归测试项目",
                "project_context": "## 项目背景\n回归测试\n\n## 论文思路\n测试论文思路",
                "outline": outline,
                "methods": method_ids,
                "phase_methods": phase_methods or {},
                "skip_stale": False,
            })
            ok2, _ = assert_ok(r2, "POST /api/outline/save")
            chapters = len(outline.get("chapters", []))
            record("Outline save", ok2, f"{chapters} chapters")
            return outline
        else:
            record("Outline task result", False, "Timed out waiting for task")
            return None
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 引用生成（需要 LLM）
# ═══════════════════════════════════════════════════════════════════════════════

def test_citations(method_ids: Optional[List], quick: bool = False):
    print("\n── 6. 引用生成 ──")
    if quick:
        record("Citation generation", True, "Quick mode — skipped LLM call", skipped=True)
        return

    if not method_ids:
        record("Citation generation", False, "No methods", skipped=True)
        return

    r = api("/api/citations/generate", {
        "topic": "回归测试项目：质量管理研究",
        "direction": "质量管理",
        "direction_name": "质量管理",
        "methods": method_ids,
        "expected_count": 15,
    }, timeout=LLM_TIMEOUT)

    ok, detail = assert_ok(r, "POST /api/citations/generate")
    task_id = r.get("task_id") if ok else None
    record("Citation generation (async)", ok, detail)

    if task_id:
        for attempt in range(15):
            time.sleep(3)
            tr = api(f"/api/tasks/{task_id}")
            if tr.get("status") == "completed":
                citations = tr.get("result", {}).get("citations", [])
                record("Citation task result", len(citations) > 0, f"{len(citations)} citations generated")
                return citations
            elif tr.get("status") == "failed":
                record("Citation task result", False, tr.get("error", "Task failed"))
                return None
        record("Citation task result", False, "Timed out")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 扩写测试（需要 LLM）
# ═══════════════════════════════════════════════════════════════════════════════

def test_expand(outline: Optional[Dict], method_ids: Optional[List], quick: bool = False):
    print("\n── 7. 章节扩写 ──")
    if quick:
        record("Expand writing", True, "Quick mode — skipped LLM call", skipped=True)
        return

    if not outline or not method_ids:
        record("Expand writing", False, "No outline or methods", skipped=True)
        return

    chapters = outline.get("chapters", [])
    if not chapters:
        record("Expand writing", False, "Outline has no chapters", skipped=True)
        return

    # 选取第一章的第一个 section
    ch = chapters[0]
    sections = ch.get("sections", [])
    if not sections:
        record("Expand writing", False, "Chapter 1 has no sections", skipped=True)
        return

    section = sections[0]
    draft_key = section.get("number", "1.1")

    r = api("/api/expand", {
        "section": section,
        "chapter": {"number": ch.get("number", 1), "title": ch.get("title", "")},
        "topic": "回归测试项目",
        "methods": method_ids,
        "project_context": "回归测试项目背景",
        "direction": "质量管理",
        "section_prompt": "请生成约500字的论文正文，包含学术引用标记。",
    }, timeout=LLM_TIMEOUT)

    ok, detail = assert_ok(r, "POST /api/expand")
    content = r.get("content", "")
    record("Expand section", ok and len(content) > 0,
           detail + f" content={len(content)} chars" if content else "")

    if content:
        # 保存草稿
        r2 = api("/api/drafts/save", {
            "draft_key": draft_key,
            "content": content,
        })
        ok2, _ = assert_ok(r2, "POST /api/drafts/save")
        stale = r2.get("stale_chapters", [])
        record("Draft save", ok2, f"stale_chapters={len(stale)}")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 数据流与一致性校验（不依赖 LLM）
# ═══════════════════════════════════════════════════════════════════════════════

def test_data_consistency():
    """全面校验数据一致性：方法池、提纲结构、引用状态、草稿关联。"""
    print("\n── 8. 数据流与一致性校验 ──")

    ws = api("/api/workspace")
    all_ok = True

    # 8a. phase_methods vs method_pools 一致性
    phase_methods = ws.get("phase_methods", {})
    method_pools = ws.get("method_pools", {})
    for phase in ["discover", "solve", "validate"]:
        pm = set(phase_methods.get(phase, []))
        mp = set(method_pools.get(phase, []))
        if pm and mp:
            # 方法池应该包含该阶段已分配的所有方法（可以更多）
            missing = pm - mp
            if missing:
                record(f"Pool consistency: {phase}", False,
                       f"Phase {phase}: {len(missing)} methods in assignments but NOT in pool")
                all_ok = False
            else:
                record(f"Pool consistency: {phase}", True,
                       f"Phase {phase}: {len(pm)} in assignments, {len(mp)} in pool")

    # 8b. 提纲结构完整性
    outline = ws.get("outline", {})
    if outline and isinstance(outline, dict):
        chapters = outline.get("chapters", [])
        chapter_ok = True
        issues = []
        for ch in chapters:
            if not ch.get("title"):
                issues.append(f"Chapter {ch.get('number', '?')} missing title")
                chapter_ok = False
            if not ch.get("sections"):
                issues.append(f"Chapter {ch.get('number', '?')} has no sections")
                chapter_ok = False
            for sec in (ch.get("sections") or []):
                if not sec.get("title"):
                    issues.append(f"Section {sec.get('number', '?')} missing title")
                    chapter_ok = False
        record("Outline structure integrity", chapter_ok,
               f"{len(chapters)} chapters" + (" — " + "; ".join(issues[:3]) if issues else ""))
        if not chapter_ok:
            all_ok = False
    else:
        record("Outline structure integrity", False, "No outline in workspace", skipped=True)

    # 8c. 草稿与提纲关联
    drafts = ws.get("drafts", {})
    if outline and isinstance(outline, dict) and drafts:
        draft_keys = set(drafts.keys())
        outline_keys = set()
        for ch in (outline.get("chapters") or []):
            for sec in (ch.get("sections") or []):
                outline_keys.add(sec.get("number", ""))
                for sub in (sec.get("subsections") or []):
                    outline_keys.add(sub.get("number", ""))
        orphan_drafts = draft_keys - outline_keys - {""}
        if orphan_drafts:
            record("Draft-outline linkage", False,
                   f"{len(orphan_drafts)} orphan drafts (keys not in outline): {list(orphan_drafts)[:3]}")
            all_ok = False
        else:
            record("Draft-outline linkage", True, f"{len(draft_keys)} drafts, all linked to outline")

    # 8d. thesis_memory 方法数据一致性
    memory = ws.get("thesis_memory", {})
    if isinstance(memory, str):
        try:
            memory = json.loads(memory) if isinstance(memory, str) else memory
        except json.JSONDecodeError:
            memory = {}
    mem_methods = memory.get("methods", [])
    mem_phase = memory.get("phase_methods", {})
    ws_phase = phase_methods
    if mem_phase and ws_phase:
        # 检查 thesis_memory 中的 phase_methods 是否与工作区存储的一致
        mismatch = False
        for phase in ["discover", "solve", "validate"]:
            mem_set = set(str(m) for m in (mem_phase.get(phase, [])))
            ws_set = set(str(m) for m in (ws_phase.get(phase, [])))
            if mem_set != ws_set:
                mismatch = True
                break
        if mismatch:
            record("Thesis memory method sync", False,
                   "Methods in thesis_memory differ from workspace phase_methods")
            all_ok = False
        else:
            record("Thesis memory method sync", True, "Methods match between thesis_memory and workspace")
    else:
        record("Thesis memory method sync", True, "No method data to compare", skipped=True)

    # 8e. stale_chapters 一致性
    stale = memory.get("stale_chapters", [])
    if stale:
        # 检查标记为过期的章节是否真的存在于提纲中
        outline_ch_nums = {str(ch.get("number", "")) for ch in (outline.get("chapters") or []) if outline}
        stale_nums = {str(s.get("chapter", "")) for s in stale}
        phantom = stale_nums - outline_ch_nums
        if phantom:
            record("Stale chapter consistency", False,
                   f"Stale chapters reference non-existent chapters: {phantom}")
            all_ok = False
        else:
            record("Stale chapter consistency", True, f"{len(stale)} stale chapters, all valid")

    # 8f. 引用数据完整性
    citations = ws.get("citations", [])
    if isinstance(citations, list) and citations:
        # 检查引用的必要字段
        missing_fields = 0
        for cite in citations[:10]:
            if not cite.get("title") and not cite.get("formatted"):
                missing_fields += 1
        if missing_fields:
            record("Citation data integrity", False, f"{missing_fields}/10 citations missing title/formatted")
            all_ok = False
        else:
            record("Citation data integrity", True, f"{len(citations)} citations, fields intact")

    return all_ok


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ThesisMind 全流程回归测试")
    parser.add_argument("--base-url", default="http://127.0.0.1:8222", help="服务器地址")
    parser.add_argument("--quick", action="store_true", help="快速模式，跳过所有 LLM 调用，仅测试数据一致性")
    parser.add_argument("--skip-llm", action="store_true", help="跳过需要 LLM 的步骤（框架/提纲/引用/扩写）")
    args = parser.parse_args()

    global BASE_URL, TIMEOUT, LLM_TIMEOUT
    BASE_URL = args.base_url
    quick = args.quick or args.skip_llm

    print("=" * 66)
    print("  ThesisMind 全流程回归测试")
    print(f"  服务器: {BASE_URL}")
    print(f"  模式: {'快速（跳过 LLM）' if quick else '完整（含 LLM 调用）'}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 66)

    start_time = time.time()

    # 1. 基础设施
    if not test_health():
        print("\n❌ 服务器不可用，测试终止。")
        sys.exit(1)

    config = test_config()
    test_license()
    test_methodologies()
    test_projects()

    # 2. 项目配置
    project_id = test_project_creation()
    test_project_context(project_id)

    # 3. 方法论
    method_ids, phase_methods = test_methodology_flow()

    # 4-7. LLM 依赖步骤
    test_framework(phase_methods, quick=quick)
    outline = test_outline(method_ids, phase_methods, quick=quick)
    test_citations(method_ids, quick=quick)
    test_expand(outline, method_ids, quick=quick)

    # 8. 数据一致性校验（始终运行）
    consistency_ok = test_data_consistency()

    # ── 汇总 ──
    elapsed = time.time() - start_time
    total = len(_results)
    passed = sum(1 for r in _results if r["passed"])
    failed = sum(1 for r in _results if not r["passed"] and not r["skipped"])
    skipped = sum(1 for r in _results if r["skipped"])

    print("\n" + "=" * 66)
    print(f"  测试结果: {total} 项  |  {PASS} {passed}  |  {FAIL} {failed}  |  {SKIP} {skipped}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  数据一致性: {'✅ 通过' if consistency_ok else '❌ 失败'}")
    print("=" * 66)

    # 输出失败详情
    if failed:
        print("\n── 失败详情 ──")
        for r in _results:
            if not r["passed"] and not r["skipped"]:
                print(f"  ❌ {r['name']}: {r['detail']}")

    # 返回码
    if failed > 0:
        print("\n❌ 回归测试未通过！修复上述问题后重新运行。")
        sys.exit(1)
    elif not consistency_ok:
        print("\n❌ 数据一致性校验失败！")
        sys.exit(2)
    else:
        print("\n✅ 全流程回归测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
