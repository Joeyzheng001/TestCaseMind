#!/usr/bin/env python3
"""AB 测试：自由分类 vs 受控词表分类"""

import json, sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from llm_config import load_llm_config

# ── Load data ──────────────────────────────────────────
with open("/tmp/cite_test_batch.json") as f:
    batch = json.load(f)

with open("/tmp/method_vocab.json") as f:
    vocab_data = json.load(f)

with open("/tmp/alias_map.json") as f:
    alias_map = json.load(f)

# ── Build prompts ──────────────────────────────────────
cite_list = json.dumps(
    [{"card_id": c["card_id"], "title": c["title"][:200]} for c in batch],
    ensure_ascii=False, indent=2,
)

# Prompt A: free-form
prompt_free = (
    "请分析以下参考文献引用，每条根据标题判断该文献使用的研究方法和理论框架。\n\n"
    "要求：\n"
    "1. 只看标题中的关键词来判断\n"
    "2. 标题中明确包含方法/理论关键词才标注，不要猜测\n"
    "3. 方法名要规范通用（如：作业成本法、社会网络分析、BIM、PDCA、层次分析法、模糊综合评价等）\n"
    "4. 没有明确方法论关键词的返回空数组\n\n"
    f"参考文献列表：\n{cite_list}\n\n"
    "只输出JSON数组：\n"
    '[{"card_id": "...", "methods": ["方法1"], "theories": ["理论1"]}, ...]'
)

# Prompt B: controlled vocabulary
# Build compact method list
vocab_compact = []
for c in vocab_data["cards"]:
    name = c["name"]
    aliases = [a for a in c["aliases"] if a != name]
    if aliases:
        vocab_compact.append(f"{name}（也称作：{'、'.join(aliases)}）")
    else:
        vocab_compact.append(name)
vocab_text = "\n".join(f"- {v}" for v in vocab_compact)

prompt_ctrl = (
    "请分析以下参考文献引用，每条根据标题判断该文献使用的研究方法。\n\n"
    "要求：\n"
    "1. 只看标题中的关键词来判断\n"
    "2. 标题中明确包含方法关键词才标注，不要猜测\n"
    "3. 方法名必须从下方的受控词表中选择，不得自创\n"
    "4. 如果标题中的方法关键词匹配到某个方法的别名，请使用规范名称（括号外的名称）\n"
    "5. 没有明确方法论关键词的返回空数组\n\n"
    f"受控方法词表：\n{vocab_text}\n\n"
    f"参考文献列表：\n{cite_list}\n\n"
    "只输出JSON数组：\n"
    '[{"card_id": "...", "methods": ["规范方法名1"]}, ...]'
)

# ── LLM Client ─────────────────────────────────────────
config = load_llm_config()
provider = config.provider
print(f"Provider: {provider}, Model: {config.model}")

if not config.api_key:
    print("ERROR: 未配置 API Key")
    sys.exit(1)

if provider in ("anthropic", "deepseek", "minimax", "moonshot", "zhipu", "qwen"):
    import anthropic
    kwargs = dict(api_key=config.api_key, max_retries=1)
    if config.base_url:
        kwargs["base_url"] = config.base_url
    client = anthropic.Anthropic(**kwargs)

    def call_llm(system_prompt, user_prompt, max_tokens=3000):
        resp = client.messages.create(
            model=config.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            thinking={"type": "disabled"},
        )
        return resp.content[0].text
elif provider == "openai":
    import openai
    client = openai.OpenAI(api_key=config.api_key, base_url=config.base_url)

    def call_llm(system_prompt, user_prompt, max_tokens=3000):
        resp = client.chat.completions.create(
            model=config.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content
else:
    print(f"Unsupported provider: {provider}")
    sys.exit(1)

# ── Parse helper ───────────────────────────────────────
def parse_response(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    if text.startswith("["):
        return json.loads(text)
    if text.startswith("{"):
        obj = json.loads(text)
        return obj if isinstance(obj, list) else obj.get("results", obj.get("data", []))
    return []

# ── Run A/B ────────────────────────────────────────────
system = "你是研究方法分类专家。根据文献标题中的关键词判断该文献涉及的研究方法，只标注明确的，不猜测。"

print("\n" + "=" * 60)
print("方案 A: LLM 自由发挥")
print("=" * 60)
raw_a = call_llm(system, prompt_free)
results_a = parse_response(raw_a)
print(f"返回 {len(results_a)} 条，共 {sum(len(r.get('methods',[])) for r in results_a)} 个方法标注")

print("\n" + "=" * 60)
print("方案 B: 受控词表")
print("=" * 60)
raw_b = call_llm(system, prompt_ctrl)
results_b = parse_response(raw_b)
print(f"返回 {len(results_b)} 条，共 {sum(len(r.get('methods',[])) for r in results_b)} 个方法标注")

# ── Normalize A to canonical names ─────────────────────
def normalize(method_name):
    """Map to canonical name via alias map, fuzzy fallback."""
    key = method_name.strip().lower()
    if key in alias_map:
        return alias_map[key]
    # Try common variations
    for suffix in ["法", "方法", "分析", "分析法", "模型", "理论", "技术", "管理"]:
        if key.endswith(suffix) and key[:-len(suffix)] in alias_map:
            return alias_map[key[:-len(suffix)]]
    return None  # NO match → unknown

results_a_norm = []
unknown_methods = set()
matched_methods = set()
for r in results_a:
    card_id = r.get("card_id", "")
    methods = r.get("methods", []) or []
    norm = []
    for m in methods:
        canon = normalize(m)
        if canon:
            norm.append(canon)
            matched_methods.add(canon)
        else:
            norm.append(f"*{m}")  # mark as unknown
            unknown_methods.add(m)
    results_a_norm.append({"card_id": card_id, "methods": norm})

results_b_norm = []
for r in results_b:
    card_id = r.get("card_id", "")
    methods = r.get("methods", []) or []
    results_b_norm.append({"card_id": card_id, "methods": methods})

# ── Side-by-side comparison ────────────────────────────
print("\n" + "=" * 60)
print("并排对比 (仅显示有方法标注的条目)")
print("=" * 60)

# Build lookup dicts
dict_a = {r["card_id"]: r["methods"] for r in results_a_norm}
dict_b = {r["card_id"]: r["methods"] for r in results_b_norm}

title_map = {c["card_id"]: c["title"][:90] for c in batch}

shown = 0
for card_id in sorted(set(list(dict_a.keys()) + list(dict_b.keys()))):
    m_a = dict_a.get(card_id, [])
    m_b = dict_b.get(card_id, [])
    if not m_a and not m_b:
        continue
    shown += 1
    title = title_map.get(card_id, "")[:80]
    print(f"\n{shown}. {title}")
    print(f"   A(自由):   {m_a if m_a else '(无)'}")
    print(f"   B(受控):   {m_b if m_b else '(无)'}")

    # Highlight differences
    set_a = {m.replace("*", "") for m in m_a if not m.startswith("*")}
    set_b = set(m_b)
    only_a = set_a - set_b
    only_b = set_b - set_a
    unknown_a = {m for m in m_a if m.startswith("*")}
    if only_a:
        print(f"   → A独有(匹配成功): {list(only_a)}")
    if unknown_a:
        print(f"   → A未知方法(无匹配): {list(unknown_a)}")
    if only_b:
        print(f"   → B独有: {list(only_b)}")

# ── Summary stats ──────────────────────────────────────
print("\n" + "=" * 60)
print("统计汇总")
print("=" * 60)

total_a_methods = sum(len(r["methods"]) for r in results_a_norm)
total_b_methods = sum(len(r["methods"]) for r in results_b_norm)
pct_a_labeled = sum(1 for r in results_a_norm if r["methods"]) / len(results_a_norm) * 100
pct_b_labeled = sum(1 for r in results_b_norm if r["methods"]) / len(results_b_norm) * 100

print(f"方案 A (自由): {total_a_methods} 个方法标注, {pct_a_labeled:.0f}% 条目有方法")
print(f"  - 匹配卡片库: {len(matched_methods)} 个方法")
print(f"  - 无匹配(新方法): {len(unknown_methods)} 个 → {list(unknown_methods)}")
print(f"方案 B (受控): {total_b_methods} 个方法标注, {pct_b_labeled:.0f}% 条目有方法")

# Save full results
with open("/tmp/ab_test_results.json", "w") as f:
    json.dump({
        "results_a": results_a_norm,
        "results_b": results_b_norm,
        "unknown_methods": list(unknown_methods),
        "matched_methods": list(matched_methods),
        "stats": {
            "a_total": total_a_methods, "a_labeled_pct": pct_a_labeled,
            "b_total": total_b_methods, "b_labeled_pct": pct_b_labeled,
            "a_unknown_count": len(unknown_methods),
            "a_matched_count": len(matched_methods),
        }
    }, f, ensure_ascii=False, indent=2)

print(f"\n完整结果: /tmp/ab_test_results.json")
