"""
拆分多引用粘合卡片：按 [N] 标记切成独立卡片。
"""
import sqlite3, re, uuid, sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "knowledge_base" / "papers.sqlite3"


def split_formatted(text: str) -> list[str]:
    """按 [数字] 标记拆分引用文本，返回独立引用列表。"""
    # 移除开头的"参考文献"标签
    text = re.sub(r'^参考文献\s*', '', text)

    # 按 [数字] 分割，保留分隔符
    parts = re.split(r'(?=\[\d+\])', text)

    results = []
    for part in parts:
        part = part.strip()
        # 去除开头的序号标记
        part = re.sub(r'^\[\d+\]\s*', '', part)
        # 过滤太短的和纯 NOT_FOUND 的
        if len(part) < 15:
            continue
        if part.strip().upper() == 'NOT_FOUND':
            continue
        # 去除末尾残留的 NOT_FOUND
        part = re.sub(r'\s*NOT_FOUND\s*$', '', part)
        if len(part) >= 15:
            results.append(part.strip())

    # 如果没有 [N] 标记但包含多个引用特征（多个 [J]/[D]/[M]），
    # 尝试按文献类型标记 + 序号组合分割
    if len(results) <= 1:
        # 按 。[ 或 . [ 分割
        parts = re.split(r'(?<=[。.])\s*(?=\[\d+\])', text)
        results = []
        for part in parts:
            part = part.strip()
            part = re.sub(r'^\[\d+\]\s*', '', part)
            if len(part) >= 15:
                results.append(part)

    return results if results else [text]


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA journal_mode=WAL")

    # 找所有含多个 [N] 标记的卡片
    rows = conn.execute(
        "SELECT * FROM citation_cards WHERE formatted LIKE '%[%]%[%]%' AND (formatted LIKE '%[J]%' OR formatted LIKE '%[D]%' OR formatted LIKE '%[M]%')"
    ).fetchall()

    # 获取列名
    cols = [desc[0] for desc in conn.execute("SELECT * FROM citation_cards LIMIT 0").description]

    print(f"Found {len(rows)} multi-ref cards")

    split_count = 0
    deleted_count = 0
    kept_count = 0

    for row in rows:
        card = dict(zip(cols, row))
        card_id = card['card_id']
        formatted = card['formatted']

        refs = split_formatted(formatted)

        if len(refs) <= 1:
            # 无法拆分，尝试另一种方式：按 [N] 在中间出现的位置
            # 检查是否确实是单条引用
            n_markers = len(re.findall(r'\[\d+\]', formatted))
            if n_markers <= 1:
                kept_count += 1
                continue
            # 多个标记但 split 失败了
            refs = re.split(r'(?<=\S)\s*(?=\[\d+\][^JDM])', formatted)
            refs = [re.sub(r'^\[\d+\]\s*', '', r).strip() for r in refs if len(r.strip()) >= 15]

        if len(refs) <= 1:
            kept_count += 1
            continue

        # 创建新卡片，每条引用一个
        for ref_text in refs:
            new_id = f"CITE-{uuid.uuid4().hex[:8].upper()}"
            try:
                import json
                methods_val = card.get('methods_json', '') or ''
                if isinstance(methods_val, list):
                    methods_val = json.dumps(methods_val, ensure_ascii=False)
                tags_val = card.get('theory_tags_json', '') or ''
                if isinstance(tags_val, list):
                    tags_val = json.dumps(tags_val, ensure_ascii=False)
                conn.execute(
                    """INSERT INTO citation_cards
                    (card_id, paper_id, formatted, title, authors, year, language, ref_type,
                     methods_json, direction_id, direction_label, theory_tags_json, verified,
                     verification_note, inserted_count, quality_score, source_section,
                     source_paper_title)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'split from multi-ref', 0, ?, '', '')""",
                    (
                        new_id, card.get('paper_id', ''), ref_text, ref_text[:120],
                        card.get('authors', '') or '', str(card.get('year', '') or ''),
                        card.get('language', '') or 'zh', card.get('ref_type', '') or 'J',
                        methods_val, card.get('direction_id', '') or '',
                        card.get('direction_label', '') or '', tags_val,
                        card.get('quality_score', 0.5) or 0.5,
                    )
                )
                split_count += 1
            except Exception as e:
                print(f"  ERR inserting split ref: {e}")

        # 删除原始合并卡片
        conn.execute("DELETE FROM citation_cards WHERE card_id = ?", (card_id,))
        deleted_count += 1

    conn.commit()
    conn.close()

    print(f"Done: {deleted_count} merged cards deleted, {split_count} single refs created, {kept_count} kept as-is")


if __name__ == "__main__":
    main()
