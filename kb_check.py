#!/usr/bin/env python3
"""
kb_check.py - 知识库健康检查

定期运行，评估知识库的质量和覆盖情况：
1. 文件统计（数量、大小、最近更新时间）
2. 向量索引状态（段落数、索引时间）
3. 检索抽样测试（验证关键词能否找到）
4. 问题诊断（空文件、重复文件、过时文件）

用法:
    python kb_check.py              # 全面检查
    python kb_check.py --search     # 交互式检索测试
    python kb_check.py --fix        # 自动修复可修复的问题
"""

import json
import sys
import time
from pathlib import Path
from collections import defaultdict

WORKDIR  = Path(__file__).parent
KB_DIR   = WORKDIR / "knowledge_base"
IDX_DIR  = WORKDIR / ".kb_index"


def fmt_size(size_bytes: int) -> str:
    if size_bytes > 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f}MB"
    return f"{size_bytes // 1024}KB"


def fmt_time(ts: float) -> str:
    import datetime
    dt = datetime.datetime.fromtimestamp(ts)
    now = datetime.datetime.now()
    diff = now - dt
    if diff.days > 30:
        return f"{diff.days}天前"
    elif diff.days > 0:
        return f"{diff.days}天前"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}小时前"
    else:
        return f"{diff.seconds // 60}分钟前"


# ── 1. 文件统计 ───────────────────────────────────────────────────────────────
def check_files() -> dict:
    print("\n📁 知识库文件统计")
    print("─" * 60)

    if not KB_DIR.exists():
        print("  ❌ knowledge_base/ 目录不存在")
        return {}

    stats = defaultdict(list)
    issues = []

    for f in sorted(KB_DIR.rglob("*")):
        if not f.is_file():
            continue
        ext  = f.suffix.lower()
        size = f.stat().st_size
        mtime = f.stat().st_mtime

        if ext == ".md":
            stats["md"].append(f)
            if size < 100:
                issues.append(f"⚠ 文件过小（可能为空）: {f.relative_to(KB_DIR)}")
            if size > 500 * 1024:
                issues.append(f"⚠ 文件过大（超过500KB，建议拆分）: {f.relative_to(KB_DIR)}")
        elif ext in (".docx", ".doc"):
            stats["docx"].append(f)
            md_version = f.with_suffix(".md")
            if not md_version.exists():
                issues.append(f"○ 未转换的 Word 文档: {f.name}  →  运行 python docx2md.py {f.name}")
        elif ext in (".xlsx", ".xls"):
            stats["xlsx"].append(f)

    # 打印统计
    md_files  = stats["md"]
    total_size = sum(f.stat().st_size for f in md_files)
    print(f"  Markdown 文件: {len(md_files)} 个，共 {fmt_size(total_size)}")

    if stats["docx"]:
        print(f"  Word 文档: {len(stats['docx'])} 个（未转换）")
    if stats["xlsx"]:
        print(f"  Excel 文档: {len(stats['xlsx'])} 个")

    # 按目录分组
    dirs = defaultdict(list)
    for f in md_files:
        rel = f.relative_to(KB_DIR)
        parent = str(rel.parent) if rel.parent != Path(".") else "根目录"
        dirs[parent].append(f)

    print(f"\n  目录分布:")
    for dir_name, files in sorted(dirs.items()):
        dir_size = sum(f.stat().st_size for f in files)
        print(f"    {dir_name}/: {len(files)} 个文件，{fmt_size(dir_size)}")

    # 最近更新
    if md_files:
        latest = max(md_files, key=lambda f: f.stat().st_mtime)
        print(f"\n  最近更新: {latest.name}（{fmt_time(latest.stat().st_mtime)}）")

    # 问题报告
    if issues:
        print(f"\n  ⚠ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"    {issue}")
    else:
        print(f"\n  ✅ 文件状态正常")

    return {"md_count": len(md_files), "total_size": total_size, "issues": issues}


# ── 2. 向量索引状态 ───────────────────────────────────────────────────────────
def check_index() -> dict:
    print("\n🔍 向量索引状态")
    print("─" * 60)

    if not IDX_DIR.exists():
        print("  ❌ 索引不存在，请先运行: python kb_rag.py --rebuild")
        return {"status": "missing"}

    hash_file = IDX_DIR / "kb_hash.txt"
    if not hash_file.exists():
        print("  ❌ 索引不完整")
        return {"status": "incomplete"}

    # 检查索引是否和当前知识库一致
    import hashlib
    h = hashlib.md5()
    for f in sorted(KB_DIR.rglob("*.md")):
        h.update(f.name.encode())
        h.update(str(f.stat().st_mtime).encode())
    current_hash = h.hexdigest()
    stored_hash  = hash_file.read_text().strip()

    if current_hash != stored_hash:
        print("  ⚠ 索引已过期（知识库有文件更新），建议运行: python kb_rag.py --rebuild")
        status = "stale"
    else:
        print("  ✅ 索引是最新的")
        status = "ok"

    # 读取段落数
    try:
        import chromadb
        from pathlib import Path as P
        client = chromadb.PersistentClient(path=str(IDX_DIR))
        col    = client.get_collection("kb_index")
        count  = col.count()
        print(f"  已索引段落: {count} 条")

        # 估算覆盖率
        md_files = list(KB_DIR.rglob("*.md"))
        avg_per_file = count / len(md_files) if md_files else 0
        print(f"  平均每文件: {avg_per_file:.0f} 段")

        if avg_per_file < 3:
            print("  ⚠ 平均段落数偏少，文件可能内容过短")
        elif avg_per_file > 200:
            print("  ⚠ 平均段落数偏多，文件可能过大，建议拆分")

        return {"status": status, "count": count}
    except Exception as e:
        print(f"  ❌ 读取索引失败: {e}")
        return {"status": "error"}


# ── 3. 检索抽样测试 ───────────────────────────────────────────────────────────
def check_retrieval(queries: list = None) -> dict:
    print("\n🎯 检索抽样测试")
    print("─" * 60)

    # 默认测试用查询
    if not queries:
        queries = [
            "枚举值字段类型",
            "计算公式因子",
            "数据表字段定义",
            "边界值处理逻辑",
        ]

    try:
        from kb_rag import KBRetriever
        retriever = KBRetriever()
    except Exception as e:
        print(f"  ❌ 无法初始化检索器: {e}")
        return {}

    results = {}
    for query in queries:
        try:
            hits = retriever.search(query, top_k=3)
            if hits:
                top = hits[0]
                score = top["score"]
                source = top["source"]
                status = "✅" if score > 0.5 else "⚠"
                print(f"  {status} \"{query}\"")
                print(f"     最高相关度: {score:.3f}  来源: {source}")
                if score < 0.4:
                    print(f"     ⚠ 相关度较低，知识库可能缺少此类内容")
            else:
                print(f"  ❌ \"{query}\" → 无结果")
            results[query] = hits[0]["score"] if hits else 0
        except Exception as e:
            print(f"  ❌ 检索失败: {e}")

    avg_score = sum(results.values()) / len(results) if results else 0
    print(f"\n  平均相关度: {avg_score:.3f}", end="  ")
    if avg_score > 0.6:
        print("✅ 检索质量良好")
    elif avg_score > 0.4:
        print("⚠ 检索质量一般，建议补充相关知识库文档")
    else:
        print("❌ 检索质量差，知识库内容可能严重不足")

    return results


# ── 4. 记忆状态 ───────────────────────────────────────────────────────────────
def check_memory() -> dict:
    print("\n🧠 长期记忆状态")
    print("─" * 60)

    mem_dir  = WORKDIR / "memory"
    lt_file  = mem_dir / "long_term.json"

    if not lt_file.exists():
        print("  ○ 暂无长期记忆（首次运行前正常）")
        return {}

    try:
        lt = json.loads(lt_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ❌ 读取记忆失败: {e}")
        return {}

    total = 0
    for key, val in lt.items():
        if isinstance(val, list):
            count = len(val)
            total += count
            status = "✅" if count > 0 else "○"
            print(f"  {status} {key}: {count} 条")
        elif isinstance(val, dict):
            skip = len(val.get("skip", []))
            keep = len(val.get("keep", []))
            total += skip + keep
            print(f"  ✅ {key}: skip={skip}, keep={keep}")

    print(f"\n  记忆总条数: {total}")
    if total < 5:
        print("  ○ 记忆较少，多跑几次 agent 后会越来越准")
    elif total > 200:
        print("  ⚠ 记忆条数较多，建议定期用 memory_review.py 清理低质量条目")
    else:
        print("  ✅ 记忆状态正常")

    # 短期记忆文件
    st_files = list(mem_dir.glob("*.json")) if mem_dir.exists() else []
    st_files = [f for f in st_files if f.name != "long_term.json"]
    if st_files:
        print(f"\n  短期记忆文件: {len(st_files)} 个")

    return {"total": total}


# ── 5. 综合评分 ───────────────────────────────────────────────────────────────
def overall_score(file_stats: dict, idx_stats: dict,
                  retrieval_stats: dict, mem_stats: dict) -> None:
    print("\n📊 综合评估")
    print("─" * 60)

    scores = {}

    # 文件得分
    md_count = file_stats.get("md_count", 0)
    issues   = len(file_stats.get("issues", []))
    if md_count >= 10 and issues == 0:
        scores["文件质量"] = 100
    elif md_count >= 5:
        scores["文件质量"] = max(60, 100 - issues * 10)
    else:
        scores["文件质量"] = max(20, md_count * 10)

    # 索引得分
    idx_status = idx_stats.get("status", "missing")
    scores["索引状态"] = {"ok": 100, "stale": 60, "incomplete": 30, "missing": 0, "error": 0}.get(idx_status, 0)

    # 检索得分
    if retrieval_stats:
        avg = sum(retrieval_stats.values()) / len(retrieval_stats)
        scores["检索质量"] = min(100, int(avg * 150))
    else:
        scores["检索质量"] = 0

    # 记忆得分
    mem_total = mem_stats.get("total", 0)
    scores["记忆积累"] = min(100, mem_total * 5)

    total = sum(scores.values()) / len(scores)
    grade = "🟢 优" if total >= 85 else "🟡 良" if total >= 70 else "🟠 中" if total >= 55 else "🔴 差"

    for name, score in scores.items():
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        print(f"  {name:8} [{bar}] {score:3d}/100")
    print(f"\n  综合得分: {total:.0f}/100  {grade}")

    # 优化建议
    suggestions = []
    if scores["文件质量"] < 70:
        suggestions.append("补充更多知识库文档（数据字典、表设计、开发设计文档）")
    if scores["索引状态"] < 100:
        suggestions.append("运行 python kb_rag.py --rebuild 更新向量索引")
    if scores["检索质量"] < 60:
        suggestions.append("知识库内容不足，检索命中率低，需补充专业文档")
    if scores["记忆积累"] < 30:
        suggestions.append("多运行几次 agent，让系统积累测试经验")

    if suggestions:
        print("\n  💡 优化建议:")
        for s in suggestions:
            print(f"    • {s}")


# ── 交互式检索测试 ────────────────────────────────────────────────────────────
def interactive_search():
    print("\n🔍 交互式检索测试（输入 q 退出）")
    print("─" * 60)
    try:
        from kb_rag import KBRetriever
        retriever = KBRetriever()
        print("  检索器已就绪\n")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return

    while True:
        try:
            query = input("  输入检索词: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() in ("q", "quit", "exit", ""):
            break

        hits = retriever.search(query, top_k=5)
        if not hits:
            print("  无结果\n")
            continue
        print(f"  找到 {len(hits)} 条结果:\n")
        for i, h in enumerate(hits, 1):
            print(f"  [{i}] 相关度: {h['score']:.3f}  来源: {h['source']}")
            print(f"      {h['content'][:200].replace(chr(10), ' ')}")
            print()


# ── 主函数 ────────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="知识库健康检查")
    parser.add_argument("--search", action="store_true", help="交互式检索测试")
    parser.add_argument("--fix",    action="store_true", help="自动修复可修复的问题")
    parser.add_argument("--quick",  action="store_true", help="快速检查（跳过检索测试）")
    args = parser.parse_args()

    if args.search:
        interactive_search()
        return

    print("=" * 60)
    print("  TestCaseMind 知识库健康检查")
    print(f"  {__import__('time').strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    file_stats      = check_files()
    idx_stats       = check_index()
    retrieval_stats = {} if args.quick else check_retrieval()
    mem_stats       = check_memory()

    overall_score(file_stats, idx_stats, retrieval_stats, mem_stats)

    if args.fix:
        print("\n🔧 自动修复")
        print("─" * 60)
        # 未转换的 docx
        for f in KB_DIR.rglob("*.docx"):
            if not f.with_suffix(".md").exists():
                print(f"  转换: {f.name}")
                import subprocess
                docx2md = WORKDIR / "docx2md.py"
                if docx2md.exists():
                    subprocess.run([sys.executable, str(docx2md), str(f)], check=False)
        # 重建过期索引
        if idx_stats.get("status") == "stale":
            print("  重建索引...")
            import subprocess
            subprocess.run([sys.executable, str(WORKDIR / "kb_rag.py"), "--rebuild"], check=False)

    print()


if __name__ == "__main__":
    main()
