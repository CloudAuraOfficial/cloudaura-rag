"""Health endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_head_method(client):
    resp = await client.head("/health")
    assert resp.status_code == 200
