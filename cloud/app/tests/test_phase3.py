"""Test Phase 3 endpoints: blind review, AIGC, PPT."""

import pytest
from httpx import ASGITransport, AsyncClient

from cloud.app.main import app


# ── Blind review ──

@pytest.mark.asyncio
async def test_blind_review_empty_content():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/blind-review", json={"content": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "内容" in data["message"]


@pytest.mark.asyncio
async def test_blind_review_with_content():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/blind-review", json={
            "content": "本文研究了基于深度学习的图像识别方法。采用了卷积神经网络作为基础模型。",
            "chapter_title": "第一章 绪论",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "total_risks" in data
    assert "triggered" in data
    assert "results" in data


# ── AIGC check ──

@pytest.mark.asyncio
async def test_aigc_check_no_content():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/aigc/check", json={"chapters": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_aigc_check_with_content():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/aigc/check", json={
            "chapters": [{
                "title": "测试章节",
                "content": "值得注意的是，本文通过深度学习方法实现了高效检测。"
                           "综上所述，该方法具有重要的意义。此外，还需要进一步优化算法。"
                           "本章以某企业实际项目为例，2023年进行了实地调研。"
            }]
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "overall_score" in data
    assert "overall_risk" in data
    assert len(data["results"]) == 1
    # Should have AI patterns detected
    ch = data["results"][0]
    assert ch["score"] > 0
    assert ch["risk_level"] in ("low", "medium", "high")


@pytest.mark.asyncio
async def test_aigc_check_human_text():
    """Text with specific references should score lower (more human-like)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/aigc/check", json={
            "chapters": [{
                "title": "案例研究",
                "content": "笔者在2024年3月参与了某市轨道交通项目，对项目进行了实地调研。"
                           "根据GB/T 12345-2022标准规范，数据来源于问卷调查500份。"
                           "如表1所示，该项目在实施过程中面临了诸多挑战。"
            }]
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Human-like text should have lower risk
    assert data["results"][0]["risk_level"] == "low"


# ── AIGC reduce ──

@pytest.mark.asyncio
async def test_aigc_reduce_no_content():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/aigc/reduce", json={"chapters": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_aigc_reduce_no_llm_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/aigc/reduce", json={
            "chapters": [{"title": "test", "content": "test content"}]
        })
    assert resp.status_code == 200
    data = resp.json()
    # Without LLM key, should report error or note
    assert data["status"] in ("error", "ok")


# ── PPT generate ──

@pytest.mark.asyncio
async def test_ppt_generate():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/ppt/generate", json={
            "ppt_type": "defense",
            "outline": {"title": "test"},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    return data["task_id"]


@pytest.mark.asyncio
async def test_ppt_task_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/ppt/task/nonexistent-id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"


@pytest.mark.asyncio
async def test_ppt_generate_and_poll():
    """Generate a PPT task then poll its status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        gen_resp = await client.post("/v1/ppt/generate", json={
            "ppt_type": "proposal",
            "outline": {"title": "测试论文"},
        })
        task_id = gen_resp.json()["task_id"]

        poll_resp = await client.get(f"/v1/ppt/task/{task_id}")
        assert poll_resp.status_code == 200
        data = poll_resp.json()
        assert data["task_id"] == task_id
        assert data["status"] in ("queued", "running", "done", "failed")
