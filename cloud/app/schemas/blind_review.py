"""Blind review request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BlindReviewRequest(BaseModel):
    content: str = ""
    chapter_title: str = ""
    chapters: list[dict] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    license_ticket: str = ""


class RiskItem(BaseModel):
    severity: str  # critical | high | medium | low
    category: str
    name: str
    evidence: str = ""
    check_question: str = ""
    fix_strategy: str = ""


class BlindReviewResponse(BaseModel):
    total_checks: int = 0
    triggered: int = 0
    critical_count: int = 0
    high_count: int = 0
    results: list[dict] = Field(default_factory=list)
