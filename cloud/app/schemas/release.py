"""Release version response schema."""

from __future__ import annotations

from pydantic import BaseModel


class ReleaseLatestResponse(BaseModel):
    version: str
    release_date: str
    url: str
    sha256: str
    signature: str = ""
    changelog: str = ""
    min_client_version: str = ""
