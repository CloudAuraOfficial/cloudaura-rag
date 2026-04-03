"""Tests for the P3 /api/ask endpoint with adaptive and corrective modes."""

import pytest
from unittest.mock import AsyncMock

from app.models.schemas import QueryClassification, QualityScore


@pytest.mark.asyncio
async def test_ask_adaptive_mode(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "What is Docker?", "mode": "adaptive"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "classification" in data
    assert "route_taken" in data


@pytest.mark.asyncio
async def test_ask_corrective_mode(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "How does monitoring work?", "mode": "corrective"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "quality" in data
    assert data["quality"]["passed"] is True


@pytest.mark.asyncio
async def test_ask_both_mode(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "Compare Docker and K8s", "mode": "both"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "classification" in data


@pytest.mark.asyncio
async def test_ask_classification_schema(client):
    resp = await client.post(
        "/api/ask",
        json={"question": "What is the port?", "mode": "adaptive"},
    )
    data = resp.json()
    c = data["classification"]
    assert "category" in c
    assert "confidence" in c
    assert "reasoning" in c
    assert c["category"] in ("no_retrieval", "simple", "complex")


@pytest.mark.asyncio
async def test_ask_no_retrieval_route(client, mock_adaptive_router, mock_generator):
    """When classified as no_retrieval, should return answer without citations."""
    mock_adaptive_router.route.return_value = (
        [],
        QueryClassification(category="no_retrieval", confidence=0.95, reasoning="General knowledge"),
        "direct LLM (no retrieval needed)",
    )
    # Mock the direct LLM call — httpx response methods are sync
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "Docker is a container platform."}

    mock_generator._client = AsyncMock()
    mock_generator._client.post.return_value = mock_response
    mock_generator._default_model = "phi3:mini"

    resp = await client.post(
        "/api/ask",
        json={"question": "What is 2+2?", "mode": "adaptive"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["citations"] == []
    assert data["route_taken"] == "direct LLM (no retrieval needed)"


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
async def test_ask_no_results_returns_400(client, mock_adaptive_router):
    mock_adaptive_router.route.return_value = (
        [],
        QueryClassification(category="simple", confidence=0.8, reasoning="Simple"),
        "simple vector search",
    )
    resp = await client.post(
        "/api/ask",
        json={"question": "Something with no matches", "mode": "adaptive"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ask_generation_error_returns_502(client, mock_generator):
    mock_generator.generate_answer.side_effect = RuntimeError("Ollama timeout")
    resp = await client.post(
        "/api/ask",
        json={"question": "Trigger error", "mode": "corrective"},
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_ask_corrections_in_response(client, mock_corrective_retriever, sample_retrieval_results):
    mock_corrective_retriever.retrieve.return_value = (
        sample_retrieval_results,
        QualityScore(score=0.75, passed=True, details="Better"),
        [{"round": 1, "expanded_query": "Better query", "quality_score": 0.75, "passed": True, "results_count": 3}],
    )
    resp = await client.post(
        "/api/ask",
        json={"question": "Vague question", "mode": "corrective"},
    )
    data = resp.json()
    assert data["corrections"] is not None
    assert len(data["corrections"]) == 1
    assert data["corrections"][0]["round"] == 1
