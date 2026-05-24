"""Admin endpoints — license management, device unbind, audit log queries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.dependencies import get_db
from cloud.app.services.admin_manager import (
    admin_issue_license,
    admin_list_activations,
    admin_list_audit_logs,
    admin_list_licenses,
    admin_revoke_license,
    admin_unbind_device,
)

router = APIRouter()


@router.get("/v1/admin/licenses")
async def list_licenses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await admin_list_licenses(db, page=page, page_size=page_size)


@router.post("/v1/admin/licenses/issue")
async def issue_license(body: dict, db: AsyncSession = Depends(get_db)):
    email = (body.get("email", "") or "").strip().lower()
    tier = (body.get("tier", "") or "").strip().lower()
    if not email or "@" not in email:
        return {"status": "error", "message": "请提供有效的邮箱地址"}
    if not tier:
        return {"status": "error", "message": "请选择许可证等级"}
    return await admin_issue_license(db, email, tier)


@router.post("/v1/admin/licenses/revoke")
async def revoke_license(body: dict, db: AsyncSession = Depends(get_db)):
    license_id = body.get("license_id", "")
    return await admin_revoke_license(db, license_id)


@router.get("/v1/admin/activations/{license_id}")
async def list_activations(license_id: str, db: AsyncSession = Depends(get_db)):
    return await admin_list_activations(db, license_id)


@router.post("/v1/admin/activations/unbind")
async def unbind_device(body: dict, db: AsyncSession = Depends(get_db)):
    activation_id = body.get("activation_id", "")
    return await admin_unbind_device(db, activation_id)


@router.get("/v1/admin/audit-logs")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    return await admin_list_audit_logs(db, page=page, page_size=page_size, action=action)
