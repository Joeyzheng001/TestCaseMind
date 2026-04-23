#!/usr/bin/env python3
"""
gen_report.py - 测分文档生成

基于前三个阶段的输出数据，生成标准测分文档（Markdown 格式）。
完全本地生成，不调用任何 API，零 token 消耗。

用法:
    python gen_report.py output/testpoints_xxx.json
    python gen_report.py output/testpoints_xxx.json --cases output/testcases_xxx.json
    python gen_report.py output/testpoints_xxx.json --cases output/testcases_xxx.json --out output/report.md
"""

import argparse
import json
import sys
import time
from pathlib import Path


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def format_risk_type(t: str) -> str:
    mapping = {
        "security": "🔒 安全",
        "performance": "⚡ 性能",
        "integration": "🔗 集成",
        "data_quality": "📊 数据质量",
        "concurrency": "🔄 并发",
    }
    return mapping.get(t, f"⚠ {t}")


def generate_report(tp_data: dict, cases: list, out_path: Path) -> str:
    """生成测分文档，返回 Markdown 字符串。"""

    meta = tp_data.get("meta", {})
    review = tp_data.get("review", {})
    testpoints = tp_data.get("testpoints", [])

    req_name = Path(meta.get("requirement", "未知需求")).name
    gen_time = meta.get("generated_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    total_tp = meta.get("total", len(testpoints))
    by_source = meta.get("by_source", {})
    req_c = by_source.get("REQ", 0)
    kb_c = by_source.get("KB", 0)
    risk_c = by_source.get("RISK", 0)

    review_score = review.get("score", "N/A")
    review_summary = review.get("summary", "")
    risk_flags = review.get("risk_flags", [])
    testable = review.get("testable_features", [])
    complete_issues = review.get("completeness_issues", [])
    consist_issues = review.get("consistency_issues", [])
    untestable = review.get("untestable_items", [])

    # 用例统计
    p0_c = sum(1 for t in testpoints if t.get("priority") == "P0")
    p1_c = sum(1 for t in testpoints if t.get("priority") == "P1")
    p2_c = sum(1 for t in testpoints if t.get("priority") == "P2")

    tc_total = len(cases)
    tc_p0 = sum(1 for c in cases if c.get("priority") == "P0")
    tc_p1 = sum(1 for c in cases if c.get("priority") == "P1")
    tc_p2 = sum(1 for c in cases if c.get("priority") == "P2")

    # 按功能模块统计测试点
    modules: dict = {}
    for tp in testpoints:
        mod = tp.get("functional_module") or tp.get("feature") or "未分类"
        modules.setdefault(mod, {"REQ": 0, "KB": 0, "RISK": 0, "total": 0})
        src = tp.get("source", "REQ")
        if src in ("REQ", "KB", "RISK"):
            modules[mod][src] += 1
        modules[mod]["total"] += 1

    # 质量评级
    if isinstance(review_score, int):
        if review_score >= 85:
            quality_level = "🟢 优"
        elif review_score >= 70:
            quality_level = "🟡 良"
        elif review_score >= 60:
            quality_level = "🟠 中"
        else:
            quality_level = "🔴 差"
    else:
        quality_level = "⚪ 未评"

    # 测试覆盖评级
    if total_tp >= 30 and kb_c > 0 and risk_c >= 3:
        coverage_level = "🟢 完整"
    elif total_tp >= 15:
        coverage_level = "🟡 基本完整"
    else:
        coverage_level = "🔴 不足"

    lines = []

    # ── 封面 ────────────────────────────────────────────────────────────────
    lines += [
        f"# 测试分析报告",
        "",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| 需求文档 | {req_name} |",
        f"| 生成时间 | {gen_time} |",
        f"| 需求质量 | {quality_level}（{review_score}/100）|",
        f"| 测试覆盖 | {coverage_level} |",
        "",
        "---",
        "",
    ]

    # ── 一、测试概述 ─────────────────────────────────────────────────────────
    lines += [
        "## 一、测试概述",
        "",
    ]
    if review_summary:
        lines += [f"> {review_summary}", ""]

    lines += [
        f"本次测试基于需求文档 **{req_name}** 进行，",
        f"共生成 **{total_tp}** 个测试点、**{tc_total}** 条测试用例。",
        "",
    ]

    # ── 二、测试范围 ─────────────────────────────────────────────────────────
    lines += [
        "## 二、测试范围",
        "",
        "### 2.1 覆盖功能点",
        "",
    ]
    if testable:
        for f in testable:
            lines.append(f"- {f}")
    else:
        lines.append("_（评审未提取到明确功能点）_")
    lines.append("")

    lines += ["### 2.2 功能模块分布", ""]
    if modules:
        lines += [
            "| 功能模块 | 测试点数 | REQ | KB | RISK |",
            "|----------|---------|-----|----|------|",
        ]
        for mod, counts in sorted(modules.items(), key=lambda x: -x[1]["total"]):
            lines.append(
                f"| {mod} | {counts['total']} | "
                f"{counts['REQ']} | {counts['KB']} | {counts['RISK']} |"
            )
    lines.append("")

    # ── 三、测试结果统计 ──────────────────────────────────────────────────────
    lines += [
        "## 三、测试点统计",
        "",
        "### 3.1 测试点来源分布",
        "",
        "| 来源类型 | 数量 | 占比 | 说明 |",
        "|---------|------|------|------|",
    ]
    if total_tp > 0:
        lines += [
            f"| 🔵 REQ 需求直出 | {req_c} | {req_c / total_tp * 100:.1f}% | 来自需求文档原文 |",
            f"| 🟡 KB 知识库补充 | {kb_c} | {kb_c / total_tp * 100:.1f}% | 来自数据字典/表设计/行业规范 |",
            f"| 🔴 RISK 风险推断 | {risk_c} | {risk_c / total_tp * 100:.1f}% | 基于测试经验的风险覆盖 |",
            f"| **合计** | **{total_tp}** | **100%** | |",
        ]
    lines.append("")

    lines += [
        "### 3.2 测试点优先级分布",
        "",
        "| 优先级 | 测试点数 | 说明 |",
        "|--------|---------|------|",
        f"| P0 核心必测 | {p0_c} | 上线前必须全部通过 |",
        f"| P1 重要应测 | {p1_c} | 正式测试需覆盖 |",
        f"| P2 边缘可测 | {p2_c} | 时间充裕时覆盖 |",
        f"| **合计** | **{total_tp}** | |",
        "",
    ]

    if tc_total > 0:
        lines += [
            "### 3.3 测试用例统计",
            "",
            "| 优先级 | 用例数 | 说明 |",
            "|--------|--------|------|",
            f"| P0 | {tc_p0} | |",
            f"| P1 | {tc_p1} | |",
            f"| P2 | {tc_p2} | |",
            f"| **合计** | **{tc_total}** | |",
            "",
        ]

    # ── 四、风险与问题 ────────────────────────────────────────────────────────
    lines += ["## 四、风险与问题", ""]

    if risk_flags:
        lines += ["### 4.1 需求评审识别风险", ""]
        for r in risk_flags:
            rtype = format_risk_type(r.get("type", "unknown"))
            desc = r.get("desc", "")
            lines.append(f"- **{rtype}**：{desc}")
        lines.append("")

    if complete_issues or consist_issues or untestable:
        lines += ["### 4.2 需求质量问题", ""]
        if complete_issues:
            lines.append("**完整性问题：**")
            for i in complete_issues:
                lines.append(f"- {i}")
            lines.append("")
        if consist_issues:
            lines.append("**一致性问题：**")
            for i in consist_issues:
                lines.append(f"- {i}")
            lines.append("")
        if untestable:
            lines.append("**不可测项（需求描述模糊，无法设计验证用例）：**")
            for i in untestable:
                lines.append(f"- {i}")
            lines.append("")

    risk_tps = [tp for tp in testpoints if tp.get("source") == "RISK"]
    if risk_tps:
        lines += ["### 4.3 测试风险点（RISK 来源测试点）", ""]
        for tp in risk_tps:
            scenario = tp.get("test_scenario") or tp.get("title", "")
            pri = tp.get("priority", "P2")
            module = tp.get("functional_module", "")
            lines.append(f"- **[{pri}][{module}]** {scenario}")
        lines.append("")

    if not risk_flags and not complete_issues and not risk_tps:
        lines += ["_（本次测试未发现明显风险项）_", ""]

    # ── 五、测试结论 ─────────────────────────────────────────────────────────
    lines += ["## 五、测试结论", ""]

    # 自动生成结论
    conclusions = []
    if isinstance(review_score, int) and review_score < 60:
        conclusions.append(
            f"⚠ 需求文档质量较低（{review_score}/100），存在较多模糊描述，"
            "建议在正式测试前与需求方确认不可测项。"
        )
    if kb_c == 0:
        conclusions.append(
            "⚠ 本次未生成知识库来源测试点，建议补充数据字典和表设计文档，"
            "以覆盖枚举值边界和字段约束测试。"
        )
    if risk_c < 3:
        conclusions.append(
            "⚠ 风险推断测试点较少，建议重点关注并发场景、数据精度和外部依赖失败等场景。"
        )
    if p0_c > 0:
        conclusions.append(f"✅ 共 {p0_c} 条 P0 核心测试点，上线前必须全部通过。")
    if tc_total > 0:
        conclusions.append(
            f"✅ 共生成 {tc_total} 条测试用例，可直接导入测试管理工具执行。"
        )

    for c in conclusions:
        lines.append(f"- {c}")
    lines.append("")

    lines += [
        "---",
        "",
        f"*本报告由测试 Agent v2 自动生成  ·  {gen_time}*",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="生成测分文档（零 token 消耗）")
    parser.add_argument("testpoints", help="测试点 JSON 文件路径")
    parser.add_argument("--cases", help="测试用例 JSON 文件路径（可选）")
    parser.add_argument("--out", help="输出 md 文件路径（默认同目录）")
    args = parser.parse_args()

    tp_path = Path(args.testpoints).expanduser()
    if not tp_path.exists():
        print(f"错误: 找不到文件 {tp_path}")
        sys.exit(1)

    tp_data = load_json(tp_path)
    if isinstance(tp_data, list):
        tp_data = {"testpoints": tp_data, "meta": {}, "review": {}}

    cases = []
    if args.cases:
        tc_path = Path(args.cases).expanduser()
        if tc_path.exists():
            raw = load_json(tc_path)
            cases = raw if isinstance(raw, list) else raw.get("testcases", [])

    out_path = (
        Path(args.out).expanduser()
        if args.out
        else tp_path.with_name(tp_path.stem.replace("testpoints", "report") + ".md")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"生成测分文档...")
    md = generate_report(tp_data, cases, out_path)
    out_path.write_text(md, encoding="utf-8")

    tp_total = tp_data.get("meta", {}).get("total", len(tp_data.get("testpoints", [])))
    print(f"✓ 测试点: {tp_total} 条  用例: {len(cases)} 条")
    print(f"✓ 输出: {out_path}")


if __name__ == "__main__":
    main()
