"""Admin service — license management, audit log queries."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.config import settings
from cloud.app.core.security import sign_payload
from cloud.app.models.activation import Activation
from cloud.app.models.audit import AuditLog
from cloud.app.models.license import License
from cloud.app.models.user import User

TIERS = {
    "basic": {"features": ["workflow"], "label": "基础版", "device_limit": 1, "duration_days": 365},
    "pro": {"features": ["workflow", "advanced"], "label": "畅想版", "device_limit": 2, "duration_days": 730},
    "vip": {"features": ["workflow", "advanced", "vip"], "label": "无忧版", "device_limit": 3, "duration_days": 730},
    "admin": {"features": ["workflow", "advanced", "vip", "admin"], "label": "管理版", "device_limit": 5, "duration_days": 3650},
}


def _generate_code() -> str:
    """Generate a TM-XXXX-XXXX-XXXX license code."""
    part = lambda: secrets.token_hex(2).upper()
    return f"TM-{part()}-{part()}-{part()}"


async def admin_list_licenses(db: AsyncSession, page: int = 1, page_size: int = 20) -> dict:
    """List all licenses with user info."""
    offset = (page - 1) * page_size
    count_result = await db.execute(select(func.count()).select_from(License))
    total = count_result.scalar()

    result = await db.execute(
        select(License, User.email, User.display_name)
        .join(User, License.user_id == User.id)
        .order_by(License.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    licenses = []
    for lic, email, display_name in rows:
        # Count activations
        act_result = await db.execute(
            select(func.count()).select_from(Activation)
            .where(Activation.license_id == lic.id, Activation.deactivated_at.is_(None))
        )
        device_count = act_result.scalar()

        licenses.append({
            "id": str(lic.id),
            "user_email": email,
            "display_name": display_name,
            "license_code": lic.license_code,
            "tier": lic.tier,
            "features": lic.features,
            "issued_at": lic.issued_at.isoformat() if lic.issued_at else "",
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else "",
            "device_limit": lic.device_limit,
            "device_count": device_count,
            "revoked": lic.revoked,
        })

    return {"total": total, "page": page, "page_size": page_size, "licenses": licenses}


async def admin_issue_license(db: AsyncSession, email: str, tier: str) -> dict:
    """Issue a new license for a user. Creates user if not exists."""
    if tier not in TIERS:
        return {"status": "error", "message": f"无效的等级: {tier}"}

    tier_info = TIERS[tier]
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(id=uuid.uuid4(), email=email, display_name=email.split("@")[0])
        db.add(user)
        await db.flush()

    license_code = _generate_code()
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(now.timestamp() + tier_info["duration_days"] * 86400, tz=timezone.utc)

    lic = License(
        id=uuid.uuid4(),
        user_id=user.id,
        license_code=license_code,
        tier=tier,
        features=tier_info["features"],
        issued_at=now,
        expires_at=expires_at,
        device_limit=tier_info["device_limit"],
    )
    db.add(lic)
    await db.flush()

    # Sign the license code for client verification
    sig = ""
    if settings.license_private_key:
        try:
            sig = sign_payload(license_code, settings.license_private_key)
        except Exception:
            pass

    return {
        "status": "ok",
        "license_code": license_code,
        "tier": tier,
        "tier_label": tier_info["label"],
        "features": tier_info["features"],
        "expires_at": expires_at.isoformat(),
        "user_email": email,
        "signature": sig,
    }


async def admin_revoke_license(db: AsyncSession, license_id: str) -> dict:
    """Revoke a license by ID."""
    try:
        lic_id = uuid.UUID(license_id)
    except ValueError:
        return {"status": "error", "message": "无效的许可证ID"}

    result = await db.execute(select(License).where(License.id == lic_id))
    lic = result.scalar_one_or_none()
    if not lic:
        return {"status": "error", "message": "许可证不存在"}

    lic.revoked = True
    lic.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "ok", "message": f"许可证 {lic.license_code} 已吊销"}


async def admin_unbind_device(db: AsyncSession, activation_id: str) -> dict:
    """Unbind a device (deactivate an activation)."""
    try:
        act_id = uuid.UUID(activation_id)
    except ValueError:
        return {"status": "error", "message": "无效的激活记录ID"}

    result = await db.execute(select(Activation).where(Activation.id == act_id))
    act = result.scalar_one_or_none()
    if not act:
        return {"status": "error", "message": "激活记录不存在"}

    act.deactivated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": "ok", "message": f"设备 {act.device_id} 已解绑"}


async def admin_list_activations(db: AsyncSession, license_id: str) -> dict:
    """List all device activations for a license."""
    try:
        lic_id = uuid.UUID(license_id)
    except ValueError:
        return {"status": "error", "message": "无效的许可证ID"}

    result = await db.execute(
        select(Activation).where(Activation.license_id == lic_id).order_by(Activation.activated_at.desc())
    )
    activations = result.scalars().all()

    return {
        "license_id": license_id,
        "activations": [
            {
                "id": str(a.id),
                "device_id": a.device_id,
                "client_version": a.client_version,
                "ip_address": str(a.ip_address) if a.ip_address else "",
                "activated_at": a.activated_at.isoformat() if a.activated_at else "",
                "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else "",
                "deactivated_at": a.deactivated_at.isoformat() if a.deactivated_at else None,
            }
            for a in activations
        ],
    }


async def admin_list_audit_logs(db: AsyncSession, page: int = 1, page_size: int = 50, action: str = "") -> dict:
    """List audit logs with optional action filter."""
    offset = (page - 1) * page_size

    base_query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)
    if action:
        base_query = base_query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    result = await db.execute(
        base_query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [
            {
                "id": str(l.id),
                "action": l.action,
                "actor_type": l.actor_type,
                "device_id": l.device_id,
                "result": l.result,
                "error_reason": l.error_reason,
                "created_at": l.created_at.isoformat() if l.created_at else "",
            }
            for l in logs
        ],
    }
