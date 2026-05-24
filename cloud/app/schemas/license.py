"""License validation request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LicenseValidateRequest(BaseModel):
    license_code: str
    device_id: str
    client_version: str
    email: str = ""


class LicenseValidateResponse(BaseModel):
    status: str  # valid | expired | revoked | device_limit | not_found
    tier: str
    tier_label: str
    features: list[str] = Field(default_factory=list)
    expires_at: datetime | str = ""
    device_limit: int = 1
    device_count: int = 0
    revoked: bool = False
    user_email: str = ""
    signature: str = ""
    signed_at: str = ""


class TrialStartRequest(BaseModel):
    email: str
    device_id: str


class TrialStartResponse(BaseModel):
    status: str  # started | already_used | rejected
    trial_days_left: int = 0
    trial_end: str = ""
    features: list[str] = Field(default_factory=list)
    signature: str = ""
