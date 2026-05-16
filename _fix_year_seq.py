"""年份矛盾修复 — 单线程顺序版，避免 8GB OOM。"""
import sqlite3, sys, time, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from anthropic import Anthropic
from llm_config import load_llm_config

DB = Path(__file__).resolve().parent / "knowledge_base" / "papers.sqlite3"

SYSTEM_PROMPT = """你是一位学术文献审核专家。你之前已确认下面这篇文献是真实存在的，只是引用年份与论文年份不一致。

现在请给出该文献的正确引用格式。直接返回标准的 GB/T 7714 格式引用文本。只返回引用文本，不要任何解释、不要 JSON、不要 markdown 标记。"""


def main():
    config = load_llm_config()
    client = Anthropic(api_key=config.api_key, base_url=config.base_url, timeout=60)

    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")

    rows = conn.execute(
        "SELECT card_id, formatted, ref_type, verification_note "
        "FROM citation_cards WHERE verified = -1 AND verification_note LIKE '%年份%' "
        "ORDER BY quality_score DESC"
    ).fetchall()

    total = len(rows)
    print(f"To fix: {total}")
    fixed = 0
    start = time.time()

    for idx, (card_id, formatted, ref_type, note) in enumerate(rows):
        user_msg = f"文献类型：{ref_type}\n当前引用格式：{formatted[:600]}\n之前备注：{note}\n\n请给出正确的标准引用格式："

        ok = False
        for attempt in range(2):
            try:
                resp = client.messages.create(
                    model=config.model, max_tokens=600,
                    thinking={"type": "disabled"},
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                )
                text = ""
                for block in resp.content:
                    if getattr(block, "type", "") == "text":
                        text += block.text
                fixed_text = text.strip()
                if fixed_text.startswith("```"):
                    fixed_text = fixed_text.split("\n", 1)[-1]
                    if fixed_text.endswith("```"):
                        fixed_text = fixed_text[:-3]
                    fixed_text = fixed_text.strip()
                if len(fixed_text) >= 15:
                    conn.execute(
                        "UPDATE citation_cards SET formatted = ?, verified = 1, verification_note = 'year fixed by LLM' WHERE card_id = ?",
                        (fixed_text, card_id),
                    )
                    ok = True
                break
            except Exception as e:
                if attempt == 1:
                    print(f"  ERR {card_id}: {e}")
                time.sleep(1)

        if ok:
            fixed += 1

        if (idx + 1) % 50 == 0:
            conn.commit()
            elapsed = time.time() - start
            rate = (idx + 1) / elapsed
            eta = (total - idx - 1) / rate / 60 if rate > 0 else 0
            print(f"  [{idx+1}/{total}] fixed:{fixed} | {rate:.1f}/s | ETA {eta:.0f}min")
        if (idx + 1) % 200 == 0:
            # 周期性重建 client，防止内存累积
            import gc
            del client
            gc.collect()
            client = Anthropic(api_key=config.api_key, base_url=config.base_url, timeout=60)

    conn.commit()
    elapsed = time.time() - start
    print(f"\nDONE in {elapsed/60:.1f}min: {fixed} fixed, {total-fixed} failed")
    conn.close()


if __name__ == "__main__":
    main()
