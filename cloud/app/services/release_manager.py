"""Release version service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.config import settings
from cloud.app.core.security import sign_payload
from cloud.app.models.release import ReleaseVersion


async def get_latest_release(db: AsyncSession) -> dict | None:
    """Return the latest active release with signed response."""
    result = await db.execute(
        select(ReleaseVersion)
        .where(ReleaseVersion.is_active == True)
        .order_by(ReleaseVersion.release_date.desc())
        .limit(1)
    )
    release = result.scalar_one_or_none()
    if not release:
        return None

    data = {
        "version": release.version,
        "release_date": release.release_date.isoformat(),
        "url": release.download_url,
        "sha256": release.sha256,
        "changelog": release.changelog or "",
        "min_client_version": release.min_client_version or "",
    }

    if settings.license_private_key:
        payload = f"{data['version']}|{data['url']}|{data['sha256']}"
        try:
            data["signature"] = sign_payload(payload, settings.license_private_key)
        except Exception:
            data["signature"] = ""

    return data
