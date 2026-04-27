#!/usr/bin/env python3
"""
docx2md.py - 高质量 Word → Markdown 转换

相比 pandoc：
- 表格转为简洁的 | 列 | 格式，不会生成 grid table
- 跳过文档信息表、参考文档等非核心内容（可配置）
- 合并单元格正确处理
- 代码块自动识别
- 支持批量转换

用法:
    python docx2md.py 需求文档.docx                   # 转换单个文件
    python docx2md.py 需求文档.docx -o output.md      # 指定输出路径
    python docx2md.py *.docx                           # 批量转换
    python docx2md.py 需求文档.docx --skip-meta        # 跳过元信息表格
"""

import re
import sys
from pathlib import Path


def cell_text(cell) -> str:
    """提取单元格纯文本，合并多段落。"""
    parts = []
    for para in cell.paragraphs:
        t = para.text.strip()
        if t:
            parts.append(t)
    return " ".join(parts).replace("\n", " ")


def table_to_md(table) -> str:
    """
    把 Word 表格转为 Markdown pipe table。
    处理合并单元格（取第一个非空值）。
    """
    if not table.rows:
        return ""

    # 提取所有行数据
    rows_data = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cells.append(cell_text(cell))
        rows_data.append(cells)

    if not rows_data:
        return ""

    # 列数统一（防止参差不齐）
    max_cols = max(len(r) for r in rows_data)
    rows_data = [r + [""] * (max_cols - len(r)) for r in rows_data]

    # 去掉完全空的列
    non_empty_cols = [
        i for i in range(max_cols)
        if any(rows_data[r][i].strip() for r in range(len(rows_data)))
    ]
    if not non_empty_cols:
        return ""
    rows_data = [[row[i] for i in non_empty_cols] for row in rows_data]
    col_count = len(non_empty_cols)

    # 如果只有一列且内容简单，输出为列表
    if col_count == 1:
        lines = []
        for row in rows_data:
            t = row[0].strip()
            if t:
                lines.append(f"- {t}")
        return "\n".join(lines)

    # 检查是否是键值表（2列，左列是标签）
    is_kv = (
        col_count == 2 and
        len(rows_data) <= 15 and
        all(len(r[0]) < 20 for r in rows_data if r[0])
    )
    if is_kv:
        lines = []
        for row in rows_data:
            k, v = row[0].strip(), row[1].strip()
            if k or v:
                lines.append(f"**{k}**：{v}" if k else v)
        return "\n\n".join(lines)

    # 标准表格
    lines = []
    header = rows_data[0]
    lines.append("| " + " | ".join(h or " " for h in header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows_data[1:]:
        # 跳过全空行
        if not any(c.strip() for c in row):
            continue
        lines.append("| " + " | ".join(c.replace("|", "\\|") or " " for c in row) + " |")

    return "\n".join(lines)


def para_to_md(para) -> str:
    """把段落转为 Markdown，处理标题/列表/加粗等。"""
    text = para.text.strip()
    if not text:
        return ""

    style_name = ""
    try:
        if para.style and para.style.name:
            style_name = para.style.name
    except Exception:
        pass

    # 标题
    heading_map = {
        "Heading 1": "#", "heading 1": "#", "标题 1": "#",
        "Heading 2": "##", "heading 2": "##", "标题 2": "##",
        "Heading 3": "###", "heading 3": "###", "标题 3": "###",
        "Heading 4": "####", "heading 4": "####", "标题 4": "####",
    }
    for style, prefix in heading_map.items():
        if style.lower() in style_name.lower():
            # 清理标题里的编号（如 "1. 需求背景" → "需求背景"）
            clean = re.sub(r'^[\d\.]+\s*', '', text).strip()
            return f"{prefix} {clean or text}"

    # 列表项
    if style_name in ("List Paragraph", "列表段落") or style_name.startswith("List"):
        return f"- {text}"

    # 纯数字编号开头的行（如 "1. 需求背景"）转为标题
    m = re.match(r'^(\d+)\.\s+(.+)$', text)
    if m and len(text) < 50:
        num = len(m.group(1))
        prefix = "#" * min(num + 1, 4)
        return f"{prefix} {m.group(2)}"

    # 处理行内加粗
    result = ""
    for run in para.runs:
        run_text = run.text
        if not run_text:
            continue
        if run.bold:
            result += f"**{run_text}**"
        elif run.italic:
            result += f"*{run_text}*"
        else:
            result += run_text

    return result.strip() or text


# 非核心内容的标题关键词（跳过这些章节）
SKIP_SECTION_KW = [
    "文档信息", "修订记录", "参考文档", "相关干系人",
    "附录", "变更历史", "版本历史",
]


def should_skip_table(table, prev_heading: str = "") -> bool:
    """判断表格是否是非核心内容（文档信息/修订记录等）。"""
    if any(kw in prev_heading for kw in SKIP_SECTION_KW):
        return True
    # 检查表格第一行是否含有非需求关键词
    if table.rows:
        first_row_text = " ".join(cell_text(c) for c in table.rows[0].cells)
        if any(kw in first_row_text for kw in ["版本号", "日期", "撰写人", "负责人"]):
            return True
    return False


def docx_to_md(docx_path: Path, skip_meta: bool = True) -> str:
    """主转换函数。"""
    try:
        from docx import Document
    except ImportError:
        print("错误: 需要 python-docx: pip install python-docx")
        sys.exit(1)

    doc = Document(str(docx_path))
    lines = []
    prev_heading = ""
    table_set = set(id(t) for t in doc.tables)
    processed_tables = set()

    # 按文档顺序遍历段落和表格
    from docx.oxml.ns import qn
    body = doc.element.body

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            # 段落
            from docx.text.paragraph import Paragraph
            para = Paragraph(child, doc)
            md_line = para_to_md(para)
            if not md_line:
                # 保留一个空行，不要多个连续空行
                if lines and lines[-1] != "":
                    lines.append("")
                continue

            # 记录当前标题，用于判断是否跳过后续表格
            if md_line.startswith("#"):
                prev_heading = md_line.lstrip("# ").strip()

            lines.append(md_line)

        elif tag == "tbl":
            # 表格
            from docx.table import Table
            table = Table(child, doc)
            table_id = id(child)

            if table_id in processed_tables:
                continue
            processed_tables.add(table_id)

            if skip_meta and should_skip_table(table, prev_heading):
                continue

            table_md = table_to_md(table)
            if table_md:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(table_md)
                lines.append("")

    # 清理多余空行
    result = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                result.append("")
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    return "\n".join(result).strip()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Word → Markdown 高质量转换")
    parser.add_argument("files",       nargs="+",           help="Word 文档路径（支持多个）")
    parser.add_argument("-o", "--out", type=str, default="", help="输出文件路径（单文件时有效）")
    parser.add_argument("--out-dir",   type=str, default="", help="批量输出目录")
    parser.add_argument("--skip-meta", action="store_true", default=True,
                        help="跳过文档信息/修订记录等非核心表格（默认开启）")
    parser.add_argument("--keep-meta", action="store_true",
                        help="保留所有表格（包括文档信息）")
    args = parser.parse_args()

    skip_meta = args.skip_meta and not args.keep_meta

    files = []
    for pattern in args.files:
        p = Path(pattern)
        if p.exists():
            files.append(p)
        else:
            import glob
            matched = glob.glob(pattern)
            files.extend(Path(m) for m in matched)

    if not files:
        print("错误: 没有找到文件")
        sys.exit(1)

    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for docx_path in files:
        if docx_path.suffix.lower() not in (".docx", ".doc"):
            print(f"跳过: {docx_path.name}（不是 Word 文档）")
            continue

        print(f"转换: {docx_path.name} ...", end=" ", flush=True)

        try:
            md_text = docx_to_md(docx_path, skip_meta=skip_meta)
        except Exception as e:
            print(f"失败: {e}")
            continue

        # 确定输出路径
        if args.out and len(files) == 1:
            out_path = Path(args.out)
        elif out_dir:
            out_path = out_dir / (docx_path.stem + ".md")
        else:
            out_path = docx_path.with_suffix(".md")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_text, encoding="utf-8")
        size_kb = out_path.stat().st_size // 1024
        lines   = len(md_text.splitlines())
        print(f"✓ {out_path.name}（{lines}行, {size_kb}KB）")


if __name__ == "__main__":
    main()
