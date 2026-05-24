"""PPT generation request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class PptGenerateRequest(BaseModel):
    ppt_type: str  # proposal | midterm | defense
    outline: dict
    design_spec: dict | None = None
    license_ticket: str = ""


class PptGenerateResponse(BaseModel):
    task_id: str
    status: str = "queued"


class PptTaskResponse(BaseModel):
    task_id: str
    status: str  # queued | running | done | failed
    progress: int = 0
    message: str = ""
    download_url: str | None = None
    expires_in: int | None = None
