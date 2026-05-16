"""
LLM 修复格式错误引用 — 并发版。
对 verified=-2 的卡片，调用 LLM 返回修正后的引用文本，反填 formatted 字段。
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

SYSTEM_PROMPT = """你是一位学术文献格式修复专家。你的任务是修复有格式问题的参考文献引用文本。

请保持原文献的作者、标题、期刊、年份、卷期号、页码等核心信息不变，只修复格式问题：
- 缺少空格的地方补空格
- 多余空格删除
- DOI 补齐缺失部分（如 cnki）
- 页码范围修复（如 8890 → 88-90）
- 标点符号规范化
- 多余字符删除

直接返回修复后的引用文本，不要任何解释、不要 JSON、不要 markdown 标记。只返回修复后的纯文本。"""

CONCURRENCY = 5


def fix_one(card_data: tuple, client, model: str) -> tuple:
    card_id, formatted, authors, year, ref_type = card_data
    parts = [f"类型：{ref_type}"]
    if authors and authors.strip():
        parts.append(f"作者：{authors}")
    if year and str(year).strip() and str(year) != "0":
        parts.append(f"年份：{year}")
    parts.append(f"当前引用文本（需要修复）：\n{formatted}")
    user_msg = "\n".join(parts)

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
            # Basic validation: must have reasonable length
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

    rows = conn.execute(
        "SELECT card_id, formatted, authors, year, ref_type "
        "FROM citation_cards WHERE verified = -2 ORDER BY quality_score DESC"
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

    BATCH = 200
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
                            "UPDATE citation_cards SET formatted = ?, verified = 1, verification_note = 'format fixed by LLM' WHERE card_id = ?",
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
