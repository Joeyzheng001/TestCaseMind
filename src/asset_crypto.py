"""
资产加密模块 — Fernet 对称加密保护知识库资产。

仓库中存储 .enc 密文文件，运行时由许可证派生密钥解密到临时目录。
没有有效许可证的用户即使 clone 了仓库也无法使用知识库。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ENC_DIR = PROJECT_ROOT / "assets_enc"


def _derive_key(secret: str, salt: bytes) -> bytes:
    """从密码和盐值派生 Fernet 密钥。"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    raw = kdf.derive(secret.encode())
    return base64.urlsafe_b64encode(raw)


def _get_asset_secret() -> str:
    """获取资产解密密钥，优先环境变量，回退到许可证绑定。"""
    env_key = os.getenv("THESISMIND_ASSET_KEY")
    if env_key:
        return env_key
    # 使用许可证机器 ID 作为回退密钥
    return f"thesismind_asset_{uuid.getnode()}"


class AssetStore:
    """管理加密资产的解密与访问。"""

    def __init__(self):
        self._temp_dir: Optional[Path] = None
        self._fernet: Optional[Fernet] = None
        self._decrypted: Dict[str, Path] = {}
        self.assets_root: Optional[Path] = None  # 解密后的资产根目录

    def setup(self, secret: str = None) -> Path:
        """
        解密所有资产到临时目录，返回资产根路径。

        Args:
            secret: 解密密钥。为 None 时从环境变量/机器 ID 派生。
        """
        if self._temp_dir:
            return self.assets_root

        secret = secret or _get_asset_secret()
        self._temp_dir = Path(tempfile.mkdtemp(prefix="thesismind_assets_"))

        manifest_path = ASSETS_ENC_DIR / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"加密资产清单不存在: {manifest_path}\n"
                "请先运行 python3 encrypt_assets.py 生成加密资产包"
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        salt = base64.urlsafe_b64decode(manifest["salt"])
        key = _derive_key(secret, salt)
        self._fernet = Fernet(key)

        total = len(manifest["files"])
        for i, entry in enumerate(manifest["files"]):
            rel_path = entry["path"]
            expected_hash = entry["sha256"]
            enc_path = ASSETS_ENC_DIR / (rel_path + ".enc")

            if not enc_path.exists():
                raise FileNotFoundError(f"加密文件缺失: {rel_path}")

            encrypted_data = enc_path.read_bytes()
            try:
                decrypted_data = self._fernet.decrypt(encrypted_data)
            except Exception:
                raise RuntimeError(
                    f"解密失败: {rel_path}\n密钥不匹配或文件已损坏。"
                    "请确认 THESISMIND_ASSET_KEY 环境变量或许可证状态。"
                )

            # 完整性校验
            actual_hash = hashlib.sha256(decrypted_data).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(f"文件完整性校验失败: {rel_path}")

            # 写入临时目录
            dest = self._temp_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(decrypted_data)
            self._decrypted[rel_path] = dest

        self.assets_root = self._temp_dir
        return self.assets_root

    def get_path(self, *parts: str) -> Path:
        """获取解密后资产的路径。如 store.get_path("knowledge_base", "references")"""
        if not self.assets_root:
            raise RuntimeError("AssetStore 尚未初始化，请先调用 setup()")
        return self.assets_root.joinpath(*parts)

    def cleanup(self):
        """清理临时解密目录。"""
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None
        self._decrypted.clear()
        self.assets_root = None

    def __del__(self):
        self.cleanup()


# 全局单例
store = AssetStore()
