"""Unit tests for HybridRetriever with fully mocked dependencies."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.retriever import HybridRetriever


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_retriever(mock_ingestion, mock_embedder, mock_reranker):
    """Build a HybridRetriever with mocked dependencies."""
    return HybridRetriever(mock_ingestion, mock_embedder, mock_reranker)


def _corpus_data(n=3):
    """Simulated ChromaDB .get() return value."""
    ids = [f"chunk_{i}" for i in range(n)]
    documents = [
        "The system uses microservices for scalability.",
        "Docker containers run behind an Nginx reverse proxy.",
        "Health checks are configured on every container.",
    ][:n]
    metadatas = [{"document": f"doc{i}.md", "chunk_index": i} for i in range(n)]
    return {"ids": ids, "documents": documents, "metadatas": metadatas}


def _vector_query_result(n=2):
    """Simulated ChromaDB .query() return value."""
    return {
        "ids": [[f"chunk_{i}" for i in range(n)]],
        "documents": [
            [
                "The system uses microservices for scalability.",
                "Docker containers run behind an Nginx reverse proxy.",
            ][:n]
        ],
        "metadatas": [
            [{"document": f"doc{i}.md", "chunk_index": i} for i in range(n)]
        ],
        "distances": [[0.15, 0.30][:n]],
    }


# ---------------------------------------------------------------------------
# BM25 index rebuild
# ---------------------------------------------------------------------------

class TestBM25Index:
    def test_rebuild_populates_corpus(self, mock_ingestion, mock_embedder, mock_reranker):
        data = _corpus_data()
        mock_ingestion.collection.get.return_value = data
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        retriever._rebuild_bm25_index()

        assert retriever._bm25 is not None
        assert len(retriever._bm25_corpus) == 3

    def test_rebuild_empty_corpus(self, mock_ingestion, mock_embedder, mock_reranker):
        mock_ingestion.collection.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        retriever._rebuild_bm25_index()

        assert retriever._bm25 is None
        assert retriever._bm25_corpus == []

    def test_bm25_search_returns_results(self, mock_ingestion, mock_embedder, mock_reranker):
        data = _corpus_data()
        mock_ingestion.collection.get.return_value = data
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        results = retriever._bm25_search("microservices scalability", top_k=2)

        assert len(results) <= 2
        assert all("bm25_score" in r for r in results)

    def test_bm25_search_empty_index(self, mock_ingestion, mock_embedder, mock_reranker):
        mock_ingestion.collection.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        results = retriever._bm25_search("anything", top_k=5)

        assert results == []


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------

class TestVectorSearch:
    def test_vector_search_returns_results(self, mock_ingestion, mock_embedder, mock_reranker):
        mock_ingestion.collection.query.return_value = _vector_query_result(2)
        mock_ingestion.collection.count.return_value = 3
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        results = retriever._vector_search("microservices", top_k=2)

        assert len(results) == 2
        assert all("vector_score" in r for r in results)

    def test_vector_search_converts_distance_to_similarity(
        self, mock_ingestion, mock_embedder, mock_reranker
    ):
        mock_ingestion.collection.query.return_value = _vector_query_result(1)
        mock_ingestion.collection.count.return_value = 3
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        results = retriever._vector_search("microservices", top_k=1)

        # distance 0.15 -> score 0.85
        assert abs(results[0]["vector_score"] - 0.85) < 1e-6

    def test_vector_search_empty_results(self, mock_ingestion, mock_embedder, mock_reranker):
        mock_ingestion.collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_ingestion.collection.count.return_value = 0
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        results = retriever._vector_search("anything", top_k=5)

        assert results == []


# ---------------------------------------------------------------------------
# Reciprocal rank fusion
# ---------------------------------------------------------------------------

class TestReciprocalRankFusion:
    def test_rrf_merges_results(self, mock_ingestion, mock_embedder, mock_reranker):
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        bm25 = [
            {"chunk_id": "a", "content": "A", "document": "d1.md", "bm25_score": 3.0},
            {"chunk_id": "b", "content": "B", "document": "d2.md", "bm25_score": 2.0},
        ]
        vector = [
            {"chunk_id": "b", "content": "B", "document": "d2.md", "vector_score": 0.9},
            {"chunk_id": "c", "content": "C", "document": "d3.md", "vector_score": 0.7},
        ]

        fused = retriever._reciprocal_rank_fusion(bm25, vector)

        ids = [d["chunk_id"] for d in fused]
        assert "a" in ids
        assert "b" in ids
        assert "c" in ids

    def test_rrf_shared_doc_ranks_higher(self, mock_ingestion, mock_embedder, mock_reranker):
        """A document appearing in both BM25 and vector results should rank higher."""
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        bm25 = [
            {"chunk_id": "shared", "content": "S", "document": "d.md", "bm25_score": 2.0},
            {"chunk_id": "bm25_only", "content": "B", "document": "d.md", "bm25_score": 1.0},
        ]
        vector = [
            {"chunk_id": "shared", "content": "S", "document": "d.md", "vector_score": 0.9},
            {"chunk_id": "vec_only", "content": "V", "document": "d.md", "vector_score": 0.5},
        ]

        fused = retriever._reciprocal_rank_fusion(bm25, vector)

        assert fused[0]["chunk_id"] == "shared"

    def test_rrf_assigns_fused_rank(self, mock_ingestion, mock_embedder, mock_reranker):
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        bm25 = [{"chunk_id": "x", "content": "X", "document": "d.md", "bm25_score": 1.0}]
        vector = []

        fused = retriever._reciprocal_rank_fusion(bm25, vector)

        assert fused[0]["fused_rank"] == 1

    def test_rrf_empty_inputs(self, mock_ingestion, mock_embedder, mock_reranker):
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)
        fused = retriever._reciprocal_rank_fusion([], [])
        assert fused == []


# ---------------------------------------------------------------------------
# Full retrieve pipeline
# ---------------------------------------------------------------------------

class TestRetrievePipeline:
    @patch.object(HybridRetriever, "_bm25_search")
    @patch.object(HybridRetriever, "_vector_search")
    def test_retrieve_returns_retrieval_results(
        self, mock_vector, mock_bm25, mock_ingestion, mock_embedder, mock_reranker
    ):
        mock_bm25.return_value = [
            {"chunk_id": "a", "content": "A", "document": "d.md", "bm25_score": 2.0},
        ]
        mock_vector.return_value = [
            {"chunk_id": "a", "content": "A", "document": "d.md", "vector_score": 0.9},
        ]
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        results = retriever.retrieve("test query", top_k=5)

        assert len(results) > 0
        from app.models.schemas import RetrievalResult
        assert all(isinstance(r, RetrievalResult) for r in results)

    @patch.object(HybridRetriever, "_bm25_search")
    @patch.object(HybridRetriever, "_vector_search")
    def test_retrieve_calls_reranker(
        self, mock_vector, mock_bm25, mock_ingestion, mock_embedder, mock_reranker
    ):
        mock_bm25.return_value = [
            {"chunk_id": "a", "content": "A", "document": "d.md", "bm25_score": 2.0},
        ]
        mock_vector.return_value = []
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        retriever.retrieve("test query")

        mock_reranker.rerank.assert_called_once()

    def test_refresh_index_rebuilds_bm25(self, mock_ingestion, mock_embedder, mock_reranker):
        data = _corpus_data()
        mock_ingestion.collection.get.return_value = data
        retriever = _make_retriever(mock_ingestion, mock_embedder, mock_reranker)

        retriever.refresh_index()

        assert retriever._bm25 is not None
        mock_ingestion.collection.get.assert_called()
