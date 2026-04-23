#!/usr/bin/env python3
"""
regen_md.py - 从已有测试点 JSON 重新生成 XMind Markdown 文件

用法:
    python regen_md.py output/testpoints_xxx.json
    python regen_md.py output/testpoints_xxx.json --out output/重新生成.md

不需要重跑整个 Agent，适合调试 MD 格式问题。
"""

import json
import sys
from pathlib import Path

# 让 Python 能找到 agent 模块
sys.path.insert(0, str(Path(__file__).parent))

import argparse
from agent import normalize_testpoint, export_markdown_xmind


def main():
    parser = argparse.ArgumentParser(description="从测试点 JSON 重新生成 XMind Markdown")
    parser.add_argument("json_file", help="测试点 JSON 文件路径")
    parser.add_argument("--out", help="输出 MD 文件路径（默认同目录同名 .md）")
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"错误: 找不到文件 {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    testpoints = data.get("testpoints", [])
    review     = data.get("review", {})
    req_name   = Path(data.get("meta", {}).get("requirement", "unknown")).name

    if not testpoints:
        print("错误: 测试点列表为空")
        sys.exit(1)

    # 标准化字段
    normalized = [normalize_testpoint(tp, i) for i, tp in enumerate(testpoints)]

    # 统计
    req_c  = sum(1 for t in normalized if t.get("source") == "REQ")
    kb_c   = sum(1 for t in normalized if t.get("source") == "KB")
    risk_c = sum(1 for t in normalized if t.get("source") == "RISK")

    print(f"需求文档: {req_name}")
    print(f"测试点总数: {len(normalized)}  REQ={req_c}  KB={kb_c}  RISK={risk_c}")
    print(f"评审分: {review.get('score', 'N/A')}")

    # 输出路径
    out_path = Path(args.out) if args.out else json_path.with_suffix(".md")

    ok = export_markdown_xmind(normalized, review, req_name, out_path)
    if ok:
        print(f"\n✓ 生成成功: {out_path}")
        print(f"  XMind 导入: 文件 → 导入 → Markdown")
    else:
        print(f"\n✗ 生成失败")


if __name__ == "__main__":
    main()
