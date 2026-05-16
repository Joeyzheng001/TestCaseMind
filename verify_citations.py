"""
逐条调用 LLM 验证引用真实性 — 并发版。
确认存在的 → verified=1
明确虚假/查不到 → verified=-1
文章存在但格式有问题 → verified=-2, verification_note 记录格式问题
"""

import json
import sys
import time
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from anthropic import Anthropic
from llm_config import load_llm_config

DB = Path(__file__).resolve().parent / "knowledge_base" / "papers.sqlite3"

SYSTEM_PROMPT = """你是一位学术文献审核专家。你的任务是在互联网知识范围内，验证一条参考文献引用的真实性和准确性。

请判断：
1. 作者、标题、期刊/会议/出版社的组合是否指向一篇真实的学术文献
2. 年份是否在合理范围内
3. 引用格式是否有明显问题（缺少期卷号、页码格式异常、DOI格式错误、缺少空格等）

注意：格式小问题不代表文献不存在。请区分「文献本身不存在/虚构」和「文献真实但格式不规范」。如果根据作者+标题+期刊的组合可以合理推断该文献存在，即使个别字段不规范，也应判断为文献真实。

回复严格的 JSON 格式，不要包含其他文字：
- 文献真实可确认：{"status": "verified"}
- 文献真实但格式有问题：{"status": "format_error", "note": "格式问题说明（简洁，20字以内）"}
- 明确无法查到或疑似虚构：{"status": "fake", "note": "无法确认原因（简洁，20字以内）"}"""

CONCURRENCY = 5


def _parse_response(response) -> dict:
    """Extract text from API response and parse JSON."""
    text = ""
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text += block.text
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


def verify_one(card_data: tuple, client, model: str) -> tuple:
    """Call LLM to verify one citation. Returns (card_id, status, note)."""
    card_id, formatted, authors, year, ref_type = card_data
    parts = [f"类型：{ref_type}"]
    if authors and authors.strip():
        parts.append(f"作者：{authors}")
    if year and str(year).strip() and str(year) != "0":
        parts.append(f"年份：{year}")
    parts.append(f"引用格式：{formatted[:500]}")
    user_msg = "请验证以下参考文献：\n\n" + "\n".join(parts)

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=256,
                thinking={"type": "disabled"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            result = _parse_response(response)
            status = result.get("status", "fake")
            note = result.get("note", "") if status != "verified" else ""
            return (card_id, status, note)
        except Exception:
            if attempt == 1:
                return (card_id, "error", str(sys.exc_info()[1])[:60])
            time.sleep(1)


def main():
    config = load_llm_config()
    if not config.api_key:
        print("ERROR: No API key configured")
        sys.exit(1)

    print(f"Model: {config.model}")
    print(f"Concurrency: {CONCURRENCY}")

    conn = sqlite3.connect(str(DB))

    # Verify ALL unverified cards
    rows = conn.execute(
        "SELECT card_id, formatted, authors, year, ref_type "
        "FROM citation_cards WHERE verified = 0 ORDER BY quality_score DESC"
    ).fetchall()

    total = len(rows)
    print(f"Cards to verify: {total}")

    model = config.model
    counts = {"verified": 0, "format_error": 0, "fake": 0, "error": 0}
    start_time = time.time()
    lock = threading.Lock()
    done = 0

    # Process in small batches to limit memory
    BATCH = 200
    for batch_start in range(0, total, BATCH):
        batch = rows[batch_start:batch_start + BATCH]
        client = Anthropic(api_key=config.api_key, base_url=config.base_url, timeout=60)

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {
                executor.submit(verify_one, row, client, model): i
                for i, row in enumerate(batch)
            }

            for future in as_completed(futures):
                card_id, status, note = future.result()
                with lock:
                    if status == "verified":
                        conn.execute(
                            "UPDATE citation_cards SET verified = 1, verification_note = '' WHERE card_id = ?",
                            (card_id,),
                        )
                    elif status == "format_error":
                        conn.execute(
                            "UPDATE citation_cards SET verified = -2, verification_note = ? WHERE card_id = ?",
                            (note[:200], card_id),
                        )
                    else:
                        v = -1 if status == "fake" else 0
                        conn.execute(
                            "UPDATE citation_cards SET verified = ?, verification_note = ? WHERE card_id = ?",
                            (v, note[:200], card_id),
                        )
                    counts[status] = counts.get(status, 0) + 1
                    done += 1

        conn.commit()
        import gc
        gc.collect()

        elapsed = time.time() - start_time
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        print(
            f"[{done}/{total}] ✓{counts['verified']} "
            f"~{counts['format_error']} ✗{counts['fake']} "
            f"?{counts.get('error',0)} "
            f"| {rate:.1f}/s | ETA {eta/60:.0f}min"
        )

    elapsed = time.time() - start_time
    conn.close()

    print(f"\n{'='*50}")
    print(f"DONE in {elapsed/60:.1f} min")
    print(f"  Verified (确认):     {counts['verified']}")
    print(f"  Format error (格式): {counts['format_error']}")
    print(f"  Fake (虚假):         {counts['fake']}")
    print(f"  Error (错误):        {counts.get('error',0)}")
    print(f"  Total:               {total}")
    print(f"  Rate:                {total/elapsed:.1f}/s")


if __name__ == "__main__":
    main()
