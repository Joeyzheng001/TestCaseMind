"""POST /v1/trial/start — trial initiation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.dependencies import get_db
from cloud.app.schemas.license import TrialStartRequest, TrialStartResponse
from cloud.app.services.trial_manager import start_trial

router = APIRouter()


@router.post("/v1/trial/start", response_model=TrialStartResponse)
async def trial_start(
    body: TrialStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host if request.client else ""
    result = await start_trial(
        db,
        email=body.email,
        device_id=body.device_id,
        ip_address=client_ip,
    )
    return result
