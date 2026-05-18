"""
论文导出工具。

Word 优先复用知识库中的论文格式模板；PDF 使用本地字体渲染分页，
避免依赖外部 LaTeX/浏览器服务。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple, Union


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output"
TEMPLATE_CANDIDATES = [
    PROJECT_ROOT / "knowledge_base/references/3.0 论文格式_复旦MEM硕士论文参考模版_飞哥ProMax版2025✅(1).docx",
    PROJECT_ROOT / "knowledge_base/references/3.0 论文格式docx.docx",
]


_MD_TABLE_ROW_RE = re.compile(r"^\|.+\|$")


def _parse_markdown_table(lines: List[str]) -> Tuple[List[str], List[str], List[List[str]]]:
    """Parse a markdown table from lines. Returns (headers, alignments, rows)."""
    raw = [line.strip() for line in lines if line.strip()]
    if len(raw) < 2:
        return [], [], []

    def _cells(line: str) -> List[str]:
        s = line.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        return [c.strip() for c in s.split("|")]

    def _parse_align(cell: str) -> str:
        cell = cell.strip().strip(":-")
        if cell.startswith(":") and cell.endswith(":"):
            return "center"
        elif cell.endswith(":"):
            return "right"
        return "left"

    headers = _cells(raw[0])
    aligns = [_parse_align(c) for c in raw[1].split("|") if c.strip() and c.strip().replace("-", "").replace(":", "") == ""]
    if not aligns:
        aligns = ["left"] * len(headers)
    while len(aligns) < len(headers):
        aligns.append("left")
    rows = [_cells(r) for r in raw[2:]]
    return headers, aligns[:len(headers)], rows


def _split_content_segments(text: str) -> List[Dict[str, Any]]:
    """Split text into segments of type 'text' or 'table'. Each segment is {type, data}."""
    if not text:
        return []
    lines = text.splitlines()
    segments = []
    buf = []
    table_lines = []

    def _flush_text():
        nonlocal buf
        content = "\n".join(buf).strip()
        if content:
            segments.append({"type": "text", "data": content})
        buf = []

    def _flush_table():
        nonlocal table_lines
        headers, aligns, rows = _parse_markdown_table(table_lines)
        if headers:
            segments.append({"type": "table", "data": {"headers": headers, "aligns": aligns, "rows": rows}})
        table_lines = []

    for line in lines:
        if _MD_TABLE_ROW_RE.match(line.strip()):
            _flush_text()
            table_lines.append(line)
        else:
            if table_lines:
                _flush_table()
            buf.append(line)

    if table_lines:
        _flush_table()
    _flush_text()
    return segments


def clean_heading(title: str, number: str = "") -> str:
    value = re.sub(r"^#{1,6}\s*", "", str(title or "")).strip()
    if number:
        value = re.sub(rf"^{re.escape(number)}\s+", "", value)
    value = re.sub(r"^\d+(?:\.\d+){0,3}\s+", "", value)
    return value.strip()


def clean_body_text(text: str, number: str = "", title: str = "") -> str:
    value = re.sub(r"^#{1,6}\s*", "", str(text or ""), flags=re.MULTILINE).strip()
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    title = clean_heading(title, number)
    lines = [line.strip() for line in value.splitlines()]
    output = []
    for index, line in enumerate(lines):
        bare = clean_heading(line, number)
        looks_like_heading = (
            bool(re.match(r"^第[一二三四五六七八九十\d]+章", line))
            or bool(re.match(r"^\d+(?:\.\d+){1,3}\s+\S{2,80}$", line))
            or bool(number and line.startswith(number))
            or bool(title and bare == title)
        )
        if index < 5 and looks_like_heading:
            continue
        if line and output and output[-1] == line:
            continue
        output.append(line)
    return "\n".join(output).strip()


def _iter_blocks(outline: Dict[str, Any], drafts: Dict[str, str]) -> Iterable[Tuple[int, str]]:
    yield 0, clean_heading(outline.get("title", "论文正文")).replace("论文:", "").strip()
    for chapter in outline.get("chapters", []):
        yield 1, clean_heading(chapter.get("title", ""))
        for section in chapter.get("sections", []):
            yield 2, f"{section.get('number')} {clean_heading(section.get('title', ''), section.get('number', ''))}"
            subsections = section.get("subsections") or []
            if subsections:
                for subsection in subsections:
                    number = subsection.get("number", "")
                    yield 3, f"{number} {clean_heading(subsection.get('title', ''), number)}"
                    draft = clean_body_text(drafts.get(number, ""), number, subsection.get("title", ""))
                    if draft:
                        yield 4, draft
            else:
                number = section.get("number", "")
                draft = clean_body_text(drafts.get(number, ""), number, section.get("title", ""))
                if draft:
                    yield 4, draft


def _template_path() -> Path | None:
    for path in TEMPLATE_CANDIDATES:
        if path.exists():
            return path
    return None


def _clear_document_body(document: Any) -> None:
    body = document._element.body
    for child in list(body):
        if child.tag.endswith("sectPr"):
            continue
        body.remove(child)


def _set_run_font(run, font_name: str, size=None, bold=False):
    """设置 run 的拉丁和东亚字体。"""
    run.font.name = font_name
    run._element.rPr.rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia', font_name)
    if size:
        run.font.size = size
    run.bold = bold


def export_docx(outline: Dict[str, Any], drafts: Dict[str, str], citations: List[Dict[str, Any]] = None) -> Path:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    from docx.oxml.ns import qn

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_ROOT / "thesis_export.docx"
    template = _template_path()
    document = Document(str(template)) if template else Document()
    if template:
        _clear_document_body(document)

    section = document.sections[0]
    section.top_margin = Pt(72)
    section.bottom_margin = Pt(72)
    section.left_margin = Pt(90)
    section.right_margin = Pt(90)

    # Normal style: 宋体 12pt
    normal = document.styles["Normal"]
    normal.font.name = "宋体"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

    for level, text in _iter_blocks(outline, drafts):
        if not text:
            continue
        if level == 0:
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(text)
            _set_run_font(run, "黑体", Pt(18), bold=True)
        elif level in {1, 2, 3}:
            paragraph = document.add_heading(text, level=min(level, 3))
            for run in paragraph.runs:
                _set_run_font(run, "黑体", bold=True)
        else:
            segments = _split_content_segments(text)
            for seg in segments:
                if seg["type"] == "table":
                    tbl = seg["data"]
                    headers = tbl["headers"]
                    aligns = tbl["aligns"]
                    rows = tbl["rows"]
                    if not headers:
                        continue
                    ncols = len(headers)
                    docx_table = document.add_table(rows=1 + len(rows), cols=ncols)
                    docx_table.style = "Table Grid"
                    # Header row
                    for ci, hdr in enumerate(headers):
                        cell = docx_table.rows[0].cells[ci]
                        cell.text = ""
                        run = cell.paragraphs[0].add_run(hdr)
                        _set_run_font(run, "宋体", Pt(10.5), bold=True)
                        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    # Data rows
                    for ri, row in enumerate(rows):
                        for ci, val in enumerate(row):
                            cell = docx_table.rows[ri + 1].cells[ci]
                            cell.text = ""
                            run = cell.paragraphs[0].add_run(val)
                            _set_run_font(run, "宋体", Pt(10.5))
                            if ci < len(aligns):
                                if aligns[ci] == "center":
                                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                                elif aligns[ci] == "right":
                                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
                    # Add spacing after table
                    spacer = document.add_paragraph("")
                    spacer.paragraph_format.line_spacing = Pt(6)
                else:
                    for part in re.split(r"\n{2,}", seg["data"]):
                        paragraph = document.add_paragraph(part.strip())
                        paragraph.paragraph_format.first_line_indent = Pt(24)
                        paragraph.paragraph_format.line_spacing = 1.5
                        for run in paragraph.runs:
                            _set_run_font(run, "宋体", Pt(12))

    # Append references
    if citations:
        ref_heading = document.add_heading("参考文献", level=1)
        for run in ref_heading.runs:
            _set_run_font(run, "黑体", bold=True)

        for i, c in enumerate(citations):
            formatted = c.get("formatted", "").strip()
            if not formatted:
                continue
            para = document.add_paragraph(f"[{i+1}] {formatted}")
            para.paragraph_format.line_spacing = 1.5
            for run in para.runs:
                _set_run_font(run, "宋体", Pt(10.5))

    document.save(path)
    return path


def _chinese_font_path() -> str:
    candidates = [
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "C:\\Windows\\Fonts\\simsun.ttc",
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    raise RuntimeError(
        "未找到中文字体文件。请安装 Noto Sans CJK 或设置 THESISMIND_FONT 环境变量指向一个 .ttf/.ttc 文件。\n"
        "macOS: 系统自带宋体\n"
        "Linux: sudo apt install fonts-noto-cjk\n"
        "Windows: 系统自带宋体/微软雅黑"
    )


def _draw_pdf_table(pdf, headers: List[str], aligns: List[str], rows: List[List[str]], body_width: float) -> None:
    """Draw a formatted table in the PDF document."""
    ncols = len(headers)
    if ncols == 0:
        return
    col_w = body_width / ncols
    line_h = 5.5
    font_size = 8

    estimated_h = (len(rows) + 1) * (line_h + 2) + 4
    if pdf.get_y() + estimated_h > pdf.h - pdf.b_margin:
        pdf.add_page()

    x0 = pdf.l_margin

    def _draw_row(cells, bold=False):
        pdf.set_font("CJK", "B" if bold else "", size=font_size)
        y = pdf.get_y()
        for ci in range(ncols):
            cell_text = cells[ci] if ci < len(cells) else ""
            if len(cell_text) > 80:
                cell_text = cell_text[:77] + "..."
            pdf.set_xy(x0 + ci * col_w, y)
            a = aligns[ci][0].upper() if ci < len(aligns) else "L"
            pdf.cell(col_w, line_h + 2, cell_text, border=1, align=a)
        pdf.set_xy(x0, y + line_h + 2)

    _draw_row(headers, bold=True)
    for row in rows:
        _draw_row(row)

    pdf.ln(4)


def export_pdf(outline: Dict[str, Any], drafts: Dict[str, str], citations: List[Dict[str, Any]] = None) -> Path:
    from fpdf import FPDF

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_ROOT / "thesis_export.pdf"

    font_path = _chinese_font_path()
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    font_sizes = {0: 22, 1: 16, 2: 13, 3: 11, 4: 10.5}

    try:
        pdf.add_font("CJK", "", font_path, uni=True)
        pdf.add_font("CJK", "B", font_path, uni=True)
    except Exception:
        pdf.add_font("CJK", font_path, uni=True)
        pdf.add_font("CJK", "B", font_path, uni=True)

    body_width = pdf.w - pdf.l_margin - pdf.r_margin

    for level, text in _iter_blocks(outline, drafts):
        if not text:
            continue

        size = font_sizes.get(level, 10.5)
        pdf.set_font("CJK", "B" if level <= 3 else "", size=size)

        if level == 0:
            pdf.set_font("CJK", "B", size=size)
            pdf.multi_cell(body_width, size * 1.4, text, align="C")
            pdf.ln(10)
        elif level == 1:
            pdf.ln(4)
            pdf.multi_cell(body_width, size * 1.3, text)
            pdf.ln(2)
        elif level in (2, 3):
            pdf.ln(2)
            indent = (level - 1) * 8
            pdf.set_x(pdf.l_margin + indent)
            pdf.multi_cell(body_width - indent, size * 1.2, text)
        else:
            pdf.set_font("CJK", "", size=size)
            segments = _split_content_segments(text)
            for seg in segments:
                if seg["type"] == "table":
                    tbl = seg["data"]
                    _draw_pdf_table(pdf, tbl["headers"], tbl["aligns"], tbl["rows"], body_width)
                else:
                    for paragraph in re.split(r"\n{2,}", seg["data"]):
                        para = paragraph.strip()
                        if not para:
                            continue
                        pdf.multi_cell(body_width, size * 1.55, para, align="L")
                        pdf.ln(1)

    # Append references
    if citations:
        pdf.add_page()
        pdf.set_font("CJK", "B", size=16)
        pdf.multi_cell(body_width, 22, "参考文献", align="L")
        pdf.ln(6)
        pdf.set_font("CJK", "", size=9)
        for i, c in enumerate(citations):
            formatted = c.get("formatted", "").strip()
            if not formatted:
                continue
            ref_line = f"[{i+1}] {formatted}"
            pdf.multi_cell(body_width, 12, ref_line, align="L")
            pdf.ln(1)

    pdf.output(path)
    return path
