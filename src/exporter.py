"""
论文导出工具。

Word 优先复用知识库中的论文格式模板；PDF 使用本地字体渲染分页，
避免依赖外部 LaTeX/浏览器服务。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output"
TEMPLATE_CANDIDATES = [
    PROJECT_ROOT / "knowledge_base/references/3.0 论文格式_复旦MEM硕士论文参考模版_飞哥ProMax版2025✅(1).docx",
    PROJECT_ROOT / "knowledge_base/references/3.0 论文格式docx.docx",
]


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


def export_docx(outline: Dict[str, Any], drafts: Dict[str, str]) -> Path:
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
            for part in re.split(r"\n{2,}", text):
                paragraph = document.add_paragraph(part.strip())
                paragraph.paragraph_format.first_line_indent = Pt(24)
                paragraph.paragraph_format.line_spacing = 1.5
                for run in paragraph.runs:
                    _set_run_font(run, "宋体", Pt(12))

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


def export_pdf(outline: Dict[str, Any], drafts: Dict[str, str]) -> Path:
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
            for paragraph in re.split(r"\n{2,}", text):
                para = paragraph.strip()
                if not para:
                    continue
                pdf.multi_cell(body_width, size * 1.55, para, align="L")
                pdf.ln(1)

    pdf.output(path)
    return path
