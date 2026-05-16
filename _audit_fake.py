"""Audit fake citations for potential misclassification."""
import sqlite3

conn = sqlite3.connect("knowledge_base/papers.sqlite3")

notes = conn.execute(
    "SELECT verification_note FROM citation_cards WHERE verified = -1 AND verification_note != ''"
).fetchall()

cat = {"年份矛盾": 0, "问卷/非学术文献": 0, "作者/格式矛盾": 0, "无法查证/虚构": 0}
other_notes = []

for (note,) in notes:
    if "年份矛盾" in note or ("年份" in note and "矛盾" in note):
        cat["年份矛盾"] += 1
    elif any(w in note for w in ["问卷", "非学术", "非文献", "调查", "选项", "量表", "题目", "题干"]):
        cat["问卷/非学术文献"] += 1
    elif any(w in note for w in ["作者", "格式混乱", "格式异常", "不一致"]):
        cat["作者/格式矛盾"] += 1
    elif any(w in note for w in ["无法查", "无法验证", "无法确认", "虚构", "不存在"]):
        cat["无法查证/虚构"] += 1
    else:
        other_notes.append(note)

for k, v in cat.items():
    print(f"  {k}: {v}")

total_with_note = sum(cat.values()) + len(other_notes)
total_fake = conn.execute("SELECT COUNT(*) FROM citation_cards WHERE verified = -1").fetchone()[0]
empty = total_fake - total_with_note
print(f"  其他: {len(other_notes)}")
print(f"  无note: {empty}")
print(f"  总计: {total_fake}")

if other_notes:
    print(f"\n=== 其他类型 note (共{len(other_notes)}条) ===")
    for n in other_notes[:30]:
        print(f"  - {n[:120]}")

# 年份矛盾样本
print("\n=== 年份矛盾 样本 (可能是真实文献) ===")
samples = conn.execute(
    "SELECT card_id, formatted, verification_note FROM citation_cards WHERE verified = -1 AND verification_note LIKE '%年份矛盾%' LIMIT 10"
).fetchall()
for cid, fmt, note in samples:
    print(f"  [{cid}] {fmt[:120]}")
    print(f"    note: {note}")
    print()

conn.close()
