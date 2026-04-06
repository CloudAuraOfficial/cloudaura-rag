"""P5 graph endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_graph_returns_data(client):
    resp = await client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "links" in data
    assert data["node_count"] >= 0
    assert data["edge_count"] >= 0


@pytest.mark.asyncio
async def test_graph_has_source_field(client):
    resp = await client.get("/api/graph")
    data = resp.json()
    assert data["source"] in ("precomputed", "live", "empty")


@pytest.mark.asyncio
async def test_graph_nodes_have_required_fields(client):
    resp = await client.get("/api/graph")
    data = resp.json()
    for node in data["nodes"]:
        assert "id" in node
        assert "label" in node
        assert "type" in node


@pytest.mark.asyncio
async def test_graph_links_have_required_fields(client):
    resp = await client.get("/api/graph")
    data = resp.json()
    for link in data["links"]:
        assert "source" in link
        assert "target" in link
