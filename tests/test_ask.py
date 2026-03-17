"""Tests for the POST /api/ask endpoint."""

import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_ask_valid_question(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "What architecture does the system use?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "citations" in data
    assert isinstance(data["citations"], list)
    assert len(data["citations"]) > 0
    assert "model" in data
    assert "retrieval_method" in data
    assert "latency_ms" in data


@pytest.mark.asyncio
async def test_ask_response_echoes_question(client):
    """The response must include a 'question' field matching the input."""
    question = "What architecture does the system use?"
    resp = await client.post("/api/ask", json={"question": question})
    data = resp.json()
    assert data["question"] == question


@pytest.mark.asyncio
async def test_ask_citations_have_required_fields(client):
    resp = await client.post(
        "/api/ask", json={"question": "Tell me about the system"}
    )
    data = resp.json()
    for citation in data["citations"]:
        assert "document" in citation
        assert "chunk_id" in citation
        assert "content" in citation
        assert "score" in citation


@pytest.mark.asyncio
async def test_ask_question_too_short(client):
    """Question shorter than 3 characters should be rejected with 422."""
    resp = await client.post("/api/ask", json={"question": "ab"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_question_empty_string(client):
    resp = await client.post("/api/ask", json={"question": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_missing_question_field(client):
    resp = await client.post("/api/ask", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_top_k_valid_range(client):
    resp = await client.post(
        "/api/ask", json={"question": "What is the architecture?", "top_k": 10}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ask_top_k_too_low(client):
    resp = await client.post(
        "/api/ask", json={"question": "What is the architecture?", "top_k": 0}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_top_k_too_high(client):
    resp = await client.post(
        "/api/ask", json={"question": "What is the architecture?", "top_k": 21}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_no_results_returns_400(client, mock_retriever):
    """When retriever returns empty list, endpoint should return 400."""
    mock_retriever.retrieve.return_value = []
    resp = await client.post(
        "/api/ask", json={"question": "Something with no matches"}
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["detail"]["error"] == "no_results"


@pytest.mark.asyncio
async def test_ask_generation_error_returns_502(client, mock_generator):
    """When generator raises, endpoint should return 502."""
    mock_generator.generate_answer.side_effect = RuntimeError("Ollama timeout")
    resp = await client.post(
        "/api/ask", json={"question": "Trigger an error please"}
    )
    assert resp.status_code == 502
    data = resp.json()
    assert data["detail"]["error"] == "generation_error"


@pytest.mark.asyncio
async def test_ask_custom_model(client, mock_generator, sample_ask_response):
    """Custom model parameter should be forwarded to the generator."""
    resp = await client.post(
        "/api/ask",
        json={"question": "What is the architecture?", "model": "llama3:8b"},
    )
    assert resp.status_code == 200
    call_kwargs = mock_generator.generate_answer.call_args
    assert call_kwargs.kwargs.get("model") == "llama3:8b"
