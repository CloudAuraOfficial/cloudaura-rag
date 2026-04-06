"""P4 ask endpoint tests — Self-RAG and Agentic modes."""

import pytest

from rag_core.models.schemas import AskResponse, Citation


@pytest.mark.asyncio
async def test_ask_self_rag_mode(client):
    resp = await client.post("/api/ask", json={
        "question": "What architecture does the system use?",
        "mode": "self_rag",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "self_rag"
    assert data["answer"]
    assert data["relevance_grades"] is not None
    assert data["critique"] is not None
    assert "self-rag" in data["retrieval_method"]


@pytest.mark.asyncio
async def test_ask_agentic_mode(client):
    resp = await client.post("/api/ask", json={
        "question": "Compare Docker and Kubernetes",
        "mode": "agentic",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "agentic"
    assert data["answer"]
    assert data["agent_steps"] is not None
    assert len(data["agent_steps"]) > 0
    assert "agentic" in data["retrieval_method"]


@pytest.mark.asyncio
async def test_ask_both_mode(client):
    resp = await client.post("/api/ask", json={
        "question": "How do deployments work?",
        "mode": "both",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "both"
    assert data["answer"]


@pytest.mark.asyncio
async def test_ask_default_mode_is_self_rag(client):
    resp = await client.post("/api/ask", json={
        "question": "What is the system architecture?",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "self_rag"


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
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_self_rag_no_results(client, mock_self_rag):
    mock_self_rag.run.return_value = (None, [], 0, None)
    resp = await client.post("/api/ask", json={
        "question": "Completely irrelevant question about nothing",
        "mode": "self_rag",
    })
    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"]["error"] == "no_results"


@pytest.mark.asyncio
async def test_ask_agentic_error_returns_502(client, mock_agent_executor):
    mock_agent_executor.run.side_effect = Exception("Ollama down")
    resp = await client.post("/api/ask", json={
        "question": "What is the architecture?",
        "mode": "agentic",
    })
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_ask_response_has_latency(client):
    resp = await client.post("/api/ask", json={
        "question": "What architecture does the system use?",
        "mode": "self_rag",
    })
    data = resp.json()
    assert "latency_ms" in data
    assert data["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_ask_response_has_citations(client):
    resp = await client.post("/api/ask", json={
        "question": "What architecture does the system use?",
        "mode": "self_rag",
    })
    data = resp.json()
    assert "citations" in data
    assert isinstance(data["citations"], list)


@pytest.mark.asyncio
async def test_ask_agentic_has_steps_with_tool_calls(client):
    resp = await client.post("/api/ask", json={
        "question": "Compare Docker and Kubernetes",
        "mode": "agentic",
    })
    data = resp.json()
    steps = data["agent_steps"]
    assert steps[0]["tool_call"]["tool"] == "retrieve"
    assert steps[1]["tool_call"]["tool"] == "answer"
