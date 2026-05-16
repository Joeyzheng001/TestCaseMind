#!/usr/bin/env python3
"""论文 PDF 自动分类 —— 按标题/摘要关键词归入子目录。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent / "knowledge_base" / "references" / "论文类"

# 优先级从高到低：先匹配到的类别胜出
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("质量管理", [
        r"质量(?!风险)",          # 质量但不紧跟"风险"
        r"DMAIC",
        r"六西格玛",
        r"QFD",
        r"FMEA",
    ]),
    ("风险管理", [
        r"风险",
        r"安全风险",
        r"安全[管评]",
    ]),
    ("进度管理", [
        r"进度",
        r"工期",
        r"排[产程]",
        r"关键链",
    ]),
    ("需求管理", [
        r"需求",
    ]),
    ("流程优化", [
        r"流程",
        r"周期优化",
        r"并行工程",
    ]),
    ("绩效评价", [
        r"绩效",
        r"评价",
        r"评估(?!研究)",         # 评估，排除"评估研究"
        r"综合[评价]",
        r"考评",
        r"协同度评[价估]",
    ]),
    ("供应链物流", [
        r"供应链",
        r"物流",
        r"配送",
        r"库存",
        r"路径优化",
        r"冷链",
        r"选址",
        r"车辆路径",
    ]),
    ("成本管理", [
        r"成本",
        r"费用",
    ]),
    ("其他", []),  # fallback
]


def classify_by_filename(filename: str) -> Optional[str]:
    """从文件名中提取分类。"""
    # 去掉扩展名
    name = Path(filename).stem
    for category, patterns in CATEGORY_RULES:
        if not patterns:  # "其他" 是 fallback
            continue
        for pattern in patterns:
            if re.search(pattern, name):
                return category
    return None


def classify_by_content(filepath: Path) -> Optional[str]:
    """提取 PDF 前几页文本，匹配摘要中的关键词。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(filepath))
        # 只读前 3 页（摘要通常在开头）
        text = ""
        for page in reader.pages[:3]:
            text += (page.extract_text() or "") + "\n"
            if len(text) > 3000:
                break
    except Exception:
        return None

    # 搜索摘要段
    abstract_match = re.search(r"(?:摘要|Abstract).{0,200}?(.{50,1500}?)(?:\n\n|\n关键词|关键词|Keyword)", text, re.DOTALL)
    search_text = abstract_match.group(1) if abstract_match else text[:2000]

    for category, patterns in CATEGORY_RULES:
        if not patterns:
            continue
        for pattern in patterns:
            if re.search(pattern, search_text):
                return category
    return None


def main():
    pdfs = sorted(ROOT.glob("*.pdf"))
    if not pdfs:
        print("根目录没有 PDF 文件")
        return

    results: dict[str, int] = {}
    for pdf in pdfs:
        cat = classify_by_filename(pdf.name)
        method = "标题"
        if cat is None:
            cat = classify_by_content(pdf)
            method = "摘要"
        if cat is None:
            cat = "其他"
            method = "fallback"

        dest_dir = ROOT / cat
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / pdf.name

        # 避免自己移动到自己
        if pdf.resolve() == dest.resolve():
            continue

        shutil.move(str(pdf), str(dest))
        results[cat] = results.get(cat, 0) + 1
        print(f"  [{method:>6}] {cat} ← {pdf.name}")

    print(f"\n分类完成：{sum(results.values())} 个文件")
    for cat, count in sorted(results.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
