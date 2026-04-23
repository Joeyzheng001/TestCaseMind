#!/usr/bin/env python3
"""
mcp_server.py - 测试 Agent MCP Server

把测试 Agent 的三个核心能力暴露为 MCP 工具，供 Claude Code 调用。

安装依赖:
    pip install mcp anthropic python-dotenv pyyaml openpyxl

注册到 Claude Code（在项目根目录创建 .mcp.json）:
    {
      "mcpServers": {
        "test-agent": {
          "type": "stdio",
          "command": "python",
          "args": ["/绝对路径/test-agent/mcp_server.py"]
        }
      }
    }

工具列表:
    review_requirement     — 评审需求文档，返回质量分和风险点
    generate_testpoints    — 生成测试点（REQ/KB/RISK 三类标记）
    generate_testcases     — 展开测试用例，生成 JSON + Excel
    convert_kb_docx        — Word 文档转 Markdown 知识库
    get_task_status        — 查看任务进度（支持续跑）
"""

import json
import os
import sys
import time
from pathlib import Path

# 确保能找到 agent 模块
AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR))

from dotenv import load_dotenv
load_dotenv(AGENT_DIR / ".env", override=True)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test-agent")

# ── 懒加载 agent 模块（避免启动时就初始化 Anthropic client）──────────────────
_agent = None
def get_agent():
    global _agent
    if _agent is None:
        import agent as _agent_module
        _agent = _agent_module
    return _agent


# ── Tool 1: 需求评审 ───────────────────────────────────────────────────────
@mcp.tool()
def review_requirement(requirement_path: str) -> str:
    """
    评审需求文档质量，识别测试风险。

    Args:
        requirement_path: 需求文档路径（相对于 test-agent 目录，或绝对路径）

    Returns:
        JSON 字符串，包含：
        - score: 质量分 (0-100)
        - summary: 一句话总结
        - risk_flags: 风险点列表
        - testable_features: 可测功能点列表
        - completeness_issues: 完整性问题
    """
    ag = get_agent()
    req_path = _resolve_path(requirement_path)

    print(f"[test-agent] 需求评审: {req_path.name}", file=sys.stderr)

    try:
        review = ag.stage1_review(req_path)
        return json.dumps(review, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "score": 0,
                           "testable_features": [], "risk_flags": []},
                          ensure_ascii=False)


# ── Tool 2: 测试点生成 ─────────────────────────────────────────────────────
@mcp.tool()
def generate_testpoints(
    requirement_path: str,
    use_knowledge_base: bool = True,
    skip_review: bool = False,
) -> str:
    """
    基于需求文档生成测试点，支持知识库检索。

    Args:
        requirement_path: 需求文档路径
        use_knowledge_base: 是否启用知识库（默认 True）
        skip_review: 是否跳过需求评审直接生成（默认 False）

    Returns:
        JSON 字符串，包含：
        - output_file: 生成的 JSON 文件路径
        - xmind_file: 生成的 Markdown 文件路径（可导入 XMind）
        - total: 测试点总数
        - by_source: {REQ, KB, RISK} 各类数量
        - testpoints: 测试点列表
    """
    ag = get_agent()
    req_path = _resolve_path(requirement_path)
    ts   = int(time.time())
    stem = req_path.stem

    print(f"[test-agent] 测试点生成: {req_path.name} (kb={use_knowledge_base})",
          file=sys.stderr)

    try:
        # 初始化任务和记忆
        from task_store import TaskStore
        from memory_store import MemoryStore
        task   = TaskStore(stem, ts)
        ag.memory = MemoryStore(stem)   # 注入到 agent 模块

        # 需求评审
        if skip_review:
            review = {"testable_features": [], "risk_flags": [], "score": 0}
        else:
            task.start("review")
            review = ag.stage1_review(req_path)
            task.done("review", review)
            ag.memory.save_after_review(review)

        # 测试点生成
        task.start("testpoints")
        testpoints = ag.stage2_testpoints(req_path, review, use_knowledge_base)
        task.done("testpoints", testpoints)
        ag.memory.save_after_testpoints(testpoints, review)

        # 标准化为扁平列表
        flat_tps = _flatten_testpoints(testpoints)

        # 统计
        def get_src(tp): return tp.get("source", "REQ") if tp.get("source") in ("REQ","KB","RISK") else "REQ"
        req_c  = sum(1 for t in flat_tps if get_src(t) == "REQ")
        kb_c   = sum(1 for t in flat_tps if get_src(t) == "KB")
        risk_c = sum(1 for t in flat_tps if get_src(t) == "RISK")

        # 写输出文件
        output_dir = AGENT_DIR / "output"
        output_dir.mkdir(exist_ok=True)

        tp_file = output_dir / f"testpoints_{stem}_{ts}.json"
        md_file = output_dir / f"testpoints_{stem}_{ts}.md"

        tp_file.write_text(json.dumps({
            "meta": {"requirement": str(req_path),
                     "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "total": len(flat_tps),
                     "by_source": {"REQ": req_c, "KB": kb_c, "RISK": risk_c}},
            "review": review,
            "testpoints": flat_tps,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        ag.export_markdown_xmind(flat_tps, review, req_path.name, md_file)

        return json.dumps({
            "output_file": str(tp_file),
            "xmind_file":  str(md_file),
            "total":       len(flat_tps),
            "by_source":   {"REQ": req_c, "KB": kb_c, "RISK": risk_c},
            "review_score": review.get("score", "N/A"),
            "risk_count":  len(review.get("risk_flags", [])),
            "testpoints":  flat_tps[:5],   # 只返回前5条预览，完整数据在文件里
            "note": f"完整测试点已写入 {tp_file.name}",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({"error": str(e), "detail": traceback.format_exc()},
                          ensure_ascii=False)


# ── Tool 3: 测试用例生成 ───────────────────────────────────────────────────
@mcp.tool()
def generate_testcases(testpoints_file: str) -> str:
    """
    基于测试点文件展开生成完整测试用例，输出 JSON + Excel。

    Args:
        testpoints_file: 测试点 JSON 文件路径（由 generate_testpoints 生成）

    Returns:
        JSON 字符串，包含：
        - json_file: 测试用例 JSON 文件路径
        - excel_file: 测试用例 Excel 文件路径
        - total: 用例总数
        - preview: 前3条用例预览
    """
    ag = get_agent()
    tp_path = _resolve_path(testpoints_file)

    print(f"[test-agent] 测试用例生成: {tp_path.name}", file=sys.stderr)

    try:
        data       = json.loads(tp_path.read_text(encoding="utf-8"))
        flat_tps   = data.get("testpoints", [])
        req_name   = Path(data.get("meta", {}).get("requirement", "unknown")).name
        ts         = int(time.time())
        stem       = tp_path.stem.replace("testpoints_", "")

        if not flat_tps:
            return json.dumps({"error": "测试点文件为空，无法生成用例"})

        # 分批生成
        testcases = ag.stage3_testcases(flat_tps, tp_path)

        # 输出文件
        output_dir = AGENT_DIR / "output"
        output_dir.mkdir(exist_ok=True)

        tc_json  = output_dir / f"testcases_{stem}.json"
        tc_xlsx  = output_dir / f"testcases_{stem}.xlsx"

        tc_json.write_text(json.dumps(testcases, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        xlsx_ok = ag.export_excel(testcases, tc_xlsx)

        return json.dumps({
            "json_file":  str(tc_json),
            "excel_file": str(tc_xlsx) if xlsx_ok else None,
            "total":      len(testcases),
            "preview":    testcases[:3],
            "note":       f"完整用例已写入 {tc_json.name}",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({"error": str(e), "detail": traceback.format_exc()},
                          ensure_ascii=False)


# ── Tool 4: Word 转知识库 ──────────────────────────────────────────────────
@mcp.tool()
def convert_kb_docx(docx_path: str) -> str:
    """
    将 Word 文档转换为 Markdown，存入知识库目录。

    Args:
        docx_path: Word 文档路径（.docx）

    Returns:
        转换结果，包含输出文件路径
    """
    import subprocess
    src = _resolve_path(docx_path)
    dst = AGENT_DIR / "knowledge_base" / (src.stem + ".md")

    print(f"[test-agent] 转换知识库: {src.name}", file=sys.stderr)

    try:
        result = subprocess.run(
            ["pandoc", str(src), "-t", "markdown", "-o", str(dst)],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return json.dumps({"error": result.stderr[:300]})

        return json.dumps({
            "output_file": str(dst),
            "size_kb": dst.stat().st_size // 1024,
            "lines": len(dst.read_text(encoding="utf-8").splitlines()),
            "note": "已加入知识库，下次运行 --kb 时会自动检索此文件",
        }, ensure_ascii=False)
    except FileNotFoundError:
        return json.dumps({"error": "pandoc 未安装，请先运行: brew install pandoc"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── Tool 5: 任务状态查询 ───────────────────────────────────────────────────
@mcp.tool()
def get_task_status(requirement_name: str = "") -> str:
    """
    查看测试任务的执行进度，支持续跑。

    Args:
        requirement_name: 需求文档名称（不含扩展名），留空则显示所有任务

    Returns:
        任务状态 JSON，包含各阶段完成情况
    """
    from task_store import TaskStore, TASKS_DIR

    tasks_info = []
    pattern = f"{requirement_name}*.json" if requirement_name else "*.json"

    for f in sorted(TASKS_DIR.glob(pattern), reverse=True)[:10]:
        try:
            data   = json.loads(f.read_text(encoding="utf-8"))
            stages = data.get("stages", {})
            tasks_info.append({
                "file":       f.name,
                "created_at": data.get("created_at"),
                "stages": {
                    s: {"status": info["status"],
                        "updated_at": info.get("updated_at")}
                    for s, info in stages.items()
                },
                "resumable": any(
                    info["status"] in ("pending", "running", "failed")
                    for info in stages.values()
                ),
            })
        except Exception:
            continue

    if not tasks_info:
        return json.dumps({"message": "没有找到任务记录", "tasks": []})

    return json.dumps({
        "total": len(tasks_info),
        "tasks": tasks_info,
        "tip": "如需续跑，在命令行加 --resume 参数",
    }, ensure_ascii=False, indent=2)


# ── 工具函数 ───────────────────────────────────────────────────────────────
def _resolve_path(p: str) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = AGENT_DIR / path
    if not path.exists():
        raise FileNotFoundError(f"找不到文件: {path}")
    return path.resolve()


def _flatten_testpoints(testpoints: list) -> list:
    if not testpoints:
        return []
    if isinstance(testpoints[0], dict) and "testpoints" in testpoints[0]:
        flat = []
        for m in testpoints:
            flat.extend(m.get("testpoints", []))
        return flat
    return testpoints


# ── 启动 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")

# ── Tool 6: 知识库沉淀 ────────────────────────────────────────────────────
@mcp.tool()
def save_to_knowledge_base(
    requirement_path: str,
    testpoints_file: str,
) -> str:
    """
    把需求文档和测试经验沉淀到知识库，自动完成三件事：
    1. 需求文档复制到 knowledge_base/ 目录（供下次检索）
    2. RISK 类测试点提取为经验条目写入长期记忆
    3. 更新该需求的短期记忆（测试点统计、已知因子）

    Args:
        requirement_path: 需求文档路径
        testpoints_file:  测试点 JSON 文件路径（由 generate_testpoints 生成）

    Returns:
        JSON 字符串，包含各步骤执行结果
    """
    import shutil
    from memory_store import MemoryStore

    req_path = _resolve_path(requirement_path)
    tp_path  = _resolve_path(testpoints_file)

    print(f"[test-agent] 知识库沉淀: {req_path.name}", file=sys.stderr)

    results = []

    # 1. 需求文档复制到知识库
    kb_dir = AGENT_DIR / "knowledge_base"
    kb_dir.mkdir(exist_ok=True)
    dst = kb_dir / req_path.name
    shutil.copy2(req_path, dst)
    status = "已更新" if dst.exists() else "已复制"
    results.append(f"需求文档{status}: knowledge_base/{req_path.name}")

    # 2. 读取测试点数据
    try:
        data     = json.loads(tp_path.read_text(encoding="utf-8"))
        flat_tps = data.get("testpoints", [])
        review   = data.get("review", {})
        meta     = data.get("meta", {})
    except Exception as e:
        return json.dumps({"error": f"读取测试点文件失败: {e}",
                           "actions": results}, ensure_ascii=False)

    # 3. 更新记忆系统
    try:
        memory = MemoryStore(req_path.stem)

        # 提取 RISK 类测试点写入长期记忆
        risk_tps    = [tp for tp in flat_tps if tp.get("source") == "RISK"]
        saved_hints = 0
        for tp in risk_tps[:8]:
            scenario = tp.get("test_scenario") or tp.get("title") or ""
            module   = tp.get("functional_module", "")
            hint     = f"[{req_path.stem}][{module}] {scenario[:70]}"
            memory.save_testpoint_hint(hint)
            saved_hints += 1
        results.append(f"提取 {saved_hints} 条风险经验写入长期记忆")

        # 提取 KB 类测试点来源规律
        kb_tps = [tp for tp in flat_tps if tp.get("source") == "KB"]
        for tp in kb_tps[:3]:
            ref = tp.get("source_ref", "")
            if ref:
                pattern = f"KB规范支撑: {ref[:60]}"
                if pattern not in memory._lt.get("domain_patterns", []):
                    memory._lt["domain_patterns"].append(pattern)
        memory._save_lt()

        # 更新短期记忆
        memory.save_after_testpoints(flat_tps, review)
        by_source = meta.get("by_source", {})
        results.append(
            f"短期记忆已更新 REQ={by_source.get('REQ',0)} "
            f"KB={by_source.get('KB',0)} RISK={by_source.get('RISK',0)}"
        )

    except Exception as e:
        results.append(f"记忆更新失败: {e}")

    # 4. 统计知识库规模
    kb_files = list(kb_dir.glob("**/*.md"))
    results.append(f"知识库现有 {len(kb_files)} 个 md 文件")

    return json.dumps({
        "status":  "done",
        "actions": results,
        "kb_file": str(dst),
        "memory":  str(AGENT_DIR / "memory" / f"{req_path.stem}.json"),
    }, ensure_ascii=False, indent=2)
