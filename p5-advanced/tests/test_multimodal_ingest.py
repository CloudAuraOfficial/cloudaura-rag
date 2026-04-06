"""Multimodal ingestor unit tests."""

from unittest.mock import AsyncMock

import pytest

from app.services.multimodal_ingest import MultimodalIngestor


@pytest.fixture
def mock_lightrag_wrapper():
    svc = AsyncMock()
    svc.ingest.return_value = True
    return svc


@pytest.fixture
def ingestor(mock_lightrag_wrapper):
    return MultimodalIngestor(
        lightrag=mock_lightrag_wrapper,
        ollama_base_url="http://localhost:11434",
        model="phi3:mini",
    )


@pytest.mark.asyncio
async def test_ingest_text(ingestor, mock_lightrag_wrapper):
    result = await ingestor.ingest_text("Hello world", "test.md")
    assert result is True
    call_args = mock_lightrag_wrapper.ingest.call_args[0][0]
    assert "Document: test.md" in call_args


@pytest.mark.asyncio
async def test_ingest_image_description(ingestor, mock_lightrag_wrapper):
    result = await ingestor.ingest_image_description("A network diagram showing services", "arch.png")
    assert result is True
    call_args = mock_lightrag_wrapper.ingest.call_args[0][0]
    assert "Image: arch.png" in call_args
    assert "Visual Description" in call_args


@pytest.mark.asyncio
async def test_ingest_table(ingestor, mock_lightrag_wrapper):
    table = "| A | B |\n|---|---|\n| 1 | 2 |"
    result = await ingestor.ingest_table(table, "data.md")
    assert result is True
    call_args = mock_lightrag_wrapper.ingest.call_args[0][0]
    assert "Table: data.md" in call_args
    assert "Structured Data" in call_args


@pytest.mark.asyncio
async def test_ingest_routes_correctly(ingestor, mock_lightrag_wrapper):
    await ingestor.ingest("text content", "text", "file.md")
    assert mock_lightrag_wrapper.ingest.call_count == 1

    await ingestor.ingest("image desc", "image_description", "img.png")
    assert mock_lightrag_wrapper.ingest.call_count == 2

    await ingestor.ingest("| a | b |", "table_markdown", "tbl.md")
    assert mock_lightrag_wrapper.ingest.call_count == 3


@pytest.mark.asyncio
async def test_ingest_failure(ingestor, mock_lightrag_wrapper):
    mock_lightrag_wrapper.ingest.return_value = False
    result = await ingestor.ingest("content", "text", "test.md")
    assert result is False
