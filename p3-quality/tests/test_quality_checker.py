"""Tests for QualityChecker — retrieval quality scoring."""

from unittest.mock import MagicMock

import pytest

from rag_core.models.schemas import RetrievalResult
from app.services.quality_checker import QualityChecker


@pytest.fixture
def checker():
    reranker = MagicMock()
    def _rerank(query, documents, top_k=None):
        for i, doc in enumerate(documents):
            doc["rerank_score"] = 0.8 - (i * 0.2)
        return documents
    reranker.rerank.side_effect = _rerank
    return QualityChecker(reranker, threshold=0.5)


@pytest.fixture
def low_quality_checker():
    reranker = MagicMock()
    def _rerank(query, documents, top_k=None):
        for doc in documents:
            doc["rerank_score"] = 0.2
        return documents
    reranker.rerank.side_effect = _rerank
    return QualityChecker(reranker, threshold=0.5)


class TestQualityChecker:
    def test_check_passes_good_results(self, checker, sample_retrieval_results):
        score = checker.check("test query", sample_retrieval_results)
        assert score.passed is True
        assert score.score > 0.5

    def test_check_fails_low_quality(self, low_quality_checker, sample_retrieval_results):
        score = low_quality_checker.check("test query", sample_retrieval_results)
        assert score.passed is False
        assert score.score < 0.5

    def test_check_empty_results(self, checker):
        score = checker.check("test query", [])
        assert score.passed is False
        assert score.score == 0.0

    def test_check_includes_details(self, checker, sample_retrieval_results):
        score = checker.check("test query", sample_retrieval_results)
        assert "threshold" in score.details
        assert "relevance" in score.details.lower()

    def test_check_score_is_max_not_avg(self, checker, sample_retrieval_results):
        score = checker.check("test query", sample_retrieval_results)
        # The checker returns max score as the quality score
        assert score.score == 0.8
