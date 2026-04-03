"""Tests for the P2 /api/ask endpoint with memory and branched modes."""

import pytest


@pytest.mark.asyncio
async def test_ask_memory_mode(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "What is Docker?", "mode": "memory"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "session_id" in data
    assert "conversation_context" in data
    assert data["retrieval_method"].startswith("memory")


@pytest.mark.asyncio
async def test_ask_branched_mode(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "Compare Docker and Kubernetes", "mode": "branched"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "sub_questions" in data
    assert data["sub_questions"] is not None
    assert len(data["sub_questions"]) > 0
    assert data["retrieval_method"].startswith("branched")


@pytest.mark.asyncio
async def test_ask_both_mode(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "What about scaling?", "mode": "both"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "combined" in data["retrieval_method"]


@pytest.mark.asyncio
async def test_ask_creates_session(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "What is Docker?"},
    )
    data = resp.json()
    assert data["session_id"] is not None
    assert len(data["session_id"]) == 12


@pytest.mark.asyncio
async def test_ask_reuses_session(client):
    resp1 = await client.post(
        "/api/ask",
        json={"question": "What is Docker?"},
    )
    sid = resp1.json()["session_id"]

    resp2 = await client.post(
        "/api/ask",
        json={"question": "Tell me more", "session_id": sid},
    )
    assert resp2.json()["session_id"] == sid


@pytest.mark.asyncio
async def test_ask_tracks_context_count(client):
    resp1 = await client.post(
        "/api/ask",
        json={"question": "First question"},
    )
    sid = resp1.json()["session_id"]
    # After first exchange: 1 user + 1 assistant = 2
    assert resp1.json()["conversation_context"] == 2

    resp2 = await client.post(
        "/api/ask",
        json={"question": "Second question", "session_id": sid},
    )
    # After second exchange: 2 user + 2 assistant = 4
    assert resp2.json()["conversation_context"] == 4


@pytest.mark.asyncio
async def test_ask_invalid_mode(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "Test question", "mode": "invalid"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_question_too_short(client):
    resp = await client.post("/api/ask", json={"question": "ab"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_no_results_returns_400(client, mock_memory_retriever):
    mock_memory_retriever.retrieve.return_value = []
    resp = await client.post(
        "/api/ask",
        json={"question": "Something with no matches"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ask_generation_error_returns_502(client, mock_generator):
    mock_generator.generate_answer.side_effect = RuntimeError("Ollama timeout")
    resp = await client.post(
        "/api/ask",
        json={"question": "Trigger error please"},
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_ask_sub_questions_schema(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "Compare Docker and K8s", "mode": "branched"},
    )
    data = resp.json()
    for sq in data["sub_questions"]:
        assert "question" in sq
        assert "results_count" in sq
