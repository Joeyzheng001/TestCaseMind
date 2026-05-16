"""
Markdown 数据清洗：去水印、页眉页脚、页码、重复标题、乱码、多余换行、断裂段落、无意义空格、参考文献编号标准化。
不修改原文件，输出到 cleaned/ 目录。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KB_ROOT = PROJECT_ROOT / "knowledge_base" / "references"
KB_CLEANED_ROOT = KB_ROOT / "cleaned"


def clean_all_md_files(
    source_dir: Optional[Path] = None, output_dir: Optional[Path] = None
) -> int:
    """清洗所有 MD 文件。返回清洗文件数。"""
    src = source_dir or (KB_ROOT / "converted")
    dst = output_dir or KB_CLEANED_ROOT
    dst.mkdir(parents=True, exist_ok=True)

    files = list(src.rglob("*.md"))
    cleaned_count = 0
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
            # 跳过已损坏或二进制文件
            if len(raw) < 100 or "\x00" in raw:
                continue
            clean = clean_text(raw, path.stem)
            if clean and len(clean) > 100:
                rel = path.relative_to(src)
                out = dst / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(clean, encoding="utf-8")
                cleaned_count += 1
        except Exception:
            continue
    return cleaned_count


def clean_text(text: str, title_hint: str = "") -> str:
    """对单篇论文全文执行完整清洗流水线。"""
    text = _fix_encoding(text)
    text = _remove_watermarks(text)
    text = _remove_headers_footers(text)
    text = _remove_page_numbers(text)
    text = _remove_duplicate_titles(text, title_hint)
    text = _normalize_newlines(text)
    text = _repair_urls(text)
    text = _repair_broken_paragraphs(text)
    text = _remove_meaningless_spaces(text)
    text = _normalize_reference_numbering(text)
    text = _remove_empty_sections(text)
    text = _trim_noise_prefix_suffix(text)
    return text.strip()


# ---- 内部清洗函数 ----

def _fix_encoding(text: str) -> str:
    """修复常见乱码字符。"""
    replacements = {
        "﻿": "",          # BOM
        "�": "",          # 替换字符
        " ": " ",         # 非断空格
        "​": "",          # 零宽空格
        "‎": "",          # 左右标记
        "‏": "",
        " ": "\n",        # 行分隔符
        " ": "\n\n",      # 段分隔符
        "�": "",               # 常见乱码
        "\x00": "",            # NULL
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # 修复被 OCR 拆散的汉字（单字空格模式如 "质 量 管 理"）
    text = re.sub(r"(?<=[一-鿿])\s(?=[一-鿿])", "", text)
    return text


def _remove_watermarks(text: str) -> str:
    """去除常见水印模式。"""
    patterns = [
        r"(?:学位论文|硕士学位论文|博士学位论文|硕士论文|博士论文|毕业论文)\s*[（(]?(?:送审|答辩|终稿|最终|盲审)?[版稿本]?[）)]?\s*",
        r"(?:机密|绝密|内部资料|仅供学术交流|请勿外传)\s*",
        r"(?:原创性声明|独创性声明|学位论文原创性声明)[\s\S]{50,300}?(?=摘要|目录|第[一二三四五六七八九十]章)",
        r"(?:中国知网|CNKI|万方数据|维普)\s*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text


def _remove_headers_footers(text: str) -> str:
    """去除重复出现的页眉页脚模式。"""
    # 常见页眉：每页重复的短行（如 "XX大学硕士学位论文"）
    lines = text.split("\n")
    if len(lines) < 10:
        return text

    # 统计每行出现频率，删除高频重复短行
    from collections import Counter

    line_counts = Counter(line.strip() for line in lines if 3 < len(line.strip()) < 60)
    to_remove = {line for line, count in line_counts.items()
                 if count > len(lines) * 0.15 and count > 3}

    if to_remove:
        lines = [l for l in lines if l.strip() not in to_remove]
    return "\n".join(lines)


def _remove_page_numbers(text: str) -> str:
    """去除独立行页码和页标记。"""
    # 独立数字行（页码）
    text = re.sub(r"^\s*-?\s*\d{1,4}\s*-?\s*$", "", text, flags=re.MULTILINE)
    # "第X页" 模式
    text = re.sub(r"第\s*\d{1,4}\s*页", "", text)
    # PDF 转换产生的页标记: "## Page 81", "- Page 42 -" 等
    text = re.sub(r"^#{1,3}\s*Page\s+\d+\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"^-\s*Page\s+\d+\s*-?\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    # 页标记后紧跟的页眉文字（如 "浙江大学参考文献" 独立出现）
    text = re.sub(r"^#{1,3}\s*Page\s+\d+\s*\n(?:[一-鿿]{2,10}(?:大学|学院).{0,20}参考文献?\s*)", "", text, flags=re.MULTILINE)
    return text


def _remove_duplicate_titles(text: str, title_hint: str = "") -> str:
    """去除正文中重复出现的论文标题。"""
    lines = text.split("\n")
    cleaned_lines = []
    seen_title = False
    # 用前 80 个非空字符作为标题候选
    title_candidates = set()
    for line in lines[:20]:
        line = line.strip()
        if 5 < len(line) < 80 and (
            "研究" in line or "管理" in line or "分析" in line or "优化" in line
        ):
            title_candidates.add(line)

    for line in lines:
        stripped = line.strip()
        if stripped in title_candidates:
            if not seen_title:
                seen_title = True
                cleaned_lines.append(line)
            # 跳过重复标题
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _normalize_newlines(text: str) -> str:
    """规范化换行：3 个以上连续换行压缩为 2 个。"""
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 中文行尾去换行（段落内换行合并）
    text = re.sub(r"(?<=[一-鿿])\n(?=[一-鿿])", "", text)
    return text


def _repair_urls(text: str) -> str:
    """修复 PDF 提取导致的 URL 损坏：跨行截断、多余空格、常见域名缺字。"""
    # 1. 先去除 URL 内部空格（合法 URL 不含空格）—— 必须在拼接之前，否则空格会导致拼接判据失败
    def _despace_url(m: re.Match) -> str:
        return m.group(0).replace(" ", "")
    text = re.sub(r"https?://[^\s。，；：、（《】\n]{5,}(?:\s+[^\s。，；：、（《】\n]{2,})*", _despace_url, text)
    # 2. 修复特定断裂数字模式（如 content_5\n725275.htm）
    text = re.sub(r"(content_|info|t\d{8}_)(\d{1,4})\n(\d{4,10})(\.htm)", r"\1\2\3\4", text)
    # 3. 连接被换行截断的 URL（第二行无空格且全是合法 URL 字符）
    text = re.sub(
        r"(https?://[^\n]+)\n([^\n]{4,})",
        lambda m: m.group(1) + m.group(2) if re.match(r"^[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+$", m.group(2)) else m.group(0),
        text,
    )
    # 4. 连接 DOI 被截断
    text = re.sub(
        r"(doi\.org/[^\n]+)\n([^\n]{4,})",
        lambda m: m.group(1) + m.group(2) if re.match(r"^[a-zA-Z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+$", m.group(2)) else m.group(0),
        text,
    )
    # 5. 常见域名缺字
    text = re.sub(r"https?://kns\.\.net/", "https://kns.cnki.net/", text)
    text = re.sub(r"http?://kns\.\.net/", "http://kns.cnki.net/", text)
    return text


def _repair_broken_paragraphs(text: str) -> str:
    """修复断裂段落：连接被 PDF 转换截断的句子。"""
    # 英文行尾连字符断裂
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    lines = text.split("\n")
    repaired = []
    buffer = ""
    in_yaml = False
    for line in lines:
        stripped = line.strip()

        # 保持 YAML 前页不会合并
        if stripped == "---":
            if buffer:
                repaired.append(buffer)
                buffer = ""
            in_yaml = not in_yaml
            repaired.append(line)
            continue
        if in_yaml:
            repaired.append(line)
            continue

        # 保持空行和元数据行
        if not stripped:
            if buffer:
                repaired.append(buffer)
                buffer = ""
            repaired.append("")
            continue

        # 不合并元数据行 (key: value) 或 Page 标记
        if re.match(r"^(?:[a-z_]+|tags?|methodologies?|research_direction|category):\s", stripped, re.IGNORECASE):
            if buffer:
                repaired.append(buffer)
                buffer = ""
            repaired.append(line)
            continue
        if re.match(r"^##\s*Page\s+\d+", stripped):
            # Page 标记直接丢弃，不保留
            continue

        # 行首有标点/数字/括号 → 新段落开始
        if buffer and (
            stripped[0] in "([（第123456789"
            or re.match(r"^\d+[.、)]", stripped)
        ):
            repaired.append(buffer)
            buffer = stripped
        # 上一行以句末标点结束 → 段落边界
        elif buffer and buffer[-1] in "。！？…"")""」』》】:：":
            repaired.append(buffer)
            buffer = stripped
        else:
            buffer = (buffer + stripped) if buffer else stripped

    if buffer:
        repaired.append(buffer)
    return "\n".join(repaired)


def _remove_meaningless_spaces(text: str) -> str:
    """去除无意义空格。"""
    # 中文间的空格
    text = re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", text)
    # 行首行尾空格
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    # 中文标点前的空格
    text = re.sub(r"\s+([，。！？；：、》」』】）\)])", r"\1", text)
    return text


def _normalize_reference_numbering(text: str) -> str:
    """标准化参考文献编号。"""
    ref_section_start = _find_reference_section(text)
    if not ref_section_start:
        return text

    prefix = text[:ref_section_start]
    ref_section = text[ref_section_start:]

    # 统一编号为 [1] [2] ...
    counter = [0]

    def renumber(match):
        counter[0] += 1
        return f"[{counter[0]}] "

    # 匹配各种编号格式
    ref_section = re.sub(
        r"^(?:\d+[.)]\s*|\[\d+\]\s*|【\d+】\s*)",
        renumber,
        ref_section,
        flags=re.MULTILINE,
    )

    return prefix + ref_section


def _remove_empty_sections(text: str) -> str:
    """删除空白过度的节标题。"""
    lines = text.split("\n")
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 孤立标题后无内容
        if re.match(r"^(?:第[一二三四五六七八九十\d]+章|[\d.]+\s*\S)", stripped):
            # 检查后续 3 行是否有内容
            subsequent = "\n".join(lines[i + 1:i + 4]).strip()
            if len(subsequent) < 20:
                continue
        result.append(line)
    return "\n".join(result)


def _trim_noise_prefix_suffix(text: str) -> str:
    """去除正文前后的噪声段落（如版权声明、致谢中的人名列表等）。"""
    # 去掉开头连续的空行和短行（但保留 YAML frontmatter）
    lines = text.split("\n")
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("---", "..."):
            start_idx = i
            break
        if len(stripped) > 15 or ":" in stripped:
            start_idx = i
            break
    # 去掉末尾的致谢/附录等
    end_markers = ["致谢", "致  谢", "Acknowledgement", "附录", "攻读学位期间发表的学术论文"]
    end_idx = len(lines)
    for i in range(len(lines) - 1, max(start_idx, len(lines) // 2), -1):
        for marker in end_markers:
            if marker in lines[i]:
                end_idx = i
                break
        if end_idx < len(lines):
            break

    return "\n".join(lines[start_idx:end_idx])


def _find_reference_section(text: str) -> int:
    """定位参考文献章节的起始位置。"""
    patterns = [
        r"^#{1,3}\s*参考文献\s*$",
        r"^参考文献\s*$",
        r"^【参考文献】\s*$",
        r"^References?\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.start()
    return 0
