#!/usr/bin/env python3
"""审核 234 个方法卡片的命名，让 LLM 给出最权威的叫法"""

import json, sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from llm_config import load_llm_config
import sqlite3

# ── Load all method cards ──────────────────────────────
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "knowledge_base", "cards.sqlite3"))
conn.row_factory = sqlite3.Row
cards = conn.execute("""
    SELECT id, name, aliases, category, phase, short_name
    FROM cards WHERE type='method_card' ORDER BY name
""").fetchall()
conn.close()

# Build input list
method_list = []
for c in cards:
    aliases = json.loads(c['aliases']) if c['aliases'] else []
    method_list.append({
        "id": c["id"],
        "current_name": c["name"],
        "aliases": aliases,
        "category": c["category"] or "",
        "phase": json.dumps(c["phase"]) if c["phase"] else "",
    })

print(f"共 {len(method_list)} 个方法卡片")

# ── Build prompt ───────────────────────────────────────
input_json = json.dumps(method_list, ensure_ascii=False, indent=2)

prompt = (
    "你是一位学术研究方法论专家，精通工程管理、项目管理、质量管理、系统工程等领域的研究方法命名规范。\n\n"
    "下面是一个论文辅助系统中的 234 个研究方法卡片。请逐一审核每个方法的名字，给出最权威、最规范的学术叫法。\n\n"
    "审核标准：\n"
    "1. 优先使用学术界通用的标准名称（如 '层次分析法' 而非 'AHP层次分析法'）\n"
    "2. 英文缩写该保留的保留（如 'FMEA失效模式与影响分析' → 建议保留，因为 FMEA 是行业通用缩写）\n"
    "3. 冗余后缀去掉（如 '问卷调查法' 已含'法'字，'法'不重复）\n"
    "4. 中英文混杂的统一：如果学术文献中以英文缩写为主，建议用缩写；如果以中文全称为主，建议用中文\n"
    "5. 同义词合并：如果两个卡片本质是同一个方法，标注出来\n"
    "6. 名字即可是独立的、可直接用于论文中作为方法名出现的，不要描述性短语\n"
    f"7. 保持与当前名相近，仅对明显不规范的进行调整\n\n"
    f"方法卡片列表：\n{input_json}\n\n"
    "只输出 JSON 数组，只包含需要改名或合并的卡片（不需要修改的不要输出以节省篇幅）。\n"
    "格式如下：\n"
    '[{"id": "原卡片ID", "current_name": "当前名", "recommended_name": "建议名", "change_type": "rename|merge", '
    '"merge_with": "合并目标卡片ID(仅merge时填)", "reason": "修改理由(15字内)"}]\n\n'
    "如果所有名字都已经很规范，输出空数组 []。"
)

# ── Call LLM ───────────────────────────────────────────
config = load_llm_config()
print(f"Provider: {config.provider}, Model: {config.model}")

import anthropic
kwargs = dict(api_key=config.api_key, max_retries=1)
if config.base_url:
    kwargs["base_url"] = config.base_url
client = anthropic.Anthropic(**kwargs)

print("正在调用 LLM 审核 234 个方法名...")
resp = client.messages.create(
    model=config.model,
    max_tokens=8000,
    system="你是学术研究方法论专家。只输出 JSON 数组，不要额外解释。",
    messages=[{"role": "user", "content": prompt}],
    thinking={"type": "disabled"},
)

raw = resp.content[0].text
raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
raw = re.sub(r"\s*```$", "", raw)

results = json.loads(raw)
print(f"LLM 返回 {len(results)} 条需要修改")

# ── Analyze ────────────────────────────────────────────
rename = [r for r in results if r.get("change_type") == "rename"]
merge = [r for r in results if r.get("change_type") == "merge"]
keep_count = len(method_list) - len(rename) - len(merge)

print(f"\n无需修改: ~{keep_count}")
print(f"需要改名 (rename): {len(rename)}")
print(f"需要合并 (merge): {len(merge)}")

# ── Show rename list ───────────────────────────────────
if rename:
    print(f"\n{'='*70}")
    print(f"需要改名的方法 ({len(rename)} 个):")
    print(f"{'='*70}")
    for r in rename:
        print(f"  {r['current_name']} → {r['recommended_name']}")
        print(f"    理由: {r.get('reason', '')}")

# ── Show merge list ────────────────────────────────────
if merge:
    print(f"\n{'='*70}")
    print(f"需要合并的方法 ({len(merge)} 个):")
    print(f"{'='*70}")
    for r in merge:
        target = r.get("merge_with", "?")
        # Find target name
        target_name = next((c["name"] for c in cards if c["id"] == target), target)
        print(f"  {r['current_name']} → 合并到 {target_name}")
        print(f"    理由: {r.get('reason', '')}")

# ── Save full report ───────────────────────────────────
report = {
    "summary": {"total": len(method_list), "rename": len(rename), "merge": len(merge), "keep_estimate": keep_count},
    "rename": rename,
    "merge": merge,
}
with open("/tmp/method_name_audit.json", "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n完整审核报告: /tmp/method_name_audit.json")
print("等待后续指令...")
