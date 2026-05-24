"""ThesisMind Cloud API — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cloud.app.config import settings
from cloud.app.routers import account as account_router
from cloud.app.routers import admin as admin_router
from cloud.app.routers import aigc as aigc_router
from cloud.app.routers import knowledge as knowledge_router
from cloud.app.routers import license as license_router
from cloud.app.routers import ppt as ppt_router
from cloud.app.routers import release as release_router
from cloud.app.routers import review as review_router
from cloud.app.routers import trial as trial_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    yield


app = FastAPI(
    title="ThesisMind Cloud API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(license_router.router)
app.include_router(release_router.router)
app.include_router(review_router.router)
app.include_router(aigc_router.router)
app.include_router(trial_router.router)
app.include_router(account_router.router)
app.include_router(admin_router.router)
app.include_router(knowledge_router.router)
app.include_router(ppt_router.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
