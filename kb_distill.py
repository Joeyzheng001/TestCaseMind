#!/usr/bin/env python3
"""
kb_distill.py - 知识提炼工具

从已跑完的 PRD 测试点中提炼通用知识，写入知识库。
大模型判断哪些规则是跨PRD通用的，过滤掉业务特定规则。

用法:
    python kb_distill.py output/xxx/testpoints.json
    python kb_distill.py output/xxx/testpoints.json --req knowledge_base/需求文档.md
    python kb_distill.py output/xxx/testpoints.json --dry-run  # 只看不写
"""

import json
import os
import sys
import time
from pathlib import Path

WORKDIR = Path(__file__).parent
KB_DIR  = WORKDIR / "knowledge_base"
DISTILL_FILE = KB_DIR / "通用规则积累.md"

sys.path.insert(0, str(WORKDIR))
from dotenv import load_dotenv
load_dotenv(WORKDIR / ".env", override=True)

try:
    import anthropic
except ImportError:
    print("错误: pip install anthropic")
    sys.exit(1)

client = anthropic.Anthropic()
MODEL  = os.environ.get("MODEL_ID", "claude-sonnet-4-6")


def load_testpoints(tp_file: Path) -> list:
    data = json.loads(tp_file.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("testpoints", [])


def distill(testpoints: list, req_text: str = "", dry_run: bool = False) -> list:
    """
    调大模型提炼通用知识点。
    返回 [{"rule": str, "category": str, "confidence": str}]
    """
    # 只取 KB 和 RISK 来源的测试点（REQ 来源通常是业务特定的）
    kb_risk_tps = [tp for tp in testpoints
                   if tp.get("source") in ("KB", "RISK")]

    if not kb_risk_tps:
        print("  没有 KB/RISK 来源测试点，无可提炼内容")
        return []

    tp_summary = "\n".join(
        f"- [{tp.get('source')}][{tp.get('priority')}] "
        f"{tp.get('test_scenario') or tp.get('title', '')} "
        f"（来源: {tp.get('source_ref', '')}）"
        for tp in kb_risk_tps[:30]
    )

    prompt = f"""以下是从一份PRD生成的测试点列表（KB和RISK来源）：

{tp_summary}

{f'PRD内容节选：{req_text[:1500]}' if req_text else ''}

请判断哪些测试场景反映了**跨PRD通用的规则**，可以沉淀到知识库供后续PRD复用。

判断标准：
- ✅ 通用：枚举值边界、字段约束、降级处理逻辑、并发风险、精度处理、数据优先级切换
- ❌ 业务特定：某版本特有功能、某PRD特有的业务规则、与具体页面强绑定的规则

输出 JSON 数组：
[
  {{
    "rule": "具体规则描述（一句话，可直接用于测试）",
    "category": "枚举值|字段约束|降级逻辑|并发风险|精度处理|数据优先级|其他",
    "confidence": "高|中",
    "example": "示例：当XXX字段为空时，应返回默认值0而非报错"
  }}
]

只输出高置信度和中置信度的条目，低置信度的直接不输出。
只输出 JSON 数组，不要其他文字。"""

    resp = client.messages.create(
        model=MODEL,
        system="你是一名资深测试架构师，专门提炼跨项目通用的测试规则。只输出 JSON，不要其他文字。",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))

    # 解析 JSON
    import re
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
    start = text.find("[")
    if start >= 0:
        text = text[start:]
    try:
        rules = json.loads(text)
        return rules if isinstance(rules, list) else []
    except Exception:
        print(f"  [warn] JSON 解析失败，原始输出: {text[:200]}")
        return []


def write_to_kb(rules: list, source_name: str) -> int:
    """把提炼的规则追加到知识库文件，返回写入条数。"""
    if not rules:
        return 0

    KB_DIR.mkdir(exist_ok=True)

    # 读取已有内容，避免重复
    existing = set()
    if DISTILL_FILE.exists():
        existing_text = DISTILL_FILE.read_text(encoding="utf-8")
        # 简单去重：检查规则前60字符
        for line in existing_text.splitlines():
            if line.startswith("- "):
                existing.add(line[2:60])

    lines = []
    if not DISTILL_FILE.exists():
        lines.append("# 通用规则积累\n")
        lines.append("本文件由 kb_distill.py 自动维护，记录跨PRD通用的测试规则。\n")
        lines.append("每条规则都经过大模型判断，具有通用性和稳定性。\n\n")

    ts = time.strftime("%Y-%m-%d")
    lines.append(f"\n## {source_name}（{ts}提炼）\n")

    written = 0
    for rule in rules:
        r = rule.get("rule", "").strip()
        if not r:
            continue
        key = r[:60]
        if key in existing:
            continue  # 跳过重复
        cat  = rule.get("category", "其他")
        conf = rule.get("confidence", "中")
        ex   = rule.get("example", "")
        lines.append(f"- **[{cat}][{conf}]** {r}")
        if ex:
            lines.append(f"  - 示例：{ex}")
        existing.add(key)
        written += 1

    if written > 0:
        with open(DISTILL_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return written


def main():
    import argparse
    parser = argparse.ArgumentParser(description="从测试点提炼通用知识写入知识库")
    parser.add_argument("testpoints", help="测试点 JSON 文件路径")
    parser.add_argument("--req",      help="对应的需求文档路径（可选，提高判断准确性）")
    parser.add_argument("--dry-run",  action="store_true", help="只展示不写入知识库")
    args = parser.parse_args()

    tp_path = Path(args.testpoints).expanduser()
    if not tp_path.exists():
        print(f"错误: 找不到文件 {tp_path}")
        sys.exit(1)

    req_text = ""
    if args.req:
        req_path = Path(args.req).expanduser()
        if req_path.exists():
            # 支持 docx 自动转换
            if req_path.suffix.lower() in (".docx", ".doc"):
                try:
                    from docx import Document
                    doc = Document(str(req_path))
                    req_text = "\n".join(
                        p.text for p in doc.paragraphs if p.text.strip()
                    )[:2000]
                except Exception:
                    import subprocess
                    r = subprocess.run(
                        ["python3", str(WORKDIR / "docx2md.py"), str(req_path)],
                        capture_output=True, text=True
                    )
                    md_path = req_path.with_suffix(".md")
                    if md_path.exists():
                        req_text = md_path.read_text(encoding="utf-8")[:2000]
            else:
                req_text = req_path.read_text(encoding="utf-8")[:2000]

    print(f"\n📚 知识提炼")
    print(f"  输入: {tp_path.name}")

    testpoints = load_testpoints(tp_path)
    kb_count   = sum(1 for tp in testpoints if tp.get("source") == "KB")
    risk_count = sum(1 for tp in testpoints if tp.get("source") == "RISK")
    print(f"  测试点: {len(testpoints)} 条（KB={kb_count}, RISK={risk_count}）")

    print(f"  调用大模型判断通用性...")
    rules = distill(testpoints, req_text, dry_run=args.dry_run)

    if not rules:
        print("  未提炼到通用规则")
        return

    print(f"\n  提炼到 {len(rules)} 条通用规则:")
    for r in rules:
        conf = r.get("confidence", "中")
        cat  = r.get("category", "其他")
        rule = r.get("rule", "")
        mark = "✅" if conf == "高" else "🟡"
        print(f"  {mark} [{cat}] {rule}")

    if args.dry_run:
        print(f"\n  [dry-run] 未写入知识库")
        return

    confirm = input(f"\n  写入知识库？(Y/n): ").strip().lower()
    if confirm == "n":
        print("  已取消")
        return

    source_name = tp_path.parent.parent.name  # output/<需求名>/<ts>/testpoints.json → 需求名
    written = write_to_kb(rules, source_name)
    print(f"\n  ✓ 写入 {written} 条到 knowledge_base/通用规则积累.md")
    print(f"  建议运行: python kb_rag.py --rebuild 更新向量索引")


if __name__ == "__main__":
    main()
