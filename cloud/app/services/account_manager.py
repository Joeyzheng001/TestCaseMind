"""Account management service — registration, lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cloud.app.models.user import User


async def register_user(db: AsyncSession, email: str, display_name: str = "") -> User:
    """Register a new user or return existing one."""
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    user = User(
        id=uuid.uuid4(),
        email=email,
        display_name=display_name or email.split("@")[0],
    )
    db.add(user)
    await db.flush()
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
