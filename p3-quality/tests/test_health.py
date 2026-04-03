"""Tests for the /health endpoint (P3)."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_schema(client):
    data = (await client.get("/health")).json()
    assert "status" in data
    assert "ollama_connected" in data
    assert "vector_store_chunks" in data
