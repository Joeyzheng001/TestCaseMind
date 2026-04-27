#!/usr/bin/env python3
"""
mcp_server.py - 测试 Agent MCP Server（异步任务版）

把耗时操作改为后台异步任务，MCP 工具立刻返回任务 ID，
Claude Code 不需要等待，后台自动运行完成后轮询状态获取结果。

工具列表:
    run_test_agent      — 一键触发完整流程（异步），立刻返回 job_id
    get_job_status      — 查询任务状态和结果
    cancel_job          — 取消正在运行的任务
    convert_kb_docx     — Word 文档转 Markdown（同步，秒级完成）
    save_to_knowledge_base — 知识库沉淀（同步）
    list_outputs        — 列出输出文件
"""

import json
import os
import subprocess
import sys
import time
import threading
import uuid
from pathlib import Path

AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(AGENT_DIR))

from dotenv import load_dotenv
load_dotenv(AGENT_DIR / ".env", override=True)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("test-agent")

# ── 任务状态存储 ──────────────────────────────────────────────────────────────
JOBS_DIR = AGENT_DIR / ".mcp_jobs"
JOBS_DIR.mkdir(exist_ok=True)


def _save_job(job: dict):
    (JOBS_DIR / f"{job['job_id']}.json").write_text(
        json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_job(job_id: str) -> dict | None:
    p = JOBS_DIR / f"{job_id}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _resolve_path(p: str) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = AGENT_DIR / path
    if not path.exists():
        raise FileNotFoundError(f"找不到文件: {path}")
    return path.resolve()


def _ensure_md(path: Path) -> Path:
    """docx 自动转换为 md，其他格式直接返回。"""
    if path.suffix.lower() not in (".docx", ".doc"):
        return path
    kb_dir  = AGENT_DIR / "knowledge_base"
    kb_dir.mkdir(exist_ok=True)
    md_path = kb_dir / (path.stem + ".md")
    if md_path.exists():
        return md_path
    result = subprocess.run(
        ["pandoc", str(path), "-t", "markdown", "-o", str(md_path)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"pandoc 转换失败: {result.stderr[:200]}")
    return md_path


# ── 后台任务执行器 ────────────────────────────────────────────────────────────
def _run_agent_background(job_id: str, req_path_str: str,
                           use_kb: bool, skip_review: bool,
                           no_cases: bool, section: str = ""):
    """在后台线程中运行 agent，更新任务状态。"""
    job = _load_job(job_id)
    if not job:
        return

    try:
        # 构建命令行参数
        cmd = [sys.executable, str(AGENT_DIR / "agent.py"), req_path_str]
        if use_kb:
            cmd.append("--kb")
        if skip_review:
            cmd.append("--skip-review")
        if no_cases:
            cmd.append("--no-cases")
        if section:
            cmd += ["--section", section]

        job["status"]    = "running"
        job["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        job["pid"]       = None
        _save_job(job)

        # 运行 agent，捕获输出
        log_path = JOBS_DIR / f"{job_id}.log"
        with open(log_path, "w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(AGENT_DIR),
            )
            job["pid"] = proc.pid
            _save_job(job)

            proc.wait()

        # 读取日志，提取输出文件路径
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        output   = _parse_output_from_log(log_text, req_path_str)

        if proc.returncode == 0:
            job["status"]       = "done"
            job["output"]       = output
            job["finished_at"]  = time.strftime("%Y-%m-%d %H:%M:%S")
            job["log_tail"]     = _tail(log_text, 20)
        else:
            job["status"]  = "failed"
            job["error"]   = f"进程退出码 {proc.returncode}"
            job["log_tail"] = _tail(log_text, 30)

    except Exception as e:
        job["status"] = "failed"
        job["error"]  = str(e)
        import traceback
        job["detail"] = traceback.format_exc()

    _save_job(job)


def _parse_output_from_log(log: str, req_path_str: str) -> dict:
    """从日志中提取输出文件路径。"""
    output = {}
    for line in log.splitlines():
        if "testpoints.json" in line or "JSON:" in line:
            m = _find_path_in_line(line, ".json")
            if m and "testpoints" in m:
                output["testpoints_json"] = m
        if "testpoints_xmind.md" in line or "Markdown" in line:
            m = _find_path_in_line(line, ".md")
            if m:
                output["testpoints_md"] = m
        if "testcases.xlsx" in line or "Excel:" in line:
            m = _find_path_in_line(line, ".xlsx")
            if m:
                output["testcases_xlsx"] = m
        if "testcases.json" in line:
            m = _find_path_in_line(line, ".json")
            if m and "testcases" in m:
                output["testcases_json"] = m
        if "report.md" in line:
            m = _find_path_in_line(line, ".md")
            if m and "report" in m:
                output["report_md"] = m

    # 尝试通过需求文档名推断输出目录
    req_stem = Path(req_path_str).stem
    out_base = AGENT_DIR / "output" / req_stem
    if out_base.exists():
        # 找最新的时间戳目录
        runs = sorted(out_base.iterdir(), reverse=True)
        if runs:
            run_dir = runs[0]
            output["output_dir"] = str(run_dir)
            for f in run_dir.iterdir():
                if f.suffix == ".json" and "testpoints" in f.name:
                    output.setdefault("testpoints_json", str(f))
                elif f.suffix == ".json" and "testcases" in f.name:
                    output.setdefault("testcases_json", str(f))
                elif f.suffix == ".xlsx":
                    output.setdefault("testcases_xlsx", str(f))
                elif f.suffix == ".md" and "report" in f.name:
                    output.setdefault("report_md", str(f))
                elif f.suffix == ".md" and "testpoints" in f.name:
                    output.setdefault("testpoints_md", str(f))

    return output


def _find_path_in_line(line: str, ext: str) -> str | None:
    import re
    m = re.search(r'[\w/\-. ]*' + ext.replace(".", r"\."), line)
    return m.group(0).strip() if m else None


def _tail(text: str, n: int) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-n:]) if lines else ""


# ── Tool 1: 一键触发完整流程（异步）────────────────────────────────────────────
@mcp.tool()
def run_test_agent(
    requirement_path: str,
    use_knowledge_base: bool = True,
    skip_review: bool = False,
    no_cases: bool = False,
    section: str = "",
) -> str:
    """
    一键触发完整测试用例生成流程（异步后台运行，立刻返回任务ID）。

    适合耗时较长的完整流程，不会导致 Claude Code 连接超时。
    使用 get_job_status(job_id) 查询进度和结果。

    Args:
        requirement_path:  需求文档路径（支持 .docx/.md/.txt）
        use_knowledge_base: 是否启用知识库检索（默认 True）
        skip_review:       是否跳过需求评审（默认 False）
        no_cases:          只生成测试点，不展开用例（默认 False）
        section:           只针对指定章节生成，如 "现货持仓数量"（默认空=全文档）

    Returns:
        {
          "job_id": "job_xxxx",
          "status": "running",
          "message": "任务已在后台启动，使用 get_job_status('job_xxxx') 查询进度"
        }
    """
    # 处理路径（docx 自动转换）
    try:
        raw_path = _resolve_path(requirement_path)
        md_path  = _ensure_md(raw_path)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)})
    except RuntimeError as e:
        return json.dumps({"error": str(e)})

    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    job = {
        "job_id":      job_id,
        "status":      "pending",
        "requirement": str(md_path),
        "use_kb":      use_knowledge_base,
        "skip_review": skip_review,
        "no_cases":    no_cases,
        "section":     section,
        "created_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_job(job)

    # 在后台线程启动
    t = threading.Thread(
        target=_run_agent_background,
        args=(job_id, str(md_path), use_knowledge_base, skip_review, no_cases, section),
        daemon=True,
    )
    t.start()

    section_msg = f"，只处理章节「{section}」" if section else ""
    return json.dumps({
        "job_id":  job_id,
        "status":  "running",
        "requirement": md_path.name,
        "message": f"任务已在后台启动{section_msg}。使用 get_job_status('{job_id}') 查询进度，通常需要 3-8 分钟。",
    }, ensure_ascii=False)


# ── Tool 2: 查询任务状态 ──────────────────────────────────────────────────────
@mcp.tool()
def get_job_status(job_id: str = "") -> str:
    """
    查询后台任务的执行进度和结果。

    Args:
        job_id: 任务ID（由 run_test_agent 返回）。留空则显示最近5个任务。

    Returns:
        任务状态、进度、输出文件路径（完成后）
    """
    if not job_id:
        # 显示最近5个任务
        jobs = []
        for f in sorted(JOBS_DIR.glob("job_*.json"), reverse=True)[:5]:
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
                jobs.append({
                    "job_id":     j.get("job_id"),
                    "status":     j.get("status"),
                    "requirement": Path(j.get("requirement", "")).name,
                    "created_at": j.get("created_at"),
                    "finished_at": j.get("finished_at", ""),
                })
            except Exception:
                continue
        return json.dumps({"recent_jobs": jobs}, ensure_ascii=False, indent=2)

    job = _load_job(job_id)
    if not job:
        return json.dumps({"error": f"找不到任务 {job_id}"})

    result = {
        "job_id":      job.get("job_id"),
        "status":      job.get("status"),
        "requirement": Path(job.get("requirement", "")).name,
        "created_at":  job.get("created_at"),
    }

    if job["status"] == "running":
        # 读取日志最后几行，显示进度
        log_path = JOBS_DIR / f"{job_id}.log"
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            result["progress"] = _tail(log_text, 5)
        result["message"] = "任务正在运行中，请稍后再查询..."

    elif job["status"] == "done":
        result["finished_at"] = job.get("finished_at")
        result["output"]      = job.get("output", {})
        result["log_tail"]    = job.get("log_tail", "")
        result["message"]     = "✅ 任务完成！"
        # 统计测试点和用例数
        try:
            tp_file = job.get("output", {}).get("testpoints_json")
            if tp_file and Path(tp_file).exists():
                tp_data = json.loads(Path(tp_file).read_text(encoding="utf-8"))
                meta = tp_data.get("meta", {})
                result["summary"] = {
                    "testpoints_total":  meta.get("total", 0),
                    "by_source":         meta.get("by_source", {}),
                    "review_score":      tp_data.get("review", {}).get("score", "N/A"),
                }
        except Exception:
            pass

    elif job["status"] == "failed":
        result["error"]    = job.get("error")
        result["log_tail"] = job.get("log_tail", "")
        result["message"]  = "❌ 任务失败，查看 log_tail 了解详情"

    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Tool 3: 取消任务 ──────────────────────────────────────────────────────────
@mcp.tool()
def cancel_job(job_id: str) -> str:
    """取消正在运行的后台任务。"""
    job = _load_job(job_id)
    if not job:
        return json.dumps({"error": f"找不到任务 {job_id}"})
    if job["status"] != "running":
        return json.dumps({"message": f"任务状态为 {job['status']}，无需取消"})

    pid = job.get("pid")
    if pid:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            job["status"] = "cancelled"
            _save_job(job)
            return json.dumps({"message": f"已发送终止信号给进程 {pid}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    return json.dumps({"error": "找不到进程 ID"})


# ── Tool 4: Word 文档转 Markdown ──────────────────────────────────────────────
@mcp.tool()
def convert_kb_docx(docx_path: str) -> str:
    """
    将 Word 文档转换为 Markdown，存入知识库目录（同步，秒级完成）。

    Args:
        docx_path: Word 文档路径（.docx）
    """
    try:
        src = _resolve_path(docx_path)
        dst = _ensure_md(src)
        return json.dumps({
            "output_file": str(dst),
            "size_kb":     dst.stat().st_size // 1024,
            "lines":       len(dst.read_text(encoding="utf-8").splitlines()),
            "note":        "已转换并加入知识库",
        }, ensure_ascii=False)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)})
    except RuntimeError as e:
        return json.dumps({"error": str(e), "hint": "请确认已安装 pandoc: brew install pandoc"})


# ── Tool 5: 知识库沉淀 ────────────────────────────────────────────────────────
@mcp.tool()
def save_to_knowledge_base(
    requirement_path: str,
    testpoints_file: str,
) -> str:
    """
    把需求文档和测试经验沉淀到知识库。

    Args:
        requirement_path: 需求文档路径
        testpoints_file:  测试点 JSON 文件路径
    """
    import shutil
    results = []
    try:
        req_path = _resolve_path(requirement_path)
        tp_path  = _resolve_path(testpoints_file)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)})

    # 需求文档复制到知识库
    kb_dir = AGENT_DIR / "knowledge_base"
    kb_dir.mkdir(exist_ok=True)
    dst = kb_dir / req_path.name
    shutil.copy2(req_path, dst)
    results.append(f"需求文档已复制到 knowledge_base/{req_path.name}")

    # 更新记忆
    try:
        from memory_store import MemoryStore
        data     = json.loads(tp_path.read_text(encoding="utf-8"))
        flat_tps = data.get("testpoints", [])
        review   = data.get("review", {})
        memory   = MemoryStore(req_path.stem)

        risk_tps = [tp for tp in flat_tps if tp.get("source") == "RISK"]
        for tp in risk_tps[:8]:
            scenario = tp.get("test_scenario") or tp.get("title") or ""
            module   = tp.get("functional_module", "")
            memory.save_testpoint_hint(f"[{req_path.stem}][{module}] {scenario[:70]}")

        memory.save_after_testpoints(flat_tps, review)
        results.append(f"提取 {len(risk_tps)} 条风险经验写入长期记忆")
    except Exception as e:
        results.append(f"记忆更新失败: {e}")

    kb_files = list((AGENT_DIR / "knowledge_base").glob("**/*.md"))
    results.append(f"知识库现有 {len(kb_files)} 个 md 文件")

    return json.dumps({"status": "done", "actions": results}, ensure_ascii=False, indent=2)


# ── Tool 6: 列出输出文件 ──────────────────────────────────────────────────────
@mcp.tool()
def list_outputs(requirement_name: str = "") -> str:
    """
    列出已生成的输出文件。

    Args:
        requirement_name: 需求文档名（可选，留空列出所有）
    """
    output_dir = AGENT_DIR / "output"
    if not output_dir.exists():
        return json.dumps({"outputs": [], "message": "output 目录不存在"})

    results = []
    pattern = f"*{requirement_name}*" if requirement_name else "*"

    for req_dir in sorted(output_dir.glob(pattern), reverse=True)[:5]:
        if not req_dir.is_dir():
            continue
        for run_dir in sorted(req_dir.iterdir(), reverse=True)[:2]:
            if not run_dir.is_dir():
                continue
            files = {f.name: str(f) for f in run_dir.iterdir() if f.is_file()}
            results.append({
                "requirement": req_dir.name,
                "timestamp":   run_dir.name,
                "files":       files,
            })

    return json.dumps({"outputs": results}, ensure_ascii=False, indent=2)


@mcp.tool()
def distill_knowledge(
    testpoints_file: str,
    requirement_path: str = "",
) -> str:
    """
    从测试点中提炼通用知识规则，写入知识库（异步，立刻返回job_id）。

    大模型判断哪些测试场景是跨PRD通用的，过滤掉业务特定规则。
    完成后用 get_job_status 查询结果，结果会列出提炼到的规则供确认。

    Args:
        testpoints_file:  测试点 JSON 文件路径（output/xxx/testpoints.json）
        requirement_path: 对应需求文档路径（可选，提高判断准确性）
    """
    try:
        tp_path = _resolve_path(testpoints_file)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)})

    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    job = {
        "job_id":     job_id,
        "type":       "distill",
        "status":     "running",
        "tp_file":    str(tp_path),
        "req_file":   requirement_path,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_job(job)

    def run_distill():
        try:
            cmd = [sys.executable, str(AGENT_DIR / "kb_distill.py"),
                   str(tp_path), "--dry-run"]
            if requirement_path:
                try:
                    req_p = _resolve_path(requirement_path)
                    cmd += ["--req", str(req_p)]
                except Exception:
                    pass

            log_path = JOBS_DIR / f"{job_id}.log"
            with open(log_path, "w", encoding="utf-8") as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                        cwd=str(AGENT_DIR))
                proc.wait()

            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            job["status"]     = "done" if proc.returncode == 0 else "failed"
            job["log_tail"]   = _tail(log_text, 30)
            job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            job["message"]    = (
                "提炼完成，查看 log_tail 确认规则后，"
                f"运行 python kb_distill.py {tp_path} 正式写入知识库"
                if proc.returncode == 0 else "提炼失败"
            )
        except Exception as e:
            job["status"] = "failed"
            job["error"]  = str(e)
        _save_job(job)

    t = threading.Thread(target=run_distill, daemon=True)
    t.start()

    return json.dumps({
        "job_id":  job_id,
        "status":  "running",
        "message": f"知识提炼已启动（dry-run 模式，不会自动写入）。"
                   f"用 get_job_status('{job_id}') 查看提炼结果，"
                   f"确认后手动运行 kb_distill.py 写入知识库。",
    }, ensure_ascii=False)


@mcp.tool()
def check_knowledge_base(quick: bool = True) -> str:
    """
    检查知识库健康状态（同步，秒级返回）。

    Args:
        quick: True=快速检查（跳过检索测试），False=完整检查
    """
    try:
        cmd = [sys.executable, str(AGENT_DIR / "kb_check.py"), "--quick"]
        if not quick:
            cmd = [sys.executable, str(AGENT_DIR / "kb_check.py")]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=60, cwd=str(AGENT_DIR))
        output = result.stdout + (result.stderr if result.stderr else "")
        return json.dumps({"output": output, "status": "ok" if result.returncode == 0 else "error"})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "检查超时，建议用命令行运行: python kb_check.py --quick"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def review_memory(action: str = "stats") -> str:
    """
    查看或管理长期记忆（同步，秒级返回）。

    Args:
        action: stats=查看统计（默认） | show=显示所有条目 | export=导出
    """
    try:
        cmd_map = {
            "stats":  [sys.executable, str(AGENT_DIR / "memory_review.py"), "--stats"],
            "show":   [sys.executable, str(AGENT_DIR / "memory_review.py")],
            "export": [sys.executable, str(AGENT_DIR / "memory_review.py"), "--export"],
        }
        cmd = cmd_map.get(action, cmd_map["stats"])
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=30, cwd=str(AGENT_DIR))
        output = result.stdout
        note   = ""
        if action == "clean":
            note = "清理操作需要交互确认，请在终端运行: python memory_review.py --clean"
        return json.dumps({"output": output, "note": note})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def rebuild_index() -> str:
    """
    重建知识库向量索引（异步，立刻返回job_id）。
    知识库有新文件加入后需要运行。
    """
    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    job = {
        "job_id":     job_id,
        "type":       "rebuild_index",
        "status":     "running",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_job(job)

    def run_rebuild():
        try:
            log_path = JOBS_DIR / f"{job_id}.log"
            with open(log_path, "w", encoding="utf-8") as log:
                proc = subprocess.Popen(
                    [sys.executable, str(AGENT_DIR / "kb_rag.py"), "--rebuild"],
                    stdout=log, stderr=subprocess.STDOUT, cwd=str(AGENT_DIR)
                )
                proc.wait()
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            job["status"]      = "done" if proc.returncode == 0 else "failed"
            job["log_tail"]    = _tail(log_text, 10)
            job["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            job["status"] = "failed"
            job["error"]  = str(e)
        _save_job(job)

    t = threading.Thread(target=run_rebuild, daemon=True)
    t.start()

    return json.dumps({
        "job_id":  job_id,
        "status":  "running",
        "message": f"索引重建已在后台启动，用 get_job_status('{job_id}') 查询进度。",
    }, ensure_ascii=False)


# ── 启动 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
