"""FastAPI dependencies — DB session, auth, rate limiting."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cloud.app.core.database import engine
from cloud.app.core.security import verify_signature


async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def verify_license_ticket(ticket: str, payload: str, public_key: bytes) -> bool:
    """Verify a license_ticket embedded in API requests."""
    return verify_signature(payload, ticket, public_key)
