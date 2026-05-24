"""POST /v1/blind-review — cloud blind review endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from cloud.app.services.blind_review import check_blind_review

router = APIRouter()


@router.post("/v1/blind-review")
async def blind_review(body: dict):
    result = check_blind_review(body)
    return result
