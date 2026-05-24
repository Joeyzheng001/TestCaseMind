"""Test that API routes are registered correctly."""

import pytest
from httpx import ASGITransport, AsyncClient

from cloud.app.main import app


def test_all_routes_registered():
    """Verify expected routes are registered without hitting DB."""
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/health" in routes
    assert "/v1/license/validate" in routes
    assert "/v1/trial/start" in routes
    assert "/v1/release/latest" in routes
    assert "/v1/knowledge/search" in routes
    assert "/v1/blind-review" in routes
    assert "/v1/aigc/check" in routes
    assert "/v1/aigc/reduce" in routes
    assert "/v1/ppt/generate" in routes
    assert "/v1/ppt/task/{task_id}" in routes
    assert "/v1/account/register" in routes
    assert "/v1/admin/licenses" in routes
    assert "/v1/admin/licenses/issue" in routes
    assert "/v1/admin/licenses/revoke" in routes
    assert "/v1/admin/activations/{license_id}" in routes
    assert "/v1/admin/activations/unbind" in routes
    assert "/v1/admin/audit-logs" in routes
    assert "/docs" in routes


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_docs_accessible():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/docs")
    assert resp.status_code == 200
