"""Common Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    code: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
