"""POST /v1/ppt/generate, GET /v1/ppt/task/{task_id} — cloud PPT endpoints."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()

# In-memory task store (replace with DB in production)
PPT_TASKS: dict[str, dict] = {}


@router.post("/v1/ppt/generate")
async def ppt_generate(body: dict):
    task_id = str(uuid.uuid4())
    PPT_TASKS[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "progress": 0,
        "message": "任务已排队",
        "download_url": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # PPT generation requires LLM for design spec + SVG generation.
    # Cloud needs its own LLM API key (set via PPT_LLM_KEY env var).
    if not os.getenv("PPT_LLM_KEY"):
        PPT_TASKS[task_id]["status"] = "failed"
        PPT_TASKS[task_id]["message"] = "云端未配置LLM密钥，PPT生成暂不可用"
        return {"task_id": task_id, "status": "queued"}

    # Stub — full PPT generation to be implemented with cloud LLM key
    PPT_TASKS[task_id]["status"] = "queued"
    PPT_TASKS[task_id]["message"] = "PPT生成功能依赖云端LLM密钥（PPT_LLM_KEY），待配置后实现完整管线"

    return {"task_id": task_id, "status": "queued"}


@router.get("/v1/ppt/task/{task_id}")
async def ppt_task(task_id: str):
    task = PPT_TASKS.get(task_id)
    if not task:
        return {"status": "error", "message": "任务不存在"}
    return task
