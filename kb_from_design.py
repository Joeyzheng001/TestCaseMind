#!/usr/bin/env python3
"""
kb_from_design.py - 从因子开发设计文档提取知识库

把因子设计 Excel 里的计算公式、参数值域、元因子取值逻辑
转换为结构化 md 文件，供 test-agent 生成测试点时检索。

用法:
    python kb_from_design.py 因子设计文档.xlsx
    python kb_from_design.py 因子设计文档.xlsx --out-dir knowledge_base/design

输出（每个因子一个文件）:
    knowledge_base/design/00_因子索引.md      ← Agent 先读这个
    knowledge_base/design/衍生品持仓数量.md
    knowledge_base/design/组合久期-全资产.md
    ...
"""

import re
import sys
from pathlib import Path

KB_DIR = Path(__file__).parent / "knowledge_base" / "design"

# 不需要提取的 sheet（模板页）
SKIP_SHEETS = {"因子开发设计文档模板"}


def extract_raw(xlsx_path: Path) -> str:
    """读取 xlsx，兼容样式有问题的文件。"""
    import pandas as pd

    # 依次尝试不同引擎
    engines = ["calamine", "xlrd", "openpyxl"]
    xl = None
    for engine in engines:
        try:
            xl = pd.ExcelFile(xlsx_path, engine=engine)
            break
        except Exception:
            continue

    if xl is None:
        # 最后降级：用 zipfile 直接读 xl/sharedStrings.xml 提取文本
        return _extract_raw_zip(xlsx_path)

    parts = []
    for sheet_name in xl.sheet_names:
        try:
            df = xl.parse(sheet_name, header=None, dtype=str).fillna("")
            parts.append(f"## Sheet: {sheet_name}")
            for _, row in df.iterrows():
                line = "\t".join(str(v) for v in row.values)
                if line.strip().replace("\t", ""):
                    parts.append(line)
        except Exception:
            continue
    return "\n".join(parts)


def _extract_raw_zip(xlsx_path: Path) -> str:
    """直接解析 xlsx zip 结构，提取共享字符串和 sheet 数据。"""
    import zipfile
    import xml.etree.ElementTree as ET

    ns = {
        "ss": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r":  "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }

    parts = []
    with zipfile.ZipFile(xlsx_path) as zf:
        names = zf.namelist()

        # 读共享字符串
        shared_strings = []
        if "xl/sharedStrings.xml" in names:
            tree = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in tree.findall(".//ss:si", ns):
                text = "".join(t.text or "" for t in si.iter() if t.text)
                shared_strings.append(text)

        # 读 workbook 获取 sheet 名称
        sheet_names = {}
        if "xl/workbook.xml" in names:
            wb_tree = ET.fromstring(zf.read("xl/workbook.xml"))
            for sheet in wb_tree.findall(".//ss:sheet", ns):
                rid  = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                sname = sheet.get("name", "")
                sheet_names[rid] = sname

        # 读 relationships 获取 sheet 文件路径
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            rel_tree = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            for rel in rel_tree.findall("*"):
                rid    = rel.get("Id", "")
                target = rel.get("Target", "")
                rels[rid] = target

        # 读每个 sheet
        for rid, sname in sheet_names.items():
            target = rels.get(rid, "")
            if not target:
                continue
            sheet_path = f"xl/{target}" if not target.startswith("xl/") else target
            if sheet_path not in names:
                continue

            parts.append(f"## Sheet: {sname}")
            sheet_tree = ET.fromstring(zf.read(sheet_path))
            for row in sheet_tree.findall(".//ss:row", ns):
                cells = []
                for c in row.findall("ss:c", ns):
                    t   = c.get("t", "")
                    val = ""
                    v   = c.find("ss:v", ns)
                    if v is not None and v.text:
                        if t == "s":
                            idx = int(v.text)
                            val = shared_strings[idx] if idx < len(shared_strings) else ""
                        elif t == "inlineStr":
                            is_elem = c.find(".//ss:t", ns)
                            val = is_elem.text if is_elem is not None else ""
                        else:
                            val = v.text
                    cells.append(val)
                line = "\t".join(cells)
                if line.strip().replace("\t", ""):
                    parts.append(line)

    return "\n".join(parts)


def split_sheets(raw: str) -> dict:
    """按 '## Sheet: xxx' 分割成各个 sheet 的内容。"""
    sheets = {}
    current_name = None
    current_lines = []

    for line in raw.splitlines():
        if line.startswith("## Sheet: "):
            if current_name and current_lines:
                sheets[current_name] = "\n".join(current_lines)
            current_name = line.replace("## Sheet: ", "").strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)

    if current_name and current_lines:
        sheets[current_name] = "\n".join(current_lines)

    return sheets


def parse_factor_sheet(name: str, content: str) -> dict:
    """
    解析单个因子 sheet，提取：
    - formula: 计算公式
    - filter_logic: 筛选逻辑
    - parameters: [{name, type, values, logic}]
    - meta_factors: [{name, is_extended, table, field, logic}]
    - raw: 原始文本（备用）
    """
    result = {
        "name":         name,
        "formula":      "",
        "filter_logic": "",
        "parameters":   [],
        "meta_factors": [],
        "raw":          content,
    }

    lines = content.splitlines()

    # 提取计算公式（通常在开头几行，含 = 号且较长）
    for line in lines[:5]:
        line = line.strip()
        if "=" in line and len(line) > 10 and not line.startswith("\t"):
            result["formula"] = line
            break

    # 提取筛选逻辑（含 "筛选逻辑" 关键词的行）
    for i, line in enumerate(lines):
        if "筛选逻辑" in line:
            # 取该行及后续非空行
            filter_parts = []
            for fl in lines[i:i+5]:
                fl = fl.strip()
                if fl and fl != "筛选逻辑":
                    filter_parts.append(fl)
            result["filter_logic"] = " ".join(filter_parts[:2])
            break

    # 提取参数行和元因子行
    params = []
    meta_factors = []
    in_param_section = False
    in_meta_section  = False

    for line in lines:
        cols = [c.strip() for c in line.split("\t")]
        if not any(c for c in cols if c):
            continue

        # 检测进入参数区域：类型列含"参数"关键词
        if any("条件参数" in c or "计算参数" in c for c in cols):
            in_param_section = True
            in_meta_section  = False

        # 检测进入元因子区域：含"元因子"和"是否为扩展因子"
        all_text = "\t".join(cols)
        if "元因子" in all_text and "是否为扩展因子" in all_text:
            in_param_section = False
            in_meta_section  = True
            continue

        # 解析参数行
        if in_param_section:
            # 找出非空列
            non_empty = [(i, c) for i, c in enumerate(cols) if c]
            if len(non_empty) >= 2:
                # 参数名通常在第2列（index 1），类型在第3列（index 2）
                # 但有些行第1列有值（行首无 tab）
                param_name = None
                param_type = None
                param_vals = ""
                param_logic = ""
                for i, (idx, val) in enumerate(non_empty):
                    if i == 0 and idx > 0:  # 行首有 tab，第一个非空列是参数名
                        param_name = val
                    elif i == 0 and idx == 0:  # 行首无 tab，跳过（不是参数行）
                        break
                    elif param_name and ("参数" in val or i == 1):
                        param_type = val
                    elif param_name and param_type and not param_vals:
                        param_vals = val
                    elif param_name and param_type and param_vals and not param_logic:
                        param_logic = val

                if param_name and param_type and "参数" in param_type:
                    params.append({
                        "name":   param_name,
                        "type":   param_type,
                        "values": param_vals,
                        "logic":  param_logic[:200],
                    })

        # 解析元因子行
        if in_meta_section:
            non_empty = [(i, c) for i, c in enumerate(cols) if c]
            if len(non_empty) >= 2:
                # 元因子名通常在第2列（行首有 tab）
                if non_empty[0][0] > 0:  # 行首有 tab
                    mf_name = non_empty[0][1]
                    if mf_name in ("元因子", "涉及元因子", "类汇总元因子概念"):
                        continue
                    # 后续列：is_extended, table, field, logic
                    vals = [v for _, v in non_empty[1:]]
                    meta_factors.append({
                        "name":        mf_name,
                        "is_extended": vals[0] if len(vals) > 0 else "",
                        "table":       vals[1] if len(vals) > 1 else "",
                        "field":       vals[2] if len(vals) > 2 else "",
                        "logic":       vals[3][:300] if len(vals) > 3 else "",
                    })

    result["parameters"]   = params
    result["meta_factors"] = meta_factors
    return result


def factor_to_md(factor: dict) -> str:
    """把解析后的因子数据转成 Markdown。"""
    name = factor["name"]
    lines = [
        f"# 因子开发设计：{name}",
        "",
        "## 测试说明",
        "本文档来自开发设计文档，包含比需求文档更详细的实现细节。",
        "生成测试点时，以下信息应作为 KB 来源的测试点依据。",
        "",
    ]

    # 计算公式
    if factor["formula"]:
        lines += [
            "## 计算公式",
            "",
            f"```",
            factor["formula"],
            f"```",
            "",
            "**测试重点**：",
            "- 用具体数值验证公式计算结果",
            "- 验证公式中每个变量的取值来源",
            "",
        ]

    # 筛选逻辑
    if factor["filter_logic"]:
        lines += [
            "## 筛选逻辑",
            "",
            factor["filter_logic"],
            "",
            "**测试重点**：",
            "- 满足筛选条件的数据应被纳入计算",
            "- 不满足筛选条件的数据应被排除",
            "",
        ]

    # 参数
    if factor["parameters"]:
        lines += [
            "## 参数列表（每个枚举值都应独立测试）",
            "",
            "| 参数名 | 类型 | 值域 | 说明 |",
            "|--------|------|------|------|",
        ]
        for p in factor["parameters"]:
            vals = p["values"].replace("\n", " ")[:80]
            logic = p["logic"].replace("\n", " ")[:60] if p["logic"] else "-"
            lines.append(f"| {p['name']} | {p['type']} | {vals} | {logic} |")

        lines += [
            "",
            "**测试规则**：",
            "- 条件参数：每个枚举值单独生成一条测试点",
            "- 计算参数：验证不同参数值对计算结果的影响",
            "- 非法参数值（超出值域）：应返回错误或使用默认值",
            "",
        ]

    # 元因子
    if factor["meta_factors"]:
        lines += [
            "## 元因子取值逻辑（数据源验证依据）",
            "",
            "| 元因子 | 是否扩展 | 数据表 | 字段 | 取值逻辑 |",
            "|--------|----------|--------|------|---------|",
        ]
        for mf in factor["meta_factors"]:
            table = mf["table"].replace("\n", " ")[:40] if mf["table"] else "-"
            field = mf["field"].replace("\n", " ")[:20] if mf["field"] else "-"
            logic = mf["logic"].replace("\n", " ")[:60] if mf["logic"] else "-"
            lines.append(
                f"| {mf['name']} | {mf['is_extended'] or '-'} | "
                f"{table} | {field} | {logic} |"
            )

        lines += [
            "",
            "**测试规则**：",
            "- 验证每个元因子从正确的表/字段取值",
            "- 验证扩展因子（是否为扩展因子=是）的加工逻辑",
            "- 验证主表无数据时是否有降级处理",
            "",
        ]

    # 原始内容（截断，备用）
    raw_preview = factor["raw"][:500].replace("\t", "  ")
    lines += [
        "## 原始设计文本（节选）",
        "",
        "```",
        raw_preview,
        "...",
        "```",
    ]

    return "\n".join(lines)


def build_index(factors: list, out_dir: Path) -> str:
    """生成索引文件。"""
    lines = [
        "# 因子开发设计文档索引",
        "",
        "根据需求涉及的因子，用 read_file 读取对应文件。",
        "设计文档比需求文档包含更详细的实现逻辑，应作为 KB 来源测试点的主要依据。",
        "",
        "| 文件名 | 因子名称 | 参数数 | 元因子数 | 计算公式预览 |",
        "|--------|----------|--------|---------|-------------|",
    ]
    for f in factors:
        fname  = f"{f['name']}.md"
        nparam = len(f["parameters"])
        nmeta  = len(f["meta_factors"])
        formula_preview = f["formula"][:40] + "..." if len(f.get("formula","")) > 40 else f.get("formula","")
        lines.append(f"| {fname} | {f['name']} | {nparam} | {nmeta} | {formula_preview} |")

    lines += [
        "",
        "## 使用方式",
        "",
        "1. 先读此索引，找到需求文档对应的因子名称",
        "2. 用 read_file 读取对应因子的设计文档",
        "3. 根据参数值域生成 KB 来源的枚举测试点",
        "4. 根据元因子取值逻辑生成数据源验证测试点",
    ]
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="从因子设计文档提取知识库")
    parser.add_argument("xlsx", help="因子设计文档 xlsx 路径")
    parser.add_argument("--out-dir", help=f"输出目录（默认 {KB_DIR}）")
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    if not xlsx_path.exists():
        print(f"错误: 找不到文件 {xlsx_path}")
        sys.exit(1)

    out_dir = Path(args.out_dir) if args.out_dir else KB_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"读取: {xlsx_path.name}")
    raw = extract_raw(xlsx_path)

    print("解析 sheet...")
    sheets = split_sheets(raw)
    print(f"共 {len(sheets)} 个 sheet")

    factors = []
    for sheet_name, content in sheets.items():
        if sheet_name in SKIP_SHEETS:
            continue
        if not content.strip():
            continue
        factor = parse_factor_sheet(sheet_name, content)
        factors.append(factor)

    print(f"\n开始生成知识库文件...\n")

    ok_count = 0
    for factor in factors:
        fname   = out_dir / f"{factor['name']}.md"
        md_text = factor_to_md(factor)
        fname.write_text(md_text, encoding="utf-8")
        size_kb = fname.stat().st_size // 1024
        print(f"  ✓  {factor['name']}.md  "
              f"（{len(factor['parameters'])}个参数, "
              f"{len(factor['meta_factors'])}个元因子, "
              f"{size_kb}KB）")
        ok_count += 1

    # 写索引
    idx_path = out_dir / "00_因子索引.md"
    idx_path.write_text(build_index(factors, out_dir), encoding="utf-8")
    print(f"\n  ✓  00_因子索引.md")

    print(f"\n{'─'*50}")
    print(f"完成: {ok_count} 个因子文件 + 1 个索引")
    print(f"输出目录: {out_dir}")
    print(f"\n下一步:")
    print(f"  python agent.py <需求文档> --kb --design knowledge_base/design/")


if __name__ == "__main__":
    main()
