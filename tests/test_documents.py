"""Tests for the /api/documents endpoints."""

import pytest


# ---------------------------------------------------------------------------
# GET /api/documents/stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_returns_200(client):
    resp = await client.get("/api/documents/stats")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stats_schema(client):
    data = (await client.get("/api/documents/stats")).json()
    assert "total_documents" in data
    assert "total_chunks" in data
    assert "embedding_model" in data
    assert "reranker_model" in data
    assert "llm_model" in data


@pytest.mark.asyncio
async def test_stats_values(client):
    data = (await client.get("/api/documents/stats")).json()
    assert data["total_documents"] == 2
    assert data["total_chunks"] == 10


# ---------------------------------------------------------------------------
# POST /api/documents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_document_returns_200(client):
    resp = await client.post(
        "/api/documents",
        json={
            "content": "This is a long enough markdown document for ingestion testing.",
            "filename": "test-doc.md",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ingest_document_response_schema(client):
    resp = await client.post(
        "/api/documents",
        json={
            "content": "Some document content that is long enough to pass validation.",
            "filename": "notes.md",
        },
    )
    data = resp.json()
    assert "filename" in data
    assert "chunks_created" in data
    assert "total_documents" in data


@pytest.mark.asyncio
async def test_ingest_document_returns_correct_filename(client):
    resp = await client.post(
        "/api/documents",
        json={
            "content": "Document content with enough characters for the minimum.",
            "filename": "my-file.md",
        },
    )
    data = resp.json()
    assert data["filename"] == "my-file.md"


@pytest.mark.asyncio
async def test_ingest_calls_services(client, mock_ingestion, mock_retriever):
    await client.post(
        "/api/documents",
        json={
            "content": "Content that is certainly long enough for ingestion.",
            "filename": "service-test.md",
        },
    )
    mock_ingestion.ingest_text.assert_called_once()
    mock_retriever.refresh_index.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_content_too_short(client):
    """Content shorter than 10 characters should be rejected with 422."""
    resp = await client.post(
        "/api/documents",
        json={"content": "short", "filename": "x.md"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_missing_filename(client):
    resp = await client.post(
        "/api/documents",
        json={"content": "This content is long enough for the validator."},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_empty_filename(client):
    resp = await client.post(
        "/api/documents",
        json={
            "content": "This content is long enough for the validator.",
            "filename": "",
        },
    )
    assert resp.status_code == 422
