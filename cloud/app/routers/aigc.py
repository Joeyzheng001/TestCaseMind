"""POST /v1/aigc/check, POST /v1/aigc/reduce — cloud AIGC endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from cloud.app.services.aigc_detector import check_aigc

router = APIRouter()


@router.post("/v1/aigc/check")
async def aigc_check(body: dict):
    return check_aigc(body)


@router.post("/v1/aigc/reduce")
async def aigc_reduce(body: dict):
    chapters = body.get("chapters", []) or []
    if not chapters:
        return {"status": "error", "message": "暂无内容可降重"}

    # AIGC reduction requires LLM rewriting.
    # Cloud needs its own LLM API key (set via AIGC_REDUCE_LLM_KEY env var).
    import os
    if not os.getenv("AIGC_REDUCE_LLM_KEY"):
        return {
            "status": "error",
            "message": "云端未配置LLM密钥，降重功能暂不可用。请在本地使用自己的API密钥进行降重。",
        }

    # Stub — full LLM-based reduction to be implemented with cloud LLM key
    return {
        "status": "ok",
        "results": chapters,
        "note": "云端降重功能需要配置AIGC_REDUCE_LLM_KEY环境变量",
    }
