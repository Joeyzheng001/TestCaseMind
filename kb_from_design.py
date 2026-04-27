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

    两阶段策略：
      阶段1 — 列解析（tab 分隔的表格格式）
      阶段2 — 文本兜底（从注释和代码中提取）
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

    # ═══════════════════════════════════════════════════════════════════════
    # 阶段1：列解析（适用于标准 tab 分隔格式）
    # ═══════════════════════════════════════════════════════════════════════

    # ── 公式提取（放宽条件）────────────────────────────────────────────
    for line in lines[:30]:
        line_s = line.strip()
        if not line_s or len(line_s) < 8:
            continue
        # 匹配计算公式特征：含 = 或汇总计算/计算公式关键词 或 DSL 关键字
        is_formula = (
            ("=" in line_s and len(line_s) > 10) or
            "汇总计算公式" in line_s or
            "计算公式" in line_s or
            line_s.startswith("SUM(") or
            line_s.startswith("FOR(") or
            line_s.startswith("switch(") or
            "Map<" in line_s
        )
        if is_formula:
            # 收集连续相关行（DSL 可能跨行）
            idx = lines.index(line) if line in lines else 0
            formula_lines = [line_s]
            for next_line in lines[idx + 1:idx + 8]:
                ns = next_line.strip()
                if ns and (ns.startswith("//") or "MF#" in ns or
                           "concat" in ns or "firstNotZero" in ns or
                           ns.startswith("SUM(") or ns.startswith("FOR(") or
                           ns.startswith(")") or "switch(" in ns or
                           ("=" in ns and len(ns) > 10)):
                    formula_lines.append(ns)
                elif ns == "" or ns.startswith("}"):
                    continue
                else:
                    break
            result["formula"] = "\n".join(formula_lines[:8])
            break

    # ── 筛选逻辑提取 ────────────────────────────────────────────────────
    _FILTER_TEMPLATE_KW = {"要实现的汇总因子", "参数", "类型", "值域", "加工逻辑"}
    for i, line in enumerate(lines):
        line_s = line.strip()
        if "筛选逻辑" in line_s:
            filter_parts = []
            for fl in lines[i+1:i+6]:
                fl = fl.strip()
                if not fl:
                    continue
                # 跳过模板列头行
                kw_hits = sum(1 for kw in _FILTER_TEMPLATE_KW if kw in fl)
                if kw_hits >= 2:
                    continue
                if fl != "筛选逻辑":
                    filter_parts.append(fl)
            if filter_parts:
                result["filter_logic"] = " ".join(filter_parts[:2])
            break

    # ── 参数提取（列解析）───────────────────────────────────────────────
    in_param_section = False
    in_meta_section  = False

    for line in lines:
        cols = [c.strip() for c in line.split("\t")]
        if not any(c for c in cols if c):
            continue

        # 检测进入参数区域
        if any("条件参数" in c or "计算参数" in c for c in cols):
            in_param_section = True
            in_meta_section  = False

        # 检测进入元因子区域
        all_text = "\t".join(cols)
        if "元因子" in all_text and "是否为扩展因子" in all_text:
            in_param_section = False
            in_meta_section  = True
            continue

        # 解析参数行
        if in_param_section:
            non_empty = [(i, c) for i, c in enumerate(cols) if c]
            if len(non_empty) >= 2:
                param_name = None
                param_type = None
                param_vals = ""
                param_logic = ""
                for j, (idx, val) in enumerate(non_empty):
                    if j == 0 and idx > 0:
                        param_name = val
                    elif j == 0 and idx == 0:
                        break
                    elif param_name and ("参数" in val or j == 1):
                        param_type = val
                    elif param_name and param_type and not param_vals:
                        param_vals = val
                    elif param_name and param_type and param_vals and not param_logic:
                        param_logic = val

                if param_name and param_type and "参数" in param_type:
                    result["parameters"].append({
                        "name":   param_name,
                        "type":   param_type,
                        "values": param_vals,
                        "logic":  param_logic[:200],
                    })

        # 解析元因子行
        if in_meta_section:
            non_empty = [(i, c) for i, c in enumerate(cols) if c]
            if len(non_empty) >= 2:
                if non_empty[0][0] > 0:
                    mf_name = non_empty[0][1]
                    if mf_name in ("元因子", "涉及元因子", "类汇总元因子概念"):
                        continue
                    vals = [v for _, v in non_empty[1:]]
                    result["meta_factors"].append({
                        "name":        mf_name,
                        "is_extended": vals[0] if len(vals) > 0 else "",
                        "table":       vals[1] if len(vals) > 1 else "",
                        "field":       vals[2] if len(vals) > 2 else "",
                        "logic":       vals[3][:300] if len(vals) > 3 else "",
                    })

    # ═══════════════════════════════════════════════════════════════════════
    # 阶段2：文本兜底（列解析无结果时兜底，有结果时补充）
    # ═══════════════════════════════════════════════════════════════════════
    if not result["parameters"]:
        _extract_params_from_text(content, result)
    if not result["meta_factors"]:
        _extract_metafactors_from_text(content, result)
    else:
        # 列解析已有结果时，文本兜底做补充（合并去重）
        supplement = {"meta_factors": []}
        _extract_metafactors_from_text(content, supplement)
        existing_names = {mf["name"] for mf in result["meta_factors"]}
        for mf in supplement.get("meta_factors", []):
            if mf["name"] not in existing_names:
                result["meta_factors"].append(mf)
                existing_names.add(mf["name"])
    if not result["filter_logic"]:
        _extract_filter_from_text(content, result)

    return result


def _extract_params_from_text(content: str, result: dict):
    """从原始文本中提取参数（兜底策略）。
    支持格式：
      //参数：参数名 值1->含义1 值2->含义2
      条件参数  参数名  值1/值2/值3
    """
    text = content.replace("\t", " ")

    # 模式1: //参数：xxx 或 参数：xxx
    param_matches = re.findall(
        r'(?:参数[：:])\s*(.+?)(?:\n|//|$)',
        text
    )
    for match in param_matches:
        # 解析 "头寸口径 1->计划日终 2->实时可用（O32）3->实时交易（金服）"
        # 先分离参数名和值
        parts = match.strip().split(None, 1)  # 第一个空格分割
        if len(parts) >= 2:
            param_name = parts[0]
            value_str = parts[1]
            # 提取枚举值: 数字->含义 或 值1/值2
            values = re.findall(r'(\d+->[^\s]*)|([^/\s]+/[^/\s]+(?:/[^/\s]+)*)', value_str)
            if values:
                flat_vals = [v[0] or v[1] for v in values]
                result["parameters"].append({
                    "name":   param_name,
                    "type":   "条件参数",
                    "values": ", ".join(flat_vals[:15]),
                    "logic":  value_str[:200],
                })
        elif parts:
            result["parameters"].append({
                "name":   parts[0],
                "type":   "条件参数",
                "values": "",
                "logic":  match.strip()[:200],
            })

    # 模式2: 行内条件参数/计算参数
    if not result["parameters"]:
        for line in text.splitlines():
            if "条件参数" in line or "计算参数" in line:
                # 尝试按空格/tab切分
                cols = line.strip().split()
                # 找 "条件参数" 或 "计算参数" 后的第一个词作为参数名
                for i, c in enumerate(cols):
                    if c in ("条件参数", "计算参数") and i + 1 < len(cols):
                        # 跳过值域/加工逻辑等描述列头
                        name = cols[i + 1]
                        if name in ("类型", "值域", "加工逻辑", "参数"):
                            continue
                        vals = cols[i + 2] if i + 2 < len(cols) and "/" in cols[i + 2] else ""
                        result["parameters"].append({
                            "name":   name,
                            "type":   c,
                            "values": vals,
                            "logic":  " ".join(cols[i + 2:i + 4])[:200] if i + 2 < len(cols) else "",
                        })
                        break
            if len(result["parameters"]) >= 20:
                break


def _extract_metafactors_from_text(content: str, result: dict, target_key: str = "meta_factors"):
    """从原始文本中提取元因子引用（兜底/补充策略）。
    匹配数据表引用：DWD_*, MG#, MF#, 取xxx表xxx字段 等

    Args:
        content:    原始文本
        result:     目标字典（会被修改）
        target_key: 写入的 key 名（默认 "meta_factors"）
    """
    text = content.replace("\t", " ")
    seen = set()

    # 匹配 "取xxx表xxx字段" 模式（最优先，最有价值）
    field_refs = re.findall(
        r'取(\S+?表)\s*(\S*?)字段',
        text
    )
    for table, field in field_refs[:15]:
        key = f"{table}.{field}"
        if key not in seen:
            seen.add(key)
            result[target_key].append({
                "name":        f"{table}.{field}" if field else table,
                "is_extended": "",
                "table":       table[:60],
                "field":       field[:40] if field else "",
                "logic":       f"从{table}取{field}字段" if field else f"从{table}取值",
            })

    # 匹配 MF#XXX 扩展因子引用
    mf_refs = re.findall(r'MF#(\w+)', text)
    for mf in mf_refs[:10]:
        if mf not in seen:
            seen.add(mf)
            result[target_key].append({
                "name":        f"MF#{mf}",
                "is_extended": "是",
                "table":       "",
                "field":       mf,
                "logic":       f"扩展因子 MF#{mf}",
            })

    # 匹配 DWD_* 和 MG#* 引用（去重后加入）
    table_refs = re.findall(r'(DWD_\w+|MG#\w+)', text)
    for match in table_refs[:15]:
        if match not in seen:
            seen.add(match)
            result[target_key].append({
                "name":        match,
                "is_extended": "",
                "table":       match if match.startswith("DWD_") else "",
                "field":       "",
                "logic":       "",
            })


def _extract_filter_from_text(content: str, result: dict):
    """从原始文本中提取筛选逻辑（兜底策略）。"""
    # 查找筛选逻辑后的非空非模板行
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "筛选逻辑" in line:
            for fl in lines[i + 1:i + 6]:
                fl = fl.strip().replace("\t", " ")
                if fl and "要实现的汇总因子" not in fl and "参数" not in fl:
                    result["filter_logic"] = fl[:200]
                    return


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
