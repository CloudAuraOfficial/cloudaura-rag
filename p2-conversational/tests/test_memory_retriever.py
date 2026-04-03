"""Tests for MemoryRetriever — conversation-augmented retrieval."""

from unittest.mock import MagicMock, call

import pytest

from rag_core.models.schemas import RetrievalResult
from app.services.memory_retriever import MemoryRetriever
from app.services.memory_store import MemoryStore


@pytest.fixture
def mock_base_retriever(sample_retrieval_results):
    r = MagicMock()
    r.retrieve.return_value = sample_retrieval_results
    return r


@pytest.fixture
def memory_retriever(mock_base_retriever, memory):
    return MemoryRetriever(mock_base_retriever, memory)


class TestMemoryRetriever:
    def test_retrieve_no_history(self, memory_retriever, mock_base_retriever, memory):
        sid = memory.create_session()
        results = memory_retriever.retrieve("What is Docker?", sid)
        assert len(results) > 0
        # Without history, query should be passed as-is
        args = mock_base_retriever.retrieve.call_args
        assert "What is Docker?" in args[0][0]

    def test_retrieve_with_history(self, memory_retriever, mock_base_retriever, memory):
        sid = memory.create_session()
        memory.add_message(sid, "user", "Tell me about Docker")
        memory.add_message(sid, "assistant", "Docker is a container platform.")

        results = memory_retriever.retrieve("What about its networking?", sid)
        assert len(results) > 0
        # With history, query should be augmented
        augmented = mock_base_retriever.retrieve.call_args[0][0]
        assert "Conversation context:" in augmented
        assert "Tell me about Docker" in augmented
        assert "What about its networking?" in augmented

    def test_retrieve_passes_top_k(self, memory_retriever, mock_base_retriever, memory):
        sid = memory.create_session()
        memory_retriever.retrieve("Test query", sid, top_k=3)
        mock_base_retriever.retrieve.assert_called_once()
        assert mock_base_retriever.retrieve.call_args[1]["top_k"] == 3

    def test_retrieve_returns_retrieval_results(self, memory_retriever, memory):
        sid = memory.create_session()
        results = memory_retriever.retrieve("Query", sid)
        assert all(isinstance(r, RetrievalResult) for r in results)
