"""P5 health endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert "demo_mode" in data
    assert "graph_nodes" in data


@pytest.mark.asyncio
async def test_health_head(client):
    resp = await client.head("/health")
    assert resp.status_code == 200
