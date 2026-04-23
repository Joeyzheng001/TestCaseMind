#!/usr/bin/env python3
"""
kb_convert.py - 知识库预处理

把 knowledge_base/ 下的 Word 文档(.docx)转换成 .md 文件，
方便后续 grep 检索。依赖 pandoc（brew install pandoc）。

用法:
    python kb_convert.py              # 转换所有未转换的 docx
    python kb_convert.py --all        # 强制重转所有 docx（覆盖已有 md）
    python kb_convert.py --check      # 只查看待转换文件列表，不执行
    python kb_convert.py --file x.docx  # 转换单个文件
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

KB_DIR = Path(__file__).parent / "knowledge_base"


def check_tool() -> bool:
    try:
        subprocess.run(["pandoc", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def convert_docx(docx_path: Path, force: bool = False) -> tuple:
    """转换单个 docx → md，返回 (成功, 信息)。"""
    md_path = docx_path.with_suffix(".md")

    if md_path.exists() and not force:
        return True, "已跳过（md 已存在，用 --all 强制重转）"

    try:
        result = subprocess.run(
            ["pandoc", str(docx_path), "-t", "markdown", "-o", str(md_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return False, f"pandoc 错误: {result.stderr[:200]}"

        # 读出来做简单清理
        content = md_path.read_text(encoding="utf-8")
        # 连续空行压缩为 2 个
        content = re.sub(r"\n{3,}", "\n\n", content)
        md_path.write_text(content, encoding="utf-8")

        size_kb = md_path.stat().st_size // 1024
        return (
            True,
            f"完成 → {md_path.name} ({size_kb} KB, {len(content.splitlines())} 行)",
        )

    except subprocess.TimeoutExpired:
        return False, "超时（60s）"
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="知识库 Word → Markdown 转换器")
    parser.add_argument("--check", action="store_true", help="只列出文件，不执行转换")
    parser.add_argument("--all", action="store_true", help="强制重转所有文件")
    parser.add_argument("--file", type=str, help="只转换指定文件名")
    args = parser.parse_args()

    if not args.check and not check_tool():
        print("错误: pandoc 不可用，请先安装: brew install pandoc")
        sys.exit(1)

    # 收集目标文件
    if args.file:
        target = KB_DIR / args.file
        if not target.exists():
            print(f"错误: 找不到 {target}")
            sys.exit(1)
        docx_files = [target]
    else:
        docx_files = sorted(KB_DIR.glob("**/*.docx"))

    if not docx_files:
        print(f"knowledge_base/ 下没有找到 .docx 文件，请把 Word 文档放入: {KB_DIR}")
        return

    # 显示文件列表
    print(f"\n找到 {len(docx_files)} 个 Word 文档:\n")
    for f in docx_files:
        md = f.with_suffix(".md")
        status = "✓ 已转换" if md.exists() else "○ 待转换"
        print(f"  {status}  {f.relative_to(KB_DIR)}  ({f.stat().st_size // 1024} KB)")

    if args.check:
        return

    to_convert = (
        docx_files
        if args.all
        else [f for f in docx_files if not f.with_suffix(".md").exists()]
    )

    if not to_convert:
        print("\n所有文件已转换。用 --all 强制重转。")
        return

    print(f"\n开始转换 {len(to_convert)} 个文件...\n")
    ok, fail = 0, 0

    for docx in to_convert:
        print(f"  转换: {docx.relative_to(KB_DIR)}")
        success, msg = convert_docx(docx, force=args.all)
        print(f"  {'✓' if success else '✗'} {msg}\n")
        if success:
            ok += 1
        else:
            fail += 1

    print(f"{'─' * 40}")
    print(f"完成: {ok} 成功  {fail} 失败")
    if ok:
        md_count = len(list(KB_DIR.glob("**/*.md")))
        print(f"\n知识库现有 {md_count} 个 md 文件，可运行:")
        print(f"  python agent.py <需求文档> --kb")


if __name__ == "__main__":
    main()
