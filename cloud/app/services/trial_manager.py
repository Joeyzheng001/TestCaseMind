"""Trial management service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.config import settings
from cloud.app.core.security import sign_payload
from cloud.app.models.audit import AuditLog
from cloud.app.models.trial import Trial


async def start_trial(
    db: AsyncSession,
    email: str,
    device_id: str,
    ip_address: str = "",
) -> dict:
    """Start a trial. Returns TrialStartResponse-compatible dict."""
    now = datetime.now(timezone.utc)

    # Check existing trial
    existing = await db.execute(
        select(Trial).where(
            Trial.email == email,
            Trial.device_id == device_id,
        )
    )
    trial = existing.scalar_one_or_none()

    if trial:
        if trial.expires_at > now:
            days_left = max(0, (trial.expires_at - now).days)
            return _signed_trial_response("already_used", trial.expires_at, 0)
        else:
            # Expired — return already_used (one trial per email+device)
            return _signed_trial_response("already_used", trial.expires_at, 0)

    # Check if email already used with different device
    email_check = await db.execute(
        select(Trial).where(Trial.email == email)
    )
    email_trial = email_check.scalar_one_or_none()
    if email_trial:
        # Allow up to 2 devices per email
        device_count_result = await db.execute(
            select(Trial).where(Trial.email == email)
        )
        devices = device_count_result.scalars().all()
        if len(list(devices)) >= 2:
            await _audit(db, "trial_start", "user", None, device_id, ip_address, "denied", "email_already_used")
            return {"status": "already_used", "trial_days_left": 0, "trial_end": "", "features": [], "signature": ""}

    # Create new trial
    expires_at = now + timedelta(days=settings.trial_days)
    trial = Trial(
        email=email,
        device_id=device_id,
        expires_at=expires_at,
        status="active",
    )
    db.add(trial)
    await _audit(db, "trial_start", "user", None, device_id, ip_address, "success", "")

    return _signed_trial_response("started", expires_at, settings.trial_days)


def _signed_trial_response(status: str, expires_at: datetime, days_left: int) -> dict:
    """Build and sign trial response."""
    features = ["workflow"] if status == "started" else []
    trial_end = expires_at.isoformat() if status == "started" else ""

    signature = ""
    if settings.license_private_key:
        try:
            payload = f"{status}|{days_left}|{trial_end}|{','.join(features)}"
            signature = sign_payload(payload, settings.license_private_key)
        except Exception:
            pass

    return {
        "status": status,
        "trial_days_left": days_left,
        "trial_end": trial_end,
        "features": features,
        "signature": signature,
    }


async def _audit(db, action, actor_type, actor_id, device_id, ip_address, result, reason):
    try:
        db.add(AuditLog(
            action=action, actor_type=actor_type, actor_id=actor_id,
            device_id=device_id, ip_address=ip_address,
            result=result, error_reason=reason,
        ))
    except Exception:
        pass
