"""Tests for conversation management endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_conversation(client):
    resp = await client.post("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert len(data["session_id"]) == 12


@pytest.mark.asyncio
async def test_list_conversations_empty(client):
    resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["sessions"] == []


@pytest.mark.asyncio
async def test_list_conversations_after_create(client):
    await client.post("/api/conversations")
    await client.post("/api/conversations")
    resp = await client.get("/api/conversations")
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_delete_conversation(client):
    create_resp = await client.post("/api/conversations")
    sid = create_resp.json()["session_id"]
    del_resp = await client.delete(f"/api/conversations/{sid}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_delete_nonexistent_conversation(client):
    resp = await client.delete("/api/conversations/nonexistent123")
    assert resp.status_code == 404
