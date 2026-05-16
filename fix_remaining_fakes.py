"""
宽松核验剩余 fake 卡片：只判断文献是否真实存在，返回正确 GB/T 7714 格式反填。
仅当完全找不到任何信息时才保留 fake。
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

SYSTEM_PROMPT = """你是一位学术文献核验专家。请核验以下参考文献引用。

规则：
1. 如果能确认该文献真实存在（作者、标题、期刊/出版社组合合理），返回正确的 GB/T 7714 标准引用格式
2. 如果文献真实但格式有小问题（页码缺横线、DOI格式异常、空格不规范），请修正后返回正确格式
3. 如果文献真实但某些字段与元数据不符（如论文年份2024但引用的是2018年的文章），这是正常引用行为，不是矛盾——请返回正确格式
4. 仅在完全找不到该文献的任何信息时，才返回 NOT_FOUND

重要：引用年份早于论文年份是正常现象，不是矛盾。作者字段为空不代表文献不存在。

直接返回引用文本或 NOT_FOUND，不要任何解释、不要 JSON、不要 markdown 标记。"""

CONCURRENCY = 5


def fix_one(card_data: tuple, client, model: str) -> tuple:
    card_id, formatted, ref_type, note = card_data
    user_msg = f"文献类型：{ref_type}\n当前格式：{formatted[:600]}\n之前备注：{note}\n\n请核验并返回正确格式："

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model, max_tokens=600,
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
            if fixed.upper() == "NOT_FOUND" or len(fixed) < 15:
                return (card_id, None, "not_found")
            return (card_id, fixed, "fixed")
        except Exception:
            if attempt == 1:
                return (card_id, None, str(sys.exc_info()[1])[:60])
            time.sleep(1)


def main():
    config = load_llm_config()
    if not config.api_key:
        print("ERROR: No API key configured")
        sys.exit(1)

    print(f"Model: {config.model}, Concurrency: {CONCURRENCY}")

    import sqlite3
    conn = sqlite3.connect(str(DB))

    # 优先回收: 作者矛盾 + 页码/卷期异常 + 期刊名损坏 + 学位论文
    # 排除明显虚构/垃圾拼接类
    rows = conn.execute(
        "SELECT card_id, formatted, ref_type, verification_note FROM citation_cards "
        "WHERE verified = -1 AND verification_note NOT LIKE '%虚构%' "
        "AND verification_note NOT LIKE '%垃圾%' AND verification_note NOT LIKE '%拼接%' "
        "AND verification_note NOT LIKE '%不存在%' AND verification_note NOT LIKE '%无法查证%' "
        "ORDER BY quality_score DESC"
    ).fetchall()

    total = len(rows)
    print(f"Cards to re-verify: {total}")

    model = config.model
    fixed_count = 0
    not_found = 0
    error_count = 0
    start_time = time.time()
    lock = threading.Lock()
    done = 0

    BATCH = 150
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
                    if status == "fixed":
                        conn.execute(
                            "UPDATE citation_cards SET formatted = ?, verified = 1, verification_note = 're-verified: corrected format' WHERE card_id = ?",
                            (fixed_text, card_id),
                        )
                        fixed_count += 1
                    elif status == "not_found":
                        conn.execute(
                            "UPDATE citation_cards SET verification_note = 're-verified: truly NOT_FOUND' WHERE card_id = ?",
                            (card_id,),
                        )
                        not_found += 1
                    else:
                        error_count += 1
                    done += 1

        conn.commit()
        import gc
        gc.collect()

        elapsed = time.time() - start_time
        rate = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / rate / 60 if rate > 0 else 0
        print(f"[{done}/{total}] fixed:{fixed_count} nf:{not_found} err:{error_count} | {rate:.1f}/s | ETA {eta:.0f}min")

    elapsed = time.time() - start_time
    conn.close()

    print(f"\nDONE in {elapsed/60:.1f}min")
    print(f"  Fixed: {fixed_count}")
    print(f"  NOT_FOUND: {not_found}")
    print(f"  Errors: {error_count}")


if __name__ == "__main__":
    main()
