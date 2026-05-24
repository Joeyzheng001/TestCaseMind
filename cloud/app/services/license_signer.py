"""License validation service — query DB, assemble response, sign."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.config import settings
from cloud.app.core.security import sign_payload
from cloud.app.models.activation import Activation
from cloud.app.models.audit import AuditLog
from cloud.app.models.license import License
from cloud.app.models.user import User


LICENSE_TIERS: dict[str, dict] = {
    "free": {"label": "免费版", "features": [], "days": 3},
    "basic": {"label": "基础版", "features": ["workflow"], "days": 365},
    "pro": {"label": "畅想版", "features": ["workflow", "advanced"], "days": 730},
    "vip": {"label": "VIP版", "features": ["all"], "days": 730},
    "admin": {"label": "管理员版", "features": ["all", "admin"], "days": 3650},
}

TIER_DEVICE_LIMITS = {
    "free": 1, "basic": 1, "pro": 2, "vip": 3, "admin": 999,
}


async def validate_license(
    db: AsyncSession,
    license_code: str,
    device_id: str,
    client_version: str = "",
    email: str = "",
    ip_address: str = "",
) -> dict:
    """Validate a license code and return signed response.

    Returns a dict formatted for LicenseValidateResponse.
    """
    now = datetime.now(timezone.utc)
    signature = ""

    # 1. Find license
    result = await db.execute(
        select(License).where(License.license_code == license_code)
    )
    lic = result.scalar_one_or_none()

    if lic is None:
        await _audit(db, "license_validate", "user", None, device_id, ip_address, "failure", "not_found")
        return {
            "status": "not_found", "tier": "free", "tier_label": "免费版",
            "features": [], "expires_at": "", "device_limit": 0, "device_count": 0,
            "revoked": False, "user_email": "", "signature": "", "signed_at": "",
        }

    # 2. Check revoked
    if lic.revoked:
        await _audit(db, "license_validate", "user", lic.user_id, device_id, ip_address, "denied", "revoked")
        return {
            "status": "revoked", "tier": lic.tier,
            "tier_label": LICENSE_TIERS.get(lic.tier, {}).get("label", lic.tier),
            "features": [], "expires_at": lic.expires_at.isoformat(),
            "device_limit": lic.device_limit, "device_count": 0,
            "revoked": True, "user_email": "", "signature": "", "signed_at": "",
        }

    # 3. Check expiry
    if lic.expires_at < now:
        await _audit(db, "license_validate", "user", lic.user_id, device_id, ip_address, "failure", "expired")
        return {
            "status": "expired", "tier": lic.tier,
            "tier_label": LICENSE_TIERS.get(lic.tier, {}).get("label", lic.tier),
            "features": [], "expires_at": lic.expires_at.isoformat(),
            "device_limit": lic.device_limit, "device_count": 0,
            "revoked": False, "user_email": "", "signature": "", "signed_at": "",
        }

    # 4. Track activation (upsert)
    existing_act = await db.execute(
        select(Activation).where(
            Activation.license_id == lic.id,
            Activation.device_id == device_id,
        )
    )
    act = existing_act.scalar_one_or_none()
    if act is None:
        # Count existing devices
        count_result = await db.execute(
            select(func.count()).where(
                Activation.license_id == lic.id,
                Activation.deactivated_at.is_(None),
            )
        )
        device_count = count_result.scalar() or 0

        if device_count >= lic.device_limit:
            await _audit(db, "license_validate", "user", lic.user_id, device_id, ip_address, "denied", "device_limit")
            return {
                "status": "device_limit", "tier": lic.tier,
                "tier_label": LICENSE_TIERS.get(lic.tier, {}).get("label", lic.tier),
                "features": [], "expires_at": lic.expires_at.isoformat(),
                "device_limit": lic.device_limit, "device_count": device_count,
                "revoked": False, "user_email": "", "signature": "", "signed_at": "",
            }

        act = Activation(
            license_id=lic.id,
            device_id=device_id,
            client_version=client_version,
            ip_address=ip_address,
        )
        db.add(act)
    else:
        act.last_seen_at = now

    # 5. Get user email
    user_result = await db.execute(select(User).where(User.id == lic.user_id))
    user = user_result.scalar_one_or_none()
    user_email = user.email if user else ""

    # 6. Get device count
    count_result = await db.execute(
        select(func.count()).where(
            Activation.license_id == lic.id,
            Activation.deactivated_at.is_(None),
        )
    )
    device_count = count_result.scalar() or 0

    # 7. Sign response
    signed_at = now.isoformat()
    payload = "|".join([
        "valid",
        lic.tier,
        ",".join(lic.features),
        lic.expires_at.isoformat(),
        str(lic.device_limit),
        str(device_count),
        str(False),
        user_email,
        signed_at,
    ])

    if settings.license_private_key:
        try:
            signature = sign_payload(payload, settings.license_private_key)
        except Exception:
            signature = ""

    await _audit(db, "license_validate", "user", lic.user_id, device_id, ip_address, "success", "")

    return {
        "status": "valid",
        "tier": lic.tier,
        "tier_label": LICENSE_TIERS.get(lic.tier, {}).get("label", lic.tier),
        "features": lic.features,
        "expires_at": lic.expires_at.isoformat(),
        "device_limit": lic.device_limit,
        "device_count": device_count,
        "revoked": False,
        "user_email": user_email,
        "signature": signature,
        "signed_at": signed_at,
    }


async def _audit(
    db: AsyncSession,
    action: str,
    actor_type: str,
    actor_id,
    device_id: str,
    ip_address: str,
    result: str,
    error_reason: str,
) -> None:
    """Write an audit log entry."""
    try:
        log = AuditLog(
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            device_id=device_id,
            ip_address=ip_address,
            result=result,
            error_reason=error_reason,
        )
        db.add(log)
    except Exception:
        pass
