"""Tests for the /health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_schema(client):
    resp = await client.get("/health")
    data = resp.json()
    assert "status" in data
    assert "ollama_connected" in data
    assert "vector_store_chunks" in data
    assert "embedding_model" in data


@pytest.mark.asyncio
async def test_health_healthy_status(client):
    """When generator reports healthy, status should be 'healthy'."""
    data = (await client.get("/health")).json()
    assert data["status"] == "healthy"
    assert data["ollama_connected"] is True


@pytest.mark.asyncio
async def test_health_degraded_when_ollama_down(client, mock_generator):
    """When generator.is_healthy() returns False, status should be 'degraded'."""
    mock_generator.is_healthy.return_value = False
    data = (await client.get("/health")).json()
    assert data["status"] == "degraded"
    assert data["ollama_connected"] is False


@pytest.mark.asyncio
async def test_health_includes_chunk_count(client):
    data = (await client.get("/health")).json()
    assert data["vector_store_chunks"] == 10


@pytest.mark.asyncio
async def test_health_includes_embedding_model(client):
    data = (await client.get("/health")).json()
    assert isinstance(data["embedding_model"], str)
    assert len(data["embedding_model"]) > 0
