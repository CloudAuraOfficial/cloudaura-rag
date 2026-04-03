"""Test fixtures for RAG-P1 Foundations.

Imports shared fixtures from rag_core and adds P1-specific test setup.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from rag_core.testing.conftest_base import *  # noqa: F401,F403
from app.config import settings


@pytest_asyncio.fixture
async def client(mock_ingestion, mock_retriever, mock_generator):
    """AsyncClient wired to a test FastAPI app with mocked state."""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from app.routers import ask
    from rag_core.routers import documents, health

    test_app = FastAPI()
    test_app.include_router(health.router)
    test_app.include_router(ask.router)
    test_app.include_router(documents.router)
    test_app.mount("/", StaticFiles(directory="p1-foundations/app/static", html=True), name="static")

    test_app.state.settings = settings
    test_app.state.ingestion = mock_ingestion
    test_app.state.retriever = mock_retriever
    test_app.state.generator = mock_generator
    test_app.state.embedder = MagicMock()
    test_app.state.reranker = MagicMock()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
