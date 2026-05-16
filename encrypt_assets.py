#!/usr/bin/env python3
"""
资产加密打包工具 — 将 knowledge_base/ 和 cards/ 加密为 assets_enc/。

运行一次后，将 assets_enc/ 提交到 Git，
原始明文目录加入 .gitignore。

使用方法:
    python3 encrypt_assets.py                    # 使用机器 ID 自动派生密钥
    python3 encrypt_assets.py --secret mykey     # 使用自定义密钥
    python3 encrypt_assets.py --secret mykey --output ./dist  # 指定输出目录
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.asset_crypto import _derive_key, PROJECT_ROOT, ASSETS_ENC_DIR


# 需要加密的资产目录和文件
ASSET_SOURCES = [
    "knowledge_base/references",
    "knowledge_base/outlines",
    "knowledge_base/templates",
    "knowledge_base/best_practices.json",
    "knowledge_base/catalog.json",
    "knowledge_base/papers.sqlite3",
    "knowledge_base/cards.sqlite3",
    # vector_store.sqlite3 是派生索引，可从 references 重建，不纳入分发
    "cards/methods",
    "cards/risks",
    "cards/cards.jsonl",
    "cards/risks.jsonl",
]

# 跳过的文件模式
SKIP_PATTERNS = [
    ".DS_Store",
    "__pycache__",
    "*.pyc",
    ".gitkeep",
    "*.tmp",
    "*-wal",
    "*-shm",
]


def should_skip(path: Path) -> bool:
    name = path.name
    for pattern in SKIP_PATTERNS:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern:
            return True
    return False


def collect_files(sources: list[str]) -> list[Path]:
    """收集所有需要加密的文件。"""
    files = []
    for src in sources:
        full = PROJECT_ROOT / src
        if not full.exists():
            print(f"  [跳过] 不存在: {src}")
            continue
        if full.is_file():
            if not should_skip(full):
                files.append(full)
        else:
            for f in full.rglob("*"):
                if f.is_file() and not should_skip(f):
                    files.append(f)
    return sorted(files)


def encrypt_assets(secret: str, output_dir: Path):
    """加密所有资产并生成 manifest。"""
    from cryptography.fernet import Fernet

    output_dir.mkdir(parents=True, exist_ok=True)

    salt = os.urandom(16)
    key = _derive_key(secret, salt)
    fernet = Fernet(key)

    files = collect_files(ASSET_SOURCES)
    if not files:
        print("错误: 没有找到任何资产文件")
        sys.exit(1)

    manifest = {
        "version": 1,
        "salt": base64.urlsafe_b64encode(salt).decode(),
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "total_size": 0,
        "files": [],
    }

    total_size = 0
    for i, file_path in enumerate(files):
        rel = file_path.relative_to(PROJECT_ROOT)
        data = file_path.read_bytes()

        encrypted = fernet.encrypt(data)
        sha = hashlib.sha256(data).hexdigest()

        dest = output_dir / (str(rel) + ".enc")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(encrypted)

        manifest["files"].append({
            "path": str(rel),
            "sha256": sha,
            "size": len(data),
        })
        total_size += len(data)

        if (i + 1) % 10 == 0 or i == len(files) - 1:
            print(f"  [{i+1}/{len(files)}] {rel}")

    manifest["total_size"] = total_size
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

    print(f"\n✓ 加密完成: {len(files)} 个文件, {total_size / 1024 / 1024:.1f} MB")
    print(f"  输出目录: {output_dir}")
    print(f"  清单文件: {manifest_path}")
    print(f"\n  密钥盐值: {manifest['salt']}")
    print(f"  ⚠ 请妥善保管密钥，丢失后无法解密资产。")
    print(f"  提交 assets_enc/ 到 Git，将原始明文目录加入 .gitignore。")


def main():
    parser = argparse.ArgumentParser(description="ThesisMind 资产加密打包工具")
    parser.add_argument(
        "--secret",
        help="加密密钥（留空则使用机器 ID 自动派生）",
    )
    parser.add_argument(
        "--output",
        default=str(ASSETS_ENC_DIR),
        help=f"输出目录（默认: {ASSETS_ENC_DIR}）",
    )
    args = parser.parse_args()

    secret = args.secret or f"thesismind_asset_{__import__('uuid').getnode()}"
    output = Path(args.output)

    print(f"ThesisMind 资产加密打包")
    print(f"  输出目录: {output}")
    print(f"  密钥: {'自定义' if args.secret else '机器 ID 派生'}")
    print()

    encrypt_assets(secret, output)


if __name__ == "__main__":
    main()
