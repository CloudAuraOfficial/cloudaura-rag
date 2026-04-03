"""Test fixtures for RAG-P3 Quality."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from rag_core.testing.conftest_base import *  # noqa: F401,F403
from rag_core.models.schemas import RetrievalResult
from app.config import settings
from app.models.schemas import QueryClassification, QualityScore, CorrectionRound


@pytest.fixture
def mock_classifier():
    svc = AsyncMock()
    svc.classify.return_value = QueryClassification(
        category="complex",
        confidence=0.85,
        reasoning="Multi-faceted question",
    )
    svc.close.return_value = None
    return svc


@pytest.fixture
def mock_quality_checker():
    svc = MagicMock()
    svc.check.return_value = QualityScore(
        score=0.78,
        passed=True,
        details="Best relevance: 0.780 (threshold: 0.5)",
    )
    return svc


@pytest.fixture
def mock_adaptive_router(sample_retrieval_results, mock_classifier):
    svc = AsyncMock()
    svc.route.return_value = (
        sample_retrieval_results,
        QueryClassification(category="complex", confidence=0.85, reasoning="Multi-faceted"),
        "full hybrid (BM25 + vector + RRF + rerank)",
    )
    return svc


@pytest.fixture
def mock_corrective_retriever(sample_retrieval_results):
    svc = AsyncMock()
    svc.retrieve.return_value = (
        sample_retrieval_results,
        QualityScore(score=0.78, passed=True, details="Good quality"),
        [],
    )
    svc.close.return_value = None
    return svc


@pytest_asyncio.fixture
async def client(mock_ingestion, mock_retriever, mock_generator, mock_adaptive_router, mock_corrective_retriever, mock_quality_checker):
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from app.routers import ask
    from rag_core.routers import documents, health

    test_app = FastAPI()
    test_app.include_router(health.router)
    test_app.include_router(ask.router)
    test_app.include_router(documents.router)
    test_app.mount("/", StaticFiles(directory="p3-quality/app/static", html=True), name="static")

    test_app.state.settings = settings
    test_app.state.ingestion = mock_ingestion
    test_app.state.retriever = mock_retriever
    test_app.state.generator = mock_generator
    test_app.state.adaptive_router = mock_adaptive_router
    test_app.state.corrective_retriever = mock_corrective_retriever
    test_app.state.quality_checker = mock_quality_checker
    test_app.state.embedder = MagicMock()
    test_app.state.reranker = MagicMock()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
