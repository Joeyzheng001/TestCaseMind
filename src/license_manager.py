"""
ThesisMind 许可证管理系统 — 5级授权体系。

安全边界:
- 客户端只应配置 Ed25519 公钥用于验签。
- 许可证签发必须在受控的管理员/销售环境中配置私钥。
- 旧版 HMAC 仅在显式配置 THESISMIND_LICENSE_KEY 时用于兼容验证，
  不再包含源码默认密钥，避免分发包自签许可证。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4
import httpx

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.api_registry import MENU_FEATURE_MAP, is_public_api, resolve_api_menu



def _compute_days_left(expires_at: str) -> int:
    """Compute days left from ISO datetime string."""
    if not expires_at:
        return 0
    try:
        expiry = datetime.fromisoformat(expires_at)
        return max(0, (expiry - datetime.now()).days)
    except Exception:
        return 0

class LicenseManager:
    """许可证管理器"""

    LICENSE_PREFIX = "TM"
    LICENSE_FILE = ".license"
    LICENSE_HISTORY_FILE = ".license_history.json"
    LICENSE_PUBLIC_KEY_ENV = "THESISMIND_LICENSE_PUBLIC_KEY"
    LICENSE_PRIVATE_KEY_ENV = "THESISMIND_LICENSE_PRIVATE_KEY"
    LEGACY_HMAC_KEY_ENV = "THESISMIND_LICENSE_KEY"
    CLOUD_URL_ENV = "THESISMIND_CLOUD_URL"
    CLOUD_CACHE_FILE = ".license_cloud_cache"
    CACHE_TTL_HOURS = 24

    # 5级授权体系
    LICENSE_TYPES: Dict[str, Dict[str, Any]] = {
        "free": {
            "days": 3,
            "label": "免费版",
            "features": [],  # 试用到期后全部锁定
            "description": "3天基础工作流试用",
        },
        "basic": {
            "days": 365,
            "label": "基础版",
            "features": ["workflow"],  # 01-07 基础工作流
            "description": "基础工作流(01-07)，1年有效",
        },
        "pro": {
            "days": 730,
            "label": "畅想版",
            "features": ["workflow", "advanced"],  # 01-08 含增值服务
            "description": "基础+增值服务(01-08)，2年有效",
        },
        "vip": {
            "days": 730,
            "label": "VIP版",
            "features": ["all"],  # 全部功能
            "description": "全部功能(01-09)，2年有效",
        },
        "admin": {
            "days": 3650,
            "label": "管理员版",
            "features": ["all", "admin"],  # 全部功能 + 系统管理权限
            "description": "全部功能+系统管理，10年有效",
        },
    }

    # 菜单 → 所需 feature 映射。实际注册表在 api_registry.py 中维护。
    MENU_FEATURE_MAP: Dict[str, Optional[str]] = MENU_FEATURE_MAP

    def __init__(self, secret_key: str = None):
        self.legacy_secret_key = secret_key or os.getenv(self.LEGACY_HMAC_KEY_ENV)
        self.cloud_url = (os.getenv(self.CLOUD_URL_ENV) or "https://api.thesismind.com").rstrip("/")
        self.public_key = self._load_public_key_from_env()
        # Private key loading kept for admin/generate use until fully migrated
        self.private_key = self._load_private_key_from_env()
        if self.public_key is None and self.private_key is not None:
            self.public_key = self.private_key.public_key()
        self.config_dir = self._resolve_config_dir()
        self.license_file = self.config_dir / self.LICENSE_FILE
        self._cache_file = self.config_dir / self.CLOUD_CACHE_FILE

    @staticmethod
    def _resolve_config_dir() -> Path:
        configured = os.getenv("THESISMIND_CONFIG_DIR")
        candidates = [Path(configured).expanduser()] if configured else []
        home = Path.home() / ".thesismind"
        local = Path(__file__).resolve().parent.parent / ".thesismind"
        candidates.extend([home, local])
        for candidate in candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
            except OSError:
                continue
        raise PermissionError("无可写的 ThesisMind 配置目录")

    # ── encoding ──────────────────────────────────────────────

    @staticmethod
    def _b32encode(data: str) -> str:
        return base64.b32encode(data.encode()).decode().rstrip("=")

    @staticmethod
    def _b32decode(encoded: str) -> str:
        padding = (8 - len(encoded) % 8) % 8
        return base64.b32decode(encoded + "=" * padding).decode()

    @staticmethod
    def _b64url_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _b64url_decode(encoded: str) -> bytes:
        padding = (4 - len(encoded) % 4) % 4
        return base64.urlsafe_b64decode(encoded + "=" * padding)

    @staticmethod
    def _decode_key_material(value: str) -> bytes:
        value = (value or "").strip()
        if not value:
            return b""
        value = value.replace("\\n", "\n")
        if "BEGIN" in value:
            return value.encode()
        return LicenseManager._b64url_decode(value)

    @classmethod
    def _load_private_key(cls, value: str) -> Ed25519PrivateKey:
        material = cls._decode_key_material(value)
        if not material:
            raise ValueError("许可证签发私钥为空")
        if material.startswith(b"-----BEGIN"):
            key = serialization.load_pem_private_key(material, password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("许可证签发私钥必须是 Ed25519 私钥")
            return key
        if len(material) != 32:
            raise ValueError("许可证签发私钥必须是 PEM 或 base64url 编码的 32 字节 Ed25519 私钥")
        return Ed25519PrivateKey.from_private_bytes(material)

    @classmethod
    def _load_public_key(cls, value: str) -> Ed25519PublicKey:
        material = cls._decode_key_material(value)
        if not material:
            raise ValueError("许可证验签公钥为空")
        if material.startswith(b"-----BEGIN"):
            key = serialization.load_pem_public_key(material)
            if not isinstance(key, Ed25519PublicKey):
                raise ValueError("许可证验签公钥必须是 Ed25519 公钥")
            return key
        if len(material) != 32:
            raise ValueError("许可证验签公钥必须是 PEM 或 base64url 编码的 32 字节 Ed25519 公钥")
        return Ed25519PublicKey.from_public_bytes(material)

    def _load_private_key_from_env(self) -> Optional[Ed25519PrivateKey]:
        value = os.getenv(self.LICENSE_PRIVATE_KEY_ENV)
        if not value:
            return None
        return self._load_private_key(value)

    def _load_public_key_from_env(self) -> Optional[Ed25519PublicKey]:
        value = os.getenv(self.LICENSE_PUBLIC_KEY_ENV)
        if not value:
            return None
        return self._load_public_key(value)

    def _sign_payload(self, payload: str) -> str:
        if self.private_key is None:
            raise RuntimeError(
                f"许可证签发私钥未配置，请仅在授权签发环境设置 {self.LICENSE_PRIVATE_KEY_ENV}"
            )
        signature = self.private_key.sign(payload.encode())
        return "ed25519:" + self._b64url_encode(signature)

    def _verify_signature(self, payload: str, provided_sig: str) -> Tuple[bool, str]:
        if provided_sig.startswith("ed25519:"):
            if self.public_key is None:
                return False, f"许可证验签公钥未配置，请设置 {self.LICENSE_PUBLIC_KEY_ENV}"
            try:
                signature = self._b64url_decode(provided_sig.split(":", 1)[1])
                self.public_key.verify(signature, payload.encode())
                return True, ""
            except (InvalidSignature, ValueError):
                return False, "许可证签名无效"

        # Legacy HMAC compatibility. There is deliberately no source-code default key.
        if self.legacy_secret_key:
            expected_sig = hmac.new(
                self.legacy_secret_key.encode(), payload.encode(), hashlib.sha256
            ).hexdigest()[:16]
            if hmac.compare_digest(provided_sig, expected_sig):
                return True, ""
            return False, "许可证签名无效"

        return False, "不支持的许可证签名算法，或未配置旧版 HMAC 兼容密钥"

    # ── license code generation ───────────────────────────────

    def generate_license(
        self,
        license_type: str = "basic",
        user_email: str = "",
        custom_id: str = "",
        machine_id: str = "",
    ) -> str:
        if license_type not in self.LICENSE_TYPES:
            raise ValueError(f"无效的许可证类型: {license_type}")

        cfg = self.LICENSE_TYPES[license_type]
        issued_at = datetime.now()
        info: Dict[str, Any] = {
            "alg": "ed25519",
            "type": license_type,
            "user_id": str(uuid4()),
            "user_email": user_email,
            "custom_id": custom_id or str(uuid4()),
            "issued_at": issued_at.isoformat(),
            "expires_at": (issued_at + timedelta(days=cfg["days"])).isoformat(),
            "features": cfg["features"],
        }
        if machine_id:
            info["machine_id"] = str(machine_id)

        payload = json.dumps(info, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        sig = self._sign_payload(payload)

        encoded = self._b32encode(f"{payload}|{sig}")
        parts = [encoded[i : i + 8] for i in range(0, len(encoded), 8)]
        code = f"{self.LICENSE_PREFIX}-" + "-".join(parts)

        # Record generation to history
        self.save_license_history({
            "action": "generate",
            "license_type": license_type,
            "user_email": user_email,
            "code_preview": code[:24] + "..." if len(code) > 24 else code,
            "generated_at": info["issued_at"],
            "expires_at": info["expires_at"],
        })

        return code

    # ── validation ────────────────────────────────────────────

    def validate_license(self, license_code: str) -> Tuple[bool, Dict]:
        try:
            if not license_code.startswith(f"{self.LICENSE_PREFIX}-"):
                return False, {"error": "许可证格式无效"}

            encoded = "".join(license_code[len(self.LICENSE_PREFIX) + 1 :].split("-"))
            data = self._b32decode(encoded)

            if "|" not in data:
                return False, {"error": "许可证数据格式无效"}

            payload, provided_sig = data.rsplit("|", 1)
            info = json.loads(payload)

            if info["type"] not in self.LICENSE_TYPES:
                return False, {"error": "无效的许可证类型"}

            signature_ok, signature_error = self._verify_signature(payload, provided_sig)
            if not signature_ok:
                return False, {"error": signature_error}

            expiry = datetime.fromisoformat(info["expires_at"])
            if datetime.now() > expiry:
                return False, {
                    "error": "许可证已过期",
                    "expired_at": info["expires_at"],
                }

            bound_machine = info.get("machine_id")
            if bound_machine and str(bound_machine) != self._machine_id():
                return False, {"error": "许可证绑定机器不匹配"}

            return True, info
        except Exception as e:
            return False, {"error": f"许可证验证失败: {e}"}

    # ── persistence ───────────────────────────────────────────

    def save_license(self, license_code: str, validate: bool = True) -> Tuple[bool, str]:
        if validate:
            ok, info = self.validate_license(license_code)
            if not ok:
                return False, f"验证失败: {info.get('error')}"

        try:
            record = {
                "code": license_code,
                "saved_at": datetime.now().isoformat(),
                "machine_id": self._machine_id(),
            }
            self.license_file.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            # Record to history
            self.save_license_history({
                "action": "activate",
                "code_preview": license_code[:24] + "..." if len(license_code) > 24 else license_code,
                "saved_at": record["saved_at"],
                "machine_id": record["machine_id"],
            })
            return True, f"许可证已保存至 {self.license_file}"
        except Exception as e:
            return False, f"保存失败: {e}"

    def load_license(self) -> Tuple[bool, Optional[str], Dict]:
        if not self.license_file.exists():
            return False, None, {"error": "未找到许可证"}

        try:
            record = json.loads(self.license_file.read_text())
            code = record.get("code")
            record_machine_id = str(record.get("machine_id", ""))
            if record_machine_id and record_machine_id != self._machine_id():
                return False, code, {"error": "本地许可证文件绑定机器不匹配"}
            ok, info = self.validate_license(code)
            if not ok:
                return False, code, info
            return True, code, info
        except Exception as e:
            return False, None, {"error": f"加载许可证失败: {e}"}

    def remove_license(self) -> Tuple[bool, str]:
        try:
            if self.license_file.exists():
                self.license_file.unlink()
            return True, "许可证已移除"
        except Exception as e:
            return False, f"移除失败: {e}"

    # ── license history ────────────────────────────────────────

    def _history_path(self) -> Path:
        return self.config_dir / self.LICENSE_HISTORY_FILE

    def save_license_history(self, record: Dict[str, Any]) -> None:
        history = self.load_license_history()
        history.append(record)
        try:
            self._history_path().write_text(
                json.dumps(history, ensure_ascii=False, indent=2)
            )
        except Exception:
            pass

    def load_license_history(self) -> list:
        p = self._history_path()
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text())
        except Exception:
            return []


    # ── cloud client ─────────────────────────────────────────

    def validate_with_cloud(self, license_code: str, email: str = "") -> Dict[str, Any]:
        """POST /v1/license/validate → verify signature → cache → return status."""
        try:
            resp = httpx.post(
                f"{self.cloud_url}/v1/license/validate",
                json={
                    "license_code": license_code,
                    "device_id": self._machine_id(),
                    "client_version": "1.0.0",
                    "email": email,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"Cloud returned {resp.status_code}"}
            data = resp.json()
            # Verify signature
            sig = data.get("signature", "")
            if sig and self.public_key:
                payload = "|".join([
                    data.get("status", ""),
                    data.get("tier", ""),
                    ",".join(data.get("features", [])),
                    data.get("expires_at", ""),
                    str(data.get("device_limit", 0)),
                    str(data.get("device_count", 0)),
                    str(data.get("revoked", False)),
                    data.get("user_email", ""),
                    data.get("signed_at", ""),
                ])
                ok, _ = self._verify_signature(payload, sig)
                if not ok:
                    return {"status": "error", "message": "Cloud signature verification failed"}
            # Cache the response
            self._cache_license_state(data)
            return data
        except Exception as e:
            return {"status": "error", "message": f"Cloud unreachable: {e}"}

    def start_trial_cloud(self, email: str) -> Dict[str, Any]:
        """POST /v1/trial/start → verify → cache → return status."""
        try:
            resp = httpx.post(
                f"{self.cloud_url}/v1/trial/start",
                json={"email": email, "device_id": self._machine_id()},
                timeout=10,
            )
            if resp.status_code == 409:
                data = resp.json()
                return {"status": data.get("status", "already_used"), "trial_days_left": 0}
            if resp.status_code != 200:
                return {"status": "error", "message": f"Cloud returned {resp.status_code}"}
            data = resp.json()
            sig = data.get("signature", "")
            if sig and self.public_key:
                features_str = ",".join(data.get("features", []))
                payload = f"{data.get('status','')}|{data.get('trial_days_left',0)}|{data.get('trial_end','')}|{features_str}"
                ok, _ = self._verify_signature(payload, sig)
                if ok:
                    self._cache_trial_state(data)
            return data
        except Exception as e:
            return {"status": "error", "message": f"Cloud unreachable: {e}"}

    def get_effective_status(self) -> Dict[str, Any]:
        """Priority: cloud-validated cache → cloud API → local fallback."""
        # 1. Try loaded license with cloud validation
        found, code, info = self.load_license()
        if found and code:
            # Check cache first
            cached = self._load_cached_license()
            if cached and self._is_cache_valid(cached):
                return cached
            # Try cloud
            cloud_result = self.validate_with_cloud(code)
            if cloud_result.get("status") == "valid":
                return self._build_status(cloud_result, code)
            # Cloud failed / invalid — fall back to local
            ok, full = self.validate_license(code)
            if ok:
                return self._build_status_local(full)

        # 2. Try trial
        trial_ok, trial_info = TrialLicense.check()
        if trial_ok:
            return {
                "status": "trial", "tier": "free", "tier_label": "免费版(试用中)",
                "days_left": trial_info.get("days_left", 0),
                "features": ["workflow"],
                "trial_active": True, "trial_days_left": trial_info.get("days_left", 0),
            }

        # 3. Nothing
        return {
            "status": "no_license", "tier": "free", "tier_label": "免费版(未激活)",
            "days_left": 0, "features": [], "trial_active": False, "trial_days_left": 0,
            "message": "请先开始免费试用或激活许可证",
        }

    def _build_status(self, cloud_data: dict, code: str) -> dict:
        """Convert cloud validation response to status dict."""
        return {
            "status": "active",
            "tier": cloud_data.get("tier", "free"),
            "tier_label": cloud_data.get("tier_label", ""),
            "user_email": cloud_data.get("user_email", ""),
            "expires_at": cloud_data.get("expires_at", ""),
            "days_left": _compute_days_left(cloud_data.get("expires_at", "")),
            "features": cloud_data.get("features", []),
            "device_limit": cloud_data.get("device_limit", 1),
            "device_count": cloud_data.get("device_count", 0),
            "trial_active": False,
            "trial_days_left": 0,
            "cloud_validated": True,
        }

    def _build_status_local(self, info: dict) -> dict:
        expiry = datetime.fromisoformat(info["expires_at"])
        days_left = max(0, (expiry - datetime.now()).days)
        tier = info["type"]
        return {
            "status": "active",
            "tier": tier,
            "tier_label": self.LICENSE_TYPES.get(tier, {}).get("label", tier),
            "user_email": info.get("user_email", ""),
            "issued_at": info.get("issued_at", ""),
            "expires_at": info["expires_at"],
            "days_left": days_left,
            "features": info.get("features", []),
            "trial_active": False,
            "trial_days_left": 0,
            "cloud_validated": False,
        }

    # ── cloud cache ──────────────────────────────────────────

    def _cache_license_state(self, data: dict) -> None:
        try:
            data["cached_at"] = datetime.now().isoformat()
            self._cache_file.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    def _cache_trial_state(self, data: dict) -> None:
        # Trial state is handled via TrialLicense class
        pass

    def _load_cached_license(self) -> Optional[Dict[str, Any]]:
        if not self._cache_file.exists():
            return None
        try:
            return json.loads(self._cache_file.read_text())
        except Exception:
            return None

    def _is_cache_valid(self, cached: dict) -> bool:
        cached_at_str = cached.get("cached_at", "")
        if not cached_at_str:
            return False
        try:
            cached_at = datetime.fromisoformat(cached_at_str)
            if datetime.now() - cached_at > timedelta(hours=self.CACHE_TTL_HOURS):
                return False
        except Exception:
            return False
        # Verify signature still valid
        sig = cached.get("signature", "")
        if sig and self.public_key:
            payload = "|".join([
                cached.get("status", ""), cached.get("tier", ""),
                ",".join(cached.get("features", [])), cached.get("expires_at", ""),
                str(cached.get("device_limit", 0)), str(cached.get("device_count", 0)),
                str(cached.get("revoked", False)), cached.get("user_email", ""),
                cached.get("signed_at", ""),
            ])
            ok, _ = self._verify_signature(payload, sig)
            return ok
        # No signature → accept cache (backward compat)
        return True

    # ── high-level status ─────────────────────────────────────

    def get_license_status(self) -> Dict[str, Any]:
        """返回前端可用的许可证状态摘要。"""
        trial_ok, trial_info = TrialLicense.check()

        found, code, info = self.load_license()

        if found and code:
            ok, full = self.validate_license(code)
            if ok:
                expiry = datetime.fromisoformat(full["expires_at"])
                days_left = max(0, (expiry - datetime.now()).days)
                tier = full["type"]
                features = full.get("features", [])
                return {
                    "status": "active",
                    "tier": tier,
                    "tier_label": self.LICENSE_TYPES.get(tier, {}).get("label", tier),
                    "user_email": full.get("user_email", ""),
                    "issued_at": full.get("issued_at", ""),
                    "expires_at": full["expires_at"],
                    "days_left": days_left,
                    "features": features,
                    "trial_active": trial_ok,
                    "trial_days_left": trial_info.get("days_left", 0) if trial_ok else 0,
                }

        # 没有有效许可证 → 检查试用
        if trial_ok:
            return {
                "status": "trial",
                "tier": "free",
                "tier_label": "免费版(试用中)",
                "days_left": trial_info.get("days_left", 0),
                "features": ["workflow"],  # 试用期间仅基础工作流 01-07
                "trial_active": True,
                "trial_days_left": trial_info.get("days_left", 0),
            }

        # 试用到期
        trial_expired = TrialLicense.is_expired()
        if trial_expired:
            return {
                "status": "expired",
                "tier": "free",
                "tier_label": "免费版(已到期)",
                "days_left": 0,
                "features": [],
                "trial_active": False,
                "trial_days_left": 0,
                "message": "试用已到期，请激活许可证继续使用",
            }

        # 没有任何记录
        return {
            "status": "no_license",
            "tier": "free",
            "tier_label": "免费版(未激活)",
            "days_left": 0,
            "features": [],
            "trial_active": False,
            "trial_days_left": 0,
            "message": "请先开始免费试用或激活许可证",
        }

    def can_access_menu(self, menu_id: str) -> Tuple[bool, str]:
        """
        检查当前许可证是否可以访问指定菜单。

        Args:
            menu_id: 菜单标识 (如 "proposal", "blind_review")

        Returns:
            (allowed, reason) 元组
        """
        status = self.get_license_status()

        if status["status"] == "expired":
            return False, "试用已到期，请激活许可证"

        required = self.MENU_FEATURE_MAP.get(menu_id)
        if required is None:
            return True, ""  # 无限制菜单

        features = status.get("features", [])
        if self._features_allow(features, required):
            return True, ""

        tier_label = status.get("tier_label", "当前版本")
        return False, f"{tier_label}不支持此功能，请升级许可证"

    def check_feature(self, feature: str) -> Tuple[bool, str]:
        """检查当前许可证是否允许使用指定功能，保留给 Agent/脚本调用。"""
        status = self.get_license_status()
        if status["status"] == "expired":
            return False, "试用已到期，请激活许可证"

        features = status.get("features", [])
        aliases = {
            "basic": "workflow",
            "business": "all",
            "pro": "advanced",
        }
        required = aliases.get(feature, feature)

        if self._features_allow(features, required):
            return True, ""

        return False, f"当前许可证不支持功能: {feature}"

    def can_access_api(self, api_path: str, method: str = "GET") -> Tuple[bool, str]:
        """检查是否可以访问指定 API 端点。"""
        method = (method or "GET").upper()

        if is_public_api(api_path, method):
            return True, ""

        menu_id = resolve_api_menu(api_path, method)
        if menu_id is None:
            return False, "未授权的 API 端点"

        return self.can_access_menu(menu_id)

    @staticmethod
    def _features_allow(features: list, required: str) -> bool:
        """判断功能集合是否满足指定权限要求，admin 不被 all 隐式包含。"""
        feature_set = set(features or [])

        if required is None:
            return True
        if required == "admin":
            return "admin" in feature_set
        if "admin" in feature_set:
            return True
        if "all" in feature_set:
            return required in {"workflow", "advanced", "vip", "all"}

        if required == "workflow":
            return "workflow" in feature_set
        if required == "advanced":
            return "advanced" in feature_set
        if required == "vip":
            return "vip" in feature_set

        return required in feature_set

    # ── helpers ───────────────────────────────────────────────

    @staticmethod
    def _machine_id() -> str:
        import uuid
        return str(uuid.getnode())


class TrialLicense:
    """免费试用管理 — 3天基础工作流试用，无需激活码"""

    TRIAL_DAYS = 3

    @classmethod
    def _file(cls) -> Path:
        return LicenseManager._resolve_config_dir() / ".trial"

    @classmethod
    def start(cls) -> Tuple[bool, str]:
        """开始免费试用（如果已有试用记录则返回剩余天数）。"""
        existing_ok, info = cls.check()
        if existing_ok:
            return True, f"试用已激活，剩余 {info['days_left']} 天"
        if info.get("expired"):
            return False, "免费试用已到期，请激活许可证继续使用"
        try:
            data = {
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=cls.TRIAL_DAYS)).isoformat(),
                "machine_id": LicenseManager._machine_id(),
            }
            f = cls._file()
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data, indent=2))
            return True, f"免费试用已激活，{cls.TRIAL_DAYS} 天基础工作流使用"
        except Exception as e:
            return False, f"激活试用失败: {e}"

    @classmethod
    def check(cls) -> Tuple[bool, Dict]:
        """检查试用是否有效。"""
        f = cls._file()
        if not f.exists():
            return False, {"error": "未找到试用记录"}
        try:
            data = json.loads(f.read_text())
            machine_id = str(data.get("machine_id", ""))
            if machine_id and machine_id != LicenseManager._machine_id():
                return False, {"error": "试用记录绑定机器不匹配"}
            expiry = datetime.fromisoformat(data["expires_at"])
            if datetime.now() > expiry:
                return False, {"error": "试用已到期", "expired": True}
            days_left = max(0, (expiry - datetime.now()).days)
            return True, {
                "days_left": days_left,
                "expires_at": data["expires_at"],
                "created_at": data.get("created_at", ""),
            }
        except Exception as e:
            return False, {"error": f"试用检查失败: {e}"}

    @classmethod
    def is_expired(cls) -> bool:
        """试用是否已到期（且存在试用记录）。"""
        f = cls._file()
        if not f.exists():
            return False
        try:
            data = json.loads(f.read_text())
            return datetime.now() > datetime.fromisoformat(data["expires_at"])
        except Exception:
            return False

    @classmethod
    def remaining_days(cls) -> int:
        ok, info = cls.check()
        return info.get("days_left", 0) if ok else 0

    @classmethod
    def create_trial(cls) -> Tuple[bool, str]:
        """兼容旧 CLI/Agent 调用。"""
        return cls.start()

    @classmethod
    def is_trial_valid(cls) -> Tuple[bool, Dict]:
        """兼容旧 CLI/Agent 调用。"""
        return cls.check()
