"""Tool registry unit tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.tool_registry import ToolRegistry
from rag_core.models.schemas import RetrievalResult


@pytest.fixture
def retrieval_results():
    return [
        RetrievalResult(
            chunk_id="abc123",
            document="architecture.md",
            content="Microservices architecture with event-driven communication.",
            rerank_score=0.95,
        ),
    ]


@pytest.fixture
def registry(retrieval_results):
    retriever = MagicMock()
    retriever.retrieve.return_value = retrieval_results
    generator = AsyncMock()
    generator._client = AsyncMock()
    generator._default_model = "phi3:mini"
    return ToolRegistry(retriever, generator)


@pytest.mark.asyncio
async def test_retrieve_tool(registry):
    result = await registry.execute("retrieve", {"query": "architecture"})
    assert "architecture.md" in result
    assert len(registry.retrieved_results) == 1


@pytest.mark.asyncio
async def test_retrieve_empty_query(registry):
    result = await registry.execute("retrieve", {"query": ""})
    assert "Error" in result


@pytest.mark.asyncio
async def test_calculate_tool(registry):
    result = await registry.execute("calculate", {"expression": "2 + 3 * 4"})
    assert result == "14"


@pytest.mark.asyncio
async def test_calculate_invalid_expression(registry):
    result = await registry.execute("calculate", {"expression": "import os"})
    assert "Error" in result or "could not evaluate" in result


@pytest.mark.asyncio
async def test_answer_tool(registry):
    result = await registry.execute("answer", {"answer": "The system uses microservices."})
    assert result == "The system uses microservices."


@pytest.mark.asyncio
async def test_unknown_tool(registry):
    result = await registry.execute("nonexistent", {})
    assert "Unknown tool" in result


@pytest.mark.asyncio
async def test_reset_clears_results(registry):
    await registry.execute("retrieve", {"query": "test"})
    assert len(registry.retrieved_results) > 0
    registry.reset()
    assert len(registry.retrieved_results) == 0


@pytest.mark.asyncio
async def test_calculate_empty_expression(registry):
    result = await registry.execute("calculate", {"expression": ""})
    assert "Error" in result
