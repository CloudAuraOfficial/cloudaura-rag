"""P5 ask endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_ask_cached_query_demo_mode(client):
    """Cached queries should return instantly in demo mode."""
    resp = await client.post("/api/ask", json={
        "question": "What is Kubernetes?",
        "mode": "hybrid",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "Kubernetes is a container orchestration platform."
    assert data["model"] == "cached"
    assert data["mode"] == "hybrid"


@pytest.mark.asyncio
async def test_ask_live_query(client):
    """Non-cached queries should hit LightRAG."""
    resp = await client.post("/api/ask", json={
        "question": "How does Docker networking work?",
        "mode": "local",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
    assert data["mode"] == "local"


@pytest.mark.asyncio
async def test_ask_all_modes_accepted(client):
    for mode in ["naive", "local", "global", "hybrid", "mix"]:
        resp = await client.post("/api/ask", json={
            "question": "Tell me about containers",
            "mode": mode,
        })
        assert resp.status_code == 200, f"Mode {mode} failed"
        assert resp.json()["mode"] == mode


@pytest.mark.asyncio
async def test_ask_invalid_mode_rejected(client):
    resp = await client.post("/api/ask", json={
        "question": "Test question",
        "mode": "invalid",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_question_too_short(client):
    resp = await client.post("/api/ask", json={
        "question": "Hi",
        "mode": "hybrid",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_has_latency(client):
    resp = await client.post("/api/ask", json={
        "question": "How do pods work?",
        "mode": "hybrid",
    })
    data = resp.json()
    assert "latency_ms" in data
    assert data["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_ask_lightrag_unavailable(client, mock_lightrag):
    mock_lightrag.is_initialized = False
    resp = await client.post("/api/ask", json={
        "question": "How does networking work?",
        "mode": "local",
    })
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_ask_query_error(client, mock_lightrag):
    mock_lightrag.query.side_effect = Exception("Ollama timeout")
    resp = await client.post("/api/ask", json={
        "question": "What is a deployment?",
        "mode": "global",
    })
    assert resp.status_code == 502
