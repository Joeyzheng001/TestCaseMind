"""Knowledge search request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    license_ticket: str = ""


class KnowledgeResult(BaseModel):
    title: str
    path: str
    content: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeResult] = []
