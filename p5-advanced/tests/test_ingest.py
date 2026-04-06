"""P5 ingest endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_ingest_text(client):
    resp = await client.post("/api/ingest", json={
        "content": "Kubernetes manages container workloads.",
        "content_type": "text",
        "filename": "k8s.md",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ingested"
    assert data["filename"] == "k8s.md"
    assert data["content_type"] == "text"


@pytest.mark.asyncio
async def test_ingest_image_description(client):
    resp = await client.post("/api/ingest", json={
        "content": "Architecture diagram showing microservices connected via API gateway.",
        "content_type": "image_description",
        "filename": "arch_diagram.png",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ingested"


@pytest.mark.asyncio
async def test_ingest_table(client):
    resp = await client.post("/api/ingest", json={
        "content": "| Service | Port |\n|---------|------|\n| API | 8080 |\n| DB | 5432 |",
        "content_type": "table_markdown",
        "filename": "services.md",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ingested"


@pytest.mark.asyncio
async def test_ingest_invalid_content_type(client):
    resp = await client.post("/api/ingest", json={
        "content": "Some content",
        "content_type": "video",
        "filename": "test.mp4",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_failure(client, mock_ingestor):
    mock_ingestor.ingest.return_value = False
    resp = await client.post("/api/ingest", json={
        "content": "Test content",
        "content_type": "text",
        "filename": "test.md",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
