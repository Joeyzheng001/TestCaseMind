"""POST /v1/license/validate — license validation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.dependencies import get_db
from cloud.app.schemas.license import LicenseValidateRequest, LicenseValidateResponse
from cloud.app.services.license_signer import validate_license

router = APIRouter()


@router.post("/v1/license/validate", response_model=LicenseValidateResponse)
async def license_validate(
    body: LicenseValidateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else ""
    result = await validate_license(
        db,
        license_code=body.license_code,
        device_id=body.device_id,
        client_version=body.client_version,
        email=body.email,
        ip_address=client_ip,
    )
    return result
