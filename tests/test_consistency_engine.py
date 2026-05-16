"""一致性引擎全面测试 — 覆盖 G1-G11 修复验证"""
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.consistency_engine import (
    extract_commitments,
    merge_commitments_to_memory,
    build_commitment_brief,
    build_unresolved_warning,
    verify_commitments,
    verify_citations,
    _parse_citation_indices,
    _get_methods_pattern,
    _get_method_promise_pattern,
    _invalidate_methods_pattern_cache,
    _load_method_names_from_db,
    _check_definition_drift,
    _definition_similarity,
)

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  FAILED  {detail}")


# ═══════════════════════════════════════════════════════════════
print("=== G5: 方法名从 cards DB 动态加载 ===")
_invalidate_methods_pattern_cache()
names = _load_method_names_from_db()
check("从DB加载方法名", len(names) > 200, f"实际: {len(names)}")
check("包含中文名", "层次分析法" in names)
check("包含英文缩写", "AHP" in names)
check("包含全量方法", "贝叶斯更新法" in names or any("贝叶斯" in n for n in names))

pattern = _get_methods_pattern()
check("正则已构建", len(pattern.pattern) > 1000, f"长度: {len(pattern.pattern)}")

promise_pattern = _get_method_promise_pattern()
check("承诺正则已构建", len(promise_pattern.pattern) > 1000)

# ═══════════════════════════════════════════════════════════════
print("\n=== G6: 方法承诺 vs 使用 区分 ===")
text = "本文将采用层次分析法对6个核心问题进行评估。同时引入德尔菲法收集专家意见。研究中使用了鱼骨图分析根因。"
result = extract_commitments(text, "第一章", "1.1")
promises = [i for i in result["items"] if i.get("source") == "promise"]
usages = [i for i in result["items"] if i.get("source") == "usage"]

check("提取到承诺", len(promises) >= 1, f"promises={[p['method'] for p in promises]}")
check("层次分析法为承诺", any(p["method"] == "层次分析法" for p in promises))
check("德尔菲法为承诺/使用", any(p["method"] == "德尔菲法" for p in promises + usages))
check("数量提取正确", any(i["type"] == "quantity" and "6个核心问题" in i["raw"] for i in result["items"]))

# "运用X" 是承诺句式，"和Y" 中 Y 无独立前缀 → usage
text2 = "本章运用鱼骨图和帕累托分析法完成了数据分析。"
result2 = extract_commitments(text2, "第二章", "2.1")
methods2 = [(i.get("source"), i.get("method")) for i in result2["items"] if i["type"] == "method"]
check("运用鱼骨图检测为promise",
      any(src == "promise" and m == "鱼骨图" for src, m in methods2),
      f"methods={methods2}")
check("帕累托分析法(跟在和后面无前缀)为usage",
      any(src == "usage" and m == "帕累托分析法" for src, m in methods2),
      f"methods={methods2}")

# ═══════════════════════════════════════════════════════════════
print("\n=== G3: verify_commitments 事后校验 ===")
memory = {}
memory = merge_commitments_to_memory(memory, "第一章", "1.1",
    "本文将采用层次分析法和模糊综合评价对6个核心风险因素进行评估。本文定义质量管理为系统化的质量保证活动。")
memory = merge_commitments_to_memory(memory, "第二章", "2.1",
    "本章使用鱼骨图进行根因分析。")

# Ch3 覆盖了层次分析法但没覆盖模糊综合评价
v = verify_commitments(
    "本研究通过层次分析法完成了权重计算，覆盖了6个核心风险因素。质量管理贯穿始终。",
    memory, "第三章"
)
check("total_commitments > 0", v["total_commitments"] > 0, f"total={v['total_commitments']}")
check("resolved >= 2", v["resolved"] >= 2, f"resolved={v['resolved']}")
check("hard_unresolved >= 1 (模糊综合评价未覆盖)", v["hard_unresolved"] >= 1, f"hard={v['hard_unresolved']}")
check("区分 hard/soft", "soft_unresolved" in v)

# ═══════════════════════════════════════════════════════════════
print("\n=== G7: 术语定义漂移检测 ===")
mem_def = {}
mem_def = merge_commitments_to_memory(mem_def, "第一章", "1.1",
    "质量管理是指通过系统化的方法确保产品或服务满足既定标准的活动。风险管理是指识别和评估潜在威胁的过程。")

# 相同定义 -> 无漂移
v1 = verify_commitments(
    "质量管理是指通过系统化的方法确保产品或服务满足既定标准的持续性活动。",
    mem_def, "第二章"
)
drifts1 = v1.get("definition_drifts", [])
check("相似定义不算漂移(similarity>=0.3)", len(drifts1) == 0,
      f"drifts={len(drifts1)}")

# 完全不同定义 -> 漂移
v2 = verify_commitments(
    "质量管理是指企业为提升短期利润而采取的各项成本削减措施。",
    mem_def, "第二章"
)
drifts2 = v2.get("definition_drifts", [])
check("完全不同的定义检测到漂移", len(drifts2) >= 1,
      f"drifts={len(drifts2)}")

# 只是使用术语，未重新定义 -> 无漂移
v3 = verify_commitments(
    "本研究在质量管理方面取得了显著成效。",
    mem_def, "第二章"
)
drifts3 = v3.get("definition_drifts", [])
check("仅引用术语不触发漂移", len(drifts3) == 0, f"drifts={len(drifts3)}")

# ═══════════════════════════════════════════════════════════════
print("\n=== G8: 引用校验 ===")
content = "文献[1]指出该方法有效。根据[2][3]的研究，进一步验证了[4-6]的结论。"
check_result = verify_citations(content, [0, 1, 2, 3, 4, 5], [{}, {}, {}, {}, {}, {}])
check("properly_cited=[0,1,2,3,4,5]", sorted(check_result["properly_cited"]) == [0, 1, 2, 3, 4, 5],
      f"properly={check_result['properly_cited']}")
check("无缺失引用", len(check_result["missing"]) == 0, f"missing={check_result['missing']}")

# Missing citation
content2 = "文献[1]提供了基础理论。"
check2 = verify_citations(content2, [0, 2], [{}, {}, {}])
check("检测到缺失引用[2]", 2 in check2["missing"], f"missing={check2['missing']}")
check("检测到意外引用(空)", len(check2["unknown"]) == 0, f"unknown={check2['unknown']}")

# Fabricated citation
content3 = "参见[99]的研究。"
check3 = verify_citations(content3, [0], [{}])
check("检测虚构引用99", 98 in check3["fabricated_indices"],
      f"fabricated={check3['fabricated_indices']}")

# No citations required but found
content4 = "本研究具有重要价值[1]。"
check4 = verify_citations(content4, [], [])
check("无引用要求时检测到误加", check4["any_found"] == True)

# Citation marker parsing
check("解析[1-3]", _parse_citation_indices("[1-3]") == [0, 1, 2])
check("解析[2,5]", sorted(_parse_citation_indices("[2,5]")) == [1, 4])
check("解析[1—3]", sorted(_parse_citation_indices("[1—3]")) == [0, 1, 2])

# ═══════════════════════════════════════════════════════════════
print("\n=== 承诺摘要与警告生成 ===")
brief = build_commitment_brief(memory)
check("承诺摘要不为空", len(brief) > 0)
check("包含方法承诺", "层次分析法" in brief)

warning = build_unresolved_warning(memory, "第三章")
check("未闭合警告生成", len(warning) > 0)

# ═══════════════════════════════════════════════════════════════
print("\n=== 定义相似度 ===")
sim = _definition_similarity("系统化的质量保证活动", "通过系统化的方法确保产品质量的活动")
check("相似定义相似度>0.3", sim > 0.3, f"sim={sim:.3f}")

sim2 = _definition_similarity("系统化的质量保证活动", "企业利润最大化策略")
check("不同定义相似度<0.3", sim2 < 0.3, f"sim={sim2:.3f}")

# ═══════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"  结果: {PASS} 通过 / {FAIL} 失败")
print(f"{'='*50}")
if FAIL > 0:
    sys.exit(1)
