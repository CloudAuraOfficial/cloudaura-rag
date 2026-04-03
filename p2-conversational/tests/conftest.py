"""Test fixtures for RAG-P2 Conversational."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from rag_core.testing.conftest_base import *  # noqa: F401,F403
from app.config import settings
from app.services.memory_store import MemoryStore


@pytest.fixture
def memory():
    return MemoryStore(window=10, max_sessions=100)


@pytest.fixture
def mock_memory_retriever(sample_retrieval_results):
    svc = MagicMock()
    svc.retrieve.return_value = sample_retrieval_results
    return svc


@pytest.fixture
def mock_branched_retriever(sample_retrieval_results):
    svc = AsyncMock()
    svc.retrieve.return_value = (
        sample_retrieval_results,
        [
            {"question": "Sub question 1?", "results_count": 2},
            {"question": "Sub question 2?", "results_count": 3},
        ],
    )
    return svc


@pytest.fixture
def mock_decomposer():
    svc = AsyncMock()
    svc.decompose.return_value = ["Sub question 1?", "Sub question 2?"]
    svc.close.return_value = None
    return svc


@pytest_asyncio.fixture
async def client(mock_ingestion, mock_retriever, mock_generator, mock_memory_retriever, mock_branched_retriever):
    """AsyncClient wired to a test FastAPI app with mocked state."""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from app.routers import ask, conversations
    from rag_core.routers import documents, health

    test_app = FastAPI()
    test_app.include_router(health.router)
    test_app.include_router(ask.router)
    test_app.include_router(conversations.router)
    test_app.include_router(documents.router)
    test_app.mount("/", StaticFiles(directory="p2-conversational/app/static", html=True), name="static")

    memory = MemoryStore(window=10, max_sessions=100)

    test_app.state.settings = settings
    test_app.state.ingestion = mock_ingestion
    test_app.state.retriever = mock_retriever
    test_app.state.generator = mock_generator
    test_app.state.memory = memory
    test_app.state.memory_retriever = mock_memory_retriever
    test_app.state.branched_retriever = mock_branched_retriever
    test_app.state.embedder = MagicMock()
    test_app.state.reranker = MagicMock()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
