"""POST /v1/knowledge/search — cloud knowledge base search."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/v1/knowledge/search")
async def knowledge_search(body: dict):
    """Knowledge base semantic search (stub — implemented with pgvector later)."""
    return {"results": []}
