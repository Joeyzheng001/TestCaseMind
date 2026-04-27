#!/usr/bin/env python3
"""
memory_review.py - 长期记忆审核与管理

查看、筛选、删除低质量的记忆条目，手动添加高价值经验。
越用越准的前提是记忆质量高，这个工具帮助保持记忆的高质量。

用法:
    python memory_review.py              # 查看所有记忆
    python memory_review.py --clean      # 交互式清理低质量条目
    python memory_review.py --add        # 手动添加记忆条目
    python memory_review.py --export     # 导出记忆为可编辑的 YAML
    python memory_review.py --import f.yaml  # 从 YAML 导入（编辑后导入）
    python memory_review.py --stats      # 只看统计不交互
"""

import json
import sys
from pathlib import Path

WORKDIR  = Path(__file__).parent
MEM_DIR  = WORKDIR / "memory"
LT_FILE  = MEM_DIR / "long_term.json"

CATEGORIES = {
    "domain_patterns":  "领域模式（业务场景规律）",
    "quality_signals":  "质量信号（评审经验）",
    "testpoint_hints":  "测试点经验（具体测试场景）",
    "risk_patterns":    "风险模式（高风险场景）",
    "section_patterns": "章节过滤规律",
}


def load_lt() -> dict:
    if not LT_FILE.exists():
        return {k: ([] if k != "section_patterns" else {"skip": [], "keep": []})
                for k in CATEGORIES}
    return json.loads(LT_FILE.read_text(encoding="utf-8"))


def save_lt(lt: dict):
    MEM_DIR.mkdir(exist_ok=True)
    LT_FILE.write_text(json.dumps(lt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ 已保存到 {LT_FILE.relative_to(WORKDIR)}")


def show_all(lt: dict):
    """展示所有记忆条目。"""
    print("\n🧠 长期记忆内容")
    print("=" * 60)

    total = 0
    for key, label in CATEGORIES.items():
        val = lt.get(key, [])
        print(f"\n【{label}】")

        if isinstance(val, list):
            if not val:
                print("  （空）")
            for i, item in enumerate(val):
                print(f"  [{i+1:2d}] {item[:100]}")
            total += len(val)

        elif isinstance(val, dict):
            skip = val.get("skip", [])
            keep = val.get("keep", [])
            if skip:
                print(f"  跳过（{len(skip)}条）:")
                for i, s in enumerate(skip):
                    print(f"    [{i+1}] {s}")
            if keep:
                print(f"  保留（{len(keep)}条）:")
                for i, s in enumerate(keep):
                    print(f"    [{i+1}] {s}")
            total += len(skip) + len(keep)

    print(f"\n  总计: {total} 条记忆")


def interactive_clean(lt: dict) -> dict:
    """交互式清理：逐条审核，选择保留或删除。"""
    print("\n🧹 交互式清理（y=保留 n=删除 q=退出 s=跳过此类别）")
    print("─" * 60)

    for key, label in CATEGORIES.items():
        val = lt.get(key, [])
        if not isinstance(val, list) or not val:
            continue

        print(f"\n【{label}】共 {len(val)} 条")
        skip = input(f"  跳过此类别? (y/N): ").strip().lower()
        if skip == "y":
            continue

        keep_items = []
        for i, item in enumerate(val):
            print(f"\n  [{i+1}/{len(val)}] {item}")
            try:
                action = input("  保留? (Y/n/q): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                keep_items.extend(val[i:])
                break
            if action == "q":
                keep_items.extend(val[i:])
                break
            elif action == "n":
                print("  ✗ 已删除")
            else:
                keep_items.append(item)

        removed = len(val) - len(keep_items)
        lt[key] = keep_items
        if removed > 0:
            print(f"\n  删除了 {removed} 条，保留 {len(keep_items)} 条")

    return lt


def add_memory(lt: dict) -> dict:
    """手动添加记忆条目。"""
    print("\n➕ 手动添加记忆")
    print("─" * 60)
    print("类别:")
    list_keys = [(k, v) for k, v in CATEGORIES.items() if k != "section_patterns"]
    for i, (key, label) in enumerate(list_keys, 1):
        print(f"  {i}. {label}")

    try:
        choice = int(input("\n选择类别 (1-4): ").strip()) - 1
        if choice < 0 or choice >= len(list_keys):
            print("无效选择")
            return lt
        key, label = list_keys[choice]
    except (ValueError, EOFError):
        return lt

    print(f"\n添加到【{label}】，每行一条，空行结束:")
    items = []
    while True:
        try:
            line = input("  > ").strip()
        except EOFError:
            break
        if not line:
            break
        items.append(line)

    if items:
        lt.setdefault(key, [])
        existing = set(lt[key])
        new_items = [x for x in items if x not in existing]
        lt[key].extend(new_items)
        print(f"  ✓ 添加了 {len(new_items)} 条（跳过 {len(items) - len(new_items)} 条重复）")

    return lt


def export_yaml(lt: dict) -> Path:
    """导出为 YAML 格式，方便人工编辑。"""
    try:
        import yaml
    except ImportError:
        print("  需要 pyyaml: pip install pyyaml")
        # 降级为 JSON
        out = MEM_DIR / "long_term_export.json"
        out.write_text(json.dumps(lt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ 已导出到 {out}（JSON 格式，可直接编辑后用 --import 导入）")
        return out

    out = MEM_DIR / "long_term_export.yaml"
    with open(out, "w", encoding="utf-8") as f:
        yaml.dump(lt, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"  ✓ 已导出到 {out}")
    print(f"  编辑后运行: python memory_review.py --import {out}")
    return out


def import_file(path: str, lt: dict) -> dict:
    """从文件导入记忆。"""
    p = Path(path)
    if not p.exists():
        print(f"  ❌ 找不到文件: {path}")
        return lt

    try:
        if p.suffix == ".yaml" or p.suffix == ".yml":
            import yaml
            new_lt = yaml.safe_load(p.read_text(encoding="utf-8"))
        else:
            new_lt = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return lt

    # 合并，不覆盖
    for key, val in new_lt.items():
        if isinstance(val, list):
            existing = set(lt.get(key, []))
            new_items = [x for x in val if x not in existing]
            lt.setdefault(key, []).extend(new_items)
            print(f"  {key}: 导入 {len(new_items)} 条")
        elif isinstance(val, dict):
            for subkey in ("skip", "keep"):
                existing = set(lt.get(key, {}).get(subkey, []))
                new_items = [x for x in val.get(subkey, []) if x not in existing]
                lt.setdefault(key, {}).setdefault(subkey, []).extend(new_items)

    print(f"  ✓ 导入完成")
    return lt


def show_stats(lt: dict):
    """只显示统计信息。"""
    print("\n📊 记忆统计")
    print("─" * 40)
    total = 0
    for key, label in CATEGORIES.items():
        val = lt.get(key, [])
        if isinstance(val, list):
            count = len(val)
            bar   = "█" * min(count, 20)
            print(f"  {label[:18]:20} {bar} {count}")
            total += count
        elif isinstance(val, dict):
            skip = len(val.get("skip", []))
            keep = len(val.get("keep", []))
            print(f"  {label[:18]:20} skip={skip} keep={keep}")
            total += skip + keep
    print(f"\n  总计: {total} 条")

    # 短期记忆
    if MEM_DIR.exists():
        st_files = [f for f in MEM_DIR.glob("*.json") if f.name != "long_term.json"]
        if st_files:
            print(f"\n  短期记忆文件: {len(st_files)} 个")
            for f in sorted(st_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                mtime = f.stat().st_mtime
                import datetime
                dt = datetime.datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
                print(f"    {f.stem[:40]}  ({dt})")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="长期记忆审核与管理")
    parser.add_argument("--clean",   action="store_true", help="交互式清理低质量条目")
    parser.add_argument("--add",     action="store_true", help="手动添加记忆条目")
    parser.add_argument("--export",  action="store_true", help="导出记忆为可编辑文件")
    parser.add_argument("--import",  dest="import_file",  help="从文件导入记忆")
    parser.add_argument("--stats",   action="store_true", help="只显示统计")
    parser.add_argument("--clear-all", action="store_true", help="清空所有记忆（危险）")
    args = parser.parse_args()

    lt = load_lt()

    if args.stats:
        show_stats(lt)
        return

    if args.clear_all:
        confirm = input("⚠ 确认清空所有长期记忆？(输入 YES 确认): ").strip()
        if confirm == "YES":
            lt = {k: ([] if k != "section_patterns" else {"skip": [], "keep": []})
                  for k in CATEGORIES}
            save_lt(lt)
            print("  ✓ 已清空")
        else:
            print("  已取消")
        return

    if args.import_file:
        lt = import_file(args.import_file, lt)
        save_lt(lt)
        return

    if args.export:
        export_yaml(lt)
        return

    if args.add:
        lt = add_memory(lt)
        save_lt(lt)
        return

    if args.clean:
        show_stats(lt)
        lt = interactive_clean(lt)
        save_lt(lt)
        show_stats(lt)
        return

    # 默认：展示所有内容
    show_all(lt)
    show_stats(lt)
    print("\n常用命令:")
    print("  python memory_review.py --clean    # 清理低质量条目")
    print("  python memory_review.py --add      # 添加高价值经验")
    print("  python memory_review.py --export   # 导出编辑")
    print("  python memory_review.py --stats    # 快速查看统计")


if __name__ == "__main__":
    main()
