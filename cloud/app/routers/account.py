"""POST /v1/account/register — user registration."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.dependencies import get_db
from cloud.app.services.account_manager import register_user

router = APIRouter()


@router.post("/v1/account/register")
async def account_register(body: dict, db: AsyncSession = Depends(get_db)):
    email = (body.get("email", "") or "").strip().lower()
    if not email or "@" not in email:
        return {"status": "error", "message": "请提供有效的邮箱地址"}

    user = await register_user(db, email, body.get("display_name", ""))
    return {
        "status": "ok",
        "user_id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
    }
