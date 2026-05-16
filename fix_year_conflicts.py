"""
对「年份矛盾」类 fake 卡片，追问 LLM 返回正确格式并反填。
"""
import json, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from anthropic import Anthropic
from llm_config import load_llm_config

DB = Path(__file__).resolve().parent / "knowledge_base" / "papers.sqlite3"

SYSTEM_PROMPT = """你是一位学术文献审核专家。你之前已确认下面这篇文献是真实存在的，只是引用年份与论文年份不一致。

现在请给出该文献的正确引用格式。直接返回标准的 GB/T 7714 格式引用文本。只返回引用文本，不要任何解释、不要 JSON、不要 markdown 标记。"""

CONCURRENCY = 3


def fix_one(card_data: tuple, client, model: str) -> tuple:
    card_id, formatted, ref_type, note = card_data
    user_msg = f"""文献类型：{ref_type}
当前引用格式：{formatted[:600]}
之前备注：{note}

请给出正确的标准引用格式："""

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=600,
                thinking={"type": "disabled"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = ""
            for block in response.content:
                if getattr(block, "type", "") == "text":
                    text += block.text
            fixed = text.strip()
            if fixed.startswith("```"):
                fixed = fixed.split("\n", 1)[-1]
                if fixed.endswith("```"):
                    fixed = fixed[:-3]
                fixed = fixed.strip()
            if len(fixed) < 15:
                return (card_id, formatted, "too_short")
            return (card_id, fixed, "ok")
        except Exception:
            if attempt == 1:
                return (card_id, formatted, str(sys.exc_info()[1])[:60])
            time.sleep(1)


def main():
    config = load_llm_config()
    if not config.api_key:
        print("ERROR: No API key configured")
        sys.exit(1)

    print(f"Model: {config.model}")
    print(f"Concurrency: {CONCURRENCY}")

    import sqlite3
    conn = sqlite3.connect(str(DB))

    # 找所有年份相关卡片（含 年份矛盾、年份冲突、年份不符 等）
    rows = conn.execute(
        "SELECT card_id, formatted, ref_type, verification_note "
        "FROM citation_cards WHERE verified = -1 AND verification_note LIKE '%年份%' "
        "ORDER BY quality_score DESC"
    ).fetchall()

    total = len(rows)
    print(f"Cards to fix: {total}")
    if total == 0:
        print("Nothing to do.")
        conn.close()
        return

    model = config.model
    fixed_count = 0
    error_count = 0
    start_time = time.time()
    lock = threading.Lock()
    done = 0

    BATCH = 100
    for batch_start in range(0, total, BATCH):
        batch = rows[batch_start:batch_start + BATCH]
        client = Anthropic(api_key=config.api_key, base_url=config.base_url, timeout=60)

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {
                executor.submit(fix_one, row, client, model): i
                for i, row in enumerate(batch)
            }

            for future in as_completed(futures):
                card_id, fixed_text, status = future.result()
                with lock:
                    if status == "ok":
                        conn.execute(
                            "UPDATE citation_cards SET formatted = ?, verified = 1, verification_note = 'year fixed by LLM' WHERE card_id = ?",
                            (fixed_text, card_id),
                        )
                        fixed_count += 1
                    else:
                        error_count += 1
                    done += 1

        conn.commit()
        import gc
        gc.collect()

        elapsed = time.time() - start_time
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        print(f"[{done}/{total}] fixed:{fixed_count} err:{error_count} | {rate:.1f}/s | ETA {eta/60:.0f}min")

    elapsed = time.time() - start_time
    conn.close()

    print(f"\n{'='*50}")
    print(f"DONE in {elapsed/60:.1f} min")
    print(f"  Fixed: {fixed_count}")
    print(f"  Errors: {error_count}")


if __name__ == "__main__":
    main()
