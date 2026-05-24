"""AIGC detection request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AigcCheckRequest(BaseModel):
    content: str = ""
    chapters: list[dict] = Field(default_factory=list)
    license_ticket: str = ""


class HighlightSpan(BaseModel):
    start: int
    end: int
    indicator: str = ""
    reason: str = ""


class ChapterAigcResult(BaseModel):
    title: str = ""
    score: float = 0.0
    risk_level: str = ""  # low | medium | high
    highlights: list[dict] = Field(default_factory=list)
    explanation: str = ""


class AigcCheckResponse(BaseModel):
    results: list[dict] = Field(default_factory=list)


class AigcReduceRequest(BaseModel):
    content: str = ""
    chapters: list[dict] = Field(default_factory=list)
    license_ticket: str = ""


class AigcReduceResponse(BaseModel):
    results: list[dict] = Field(default_factory=list)
