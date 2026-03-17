"""Shared fixtures for cloudaura-rag test suite.

All external dependencies (Ollama, ChromaDB, sentence-transformers) are mocked
so tests run without any infrastructure.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import State

from app.models.schemas import AskResponse, Citation, RetrievalResult


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_chunks() -> list[dict]:
    return [
        {
            "chunk_id": "abc123",
            "document": "architecture.md",
            "content": "The system uses a microservices architecture with event-driven communication.",
            "bm25_score": 2.5,
            "vector_score": 0.88,
            "rerank_score": 0.95,
            "fused_rank": 1,
        },
        {
            "chunk_id": "def456",
            "document": "deployment.md",
            "content": "Deployments are managed through Docker Compose with health checks.",
            "bm25_score": 1.8,
            "vector_score": 0.72,
            "rerank_score": 0.80,
            "fused_rank": 2,
        },
    ]


@pytest.fixture
def sample_retrieval_results(sample_chunks) -> list[RetrievalResult]:
    return [RetrievalResult(**c) for c in sample_chunks]


@pytest.fixture
def sample_ask_response(sample_retrieval_results) -> AskResponse:
    return AskResponse(
        question="What architecture does the system use?",
        answer="The system uses a microservices architecture [Source: architecture.md, abc123].",
        citations=[
            Citation(
                document=r.document,
                chunk_id=r.chunk_id,
                content=r.content[:200],
                score=r.rerank_score or 0.0,
            )
            for r in sample_retrieval_results
        ],
        model="phi3:mini",
        retrieval_method="hybrid (BM25 + vector + cross-encoder rerank)",
        latency_ms=150.0,
    )


# ---------------------------------------------------------------------------
# Mock services
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ingestion():
    svc = MagicMock()
    svc.get_stats.return_value = {"total_documents": 2, "total_chunks": 10}
    svc.ingest_text.return_value = 5
    svc.collection = MagicMock()
    svc.collection.count.return_value = 10
    return svc


@pytest.fixture
def mock_retriever(sample_retrieval_results):
    svc = MagicMock()
    svc.retrieve.return_value = sample_retrieval_results
    svc.refresh_index.return_value = None
    return svc


@pytest.fixture
def mock_generator(sample_ask_response):
    svc = AsyncMock()
    svc.is_healthy.return_value = True
    svc.generate_answer.return_value = sample_ask_response
    svc.close.return_value = None
    return svc


@pytest.fixture
def mock_embedder():
    svc = MagicMock()
    svc.embed.return_value = [[0.1] * 384]
    svc.embed_query.return_value = [0.1] * 384
    svc.dimension = 384
    return svc


@pytest.fixture
def mock_reranker():
    svc = MagicMock()

    def _rerank(query, documents, top_k=None):
        for i, doc in enumerate(documents):
            doc["rerank_score"] = 1.0 - (i * 0.1)
        top_k = top_k or 5
        return documents[:top_k]

    svc.rerank.side_effect = _rerank
    return svc


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(mock_ingestion, mock_retriever, mock_generator):
    """AsyncClient wired to a test FastAPI app with mocked state.

    We build a minimal FastAPI app that skips the real lifespan (which would
    load ML models and connect to ChromaDB/Ollama). Instead we inject mock
    services directly into app.state before any request is made.
    """
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from app.routers import ask, documents, health

    test_app = FastAPI()
    test_app.include_router(health.router)
    test_app.include_router(ask.router)
    test_app.include_router(documents.router)
    test_app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

    # Inject mocked services directly — no lifespan needed.
    test_app.state.ingestion = mock_ingestion
    test_app.state.retriever = mock_retriever
    test_app.state.generator = mock_generator
    test_app.state.embedder = MagicMock()
    test_app.state.reranker = MagicMock()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
