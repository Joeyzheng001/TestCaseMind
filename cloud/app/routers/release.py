"""GET /v1/release/latest — client auto-update endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.dependencies import get_db
from cloud.app.services.release_manager import get_latest_release

router = APIRouter()


@router.get("/v1/release/latest")
async def release_latest(db: AsyncSession = Depends(get_db)):
    release = await get_latest_release(db)
    if release is None:
        return {"version": "", "release_date": "", "url": "", "sha256": "",
                "signature": "", "changelog": "", "min_client_version": ""}
    return release
