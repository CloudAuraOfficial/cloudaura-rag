"""Tests for CorrectiveRetriever — quality-driven retry logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_core.models.schemas import RetrievalResult
from app.models.schemas import QualityScore
from app.services.corrective_retriever import CorrectiveRetriever
from app.services.quality_checker import QualityChecker


@pytest.fixture
def mock_quality_pass():
    checker = MagicMock(spec=QualityChecker)
    checker.check.return_value = QualityScore(score=0.8, passed=True, details="Good")
    return checker


@pytest.fixture
def mock_quality_fail_then_pass():
    checker = MagicMock(spec=QualityChecker)
    checker.check.side_effect = [
        QualityScore(score=0.3, passed=False, details="Low quality"),
        QualityScore(score=0.75, passed=True, details="Better after expansion"),
    ]
    return checker


@pytest.fixture
def mock_quality_always_fail():
    checker = MagicMock(spec=QualityChecker)
    checker.check.return_value = QualityScore(score=0.2, passed=False, details="Still low")
    return checker


class TestCorrectiveRetriever:
    @pytest.mark.asyncio
    async def test_first_pass_succeeds(self, mock_retriever, mock_quality_pass, sample_retrieval_results):
        mock_retriever.retrieve.return_value = sample_retrieval_results
        cr = CorrectiveRetriever.__new__(CorrectiveRetriever)
        cr._retriever = mock_retriever
        cr._checker = mock_quality_pass
        cr._max_rounds = 2

        results, quality, corrections = await cr.retrieve("test query")
        assert quality.passed is True
        assert len(corrections) == 0
        mock_retriever.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_corrective_round_succeeds(self, mock_retriever, mock_quality_fail_then_pass, sample_retrieval_results):
        mock_retriever.retrieve.return_value = sample_retrieval_results
        cr = CorrectiveRetriever.__new__(CorrectiveRetriever)
        cr._retriever = mock_retriever
        cr._checker = mock_quality_fail_then_pass
        cr._client = AsyncMock()
        cr._client.post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"response": "Expanded query about Docker containers"})
        )
        cr._model = "phi3:mini"
        cr._max_rounds = 2

        results, quality, corrections = await cr.retrieve("test query")
        assert quality.passed is True
        assert len(corrections) == 1
        assert corrections[0].round == 1
        assert corrections[0].passed is True

    @pytest.mark.asyncio
    async def test_exhausts_all_rounds(self, mock_retriever, mock_quality_always_fail, sample_retrieval_results):
        mock_retriever.retrieve.return_value = sample_retrieval_results
        cr = CorrectiveRetriever.__new__(CorrectiveRetriever)
        cr._retriever = mock_retriever
        cr._checker = mock_quality_always_fail
        cr._client = AsyncMock()
        cr._client.post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"response": "Expanded query"})
        )
        cr._model = "phi3:mini"
        cr._max_rounds = 2

        results, quality, corrections = await cr.retrieve("test query")
        assert quality.passed is False
        assert len(corrections) == 2

    @pytest.mark.asyncio
    async def test_corrections_contain_expanded_query(self, mock_retriever, mock_quality_fail_then_pass, sample_retrieval_results):
        mock_retriever.retrieve.return_value = sample_retrieval_results
        cr = CorrectiveRetriever.__new__(CorrectiveRetriever)
        cr._retriever = mock_retriever
        cr._checker = mock_quality_fail_then_pass
        cr._client = AsyncMock()
        cr._client.post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={"response": "Better phrased Docker question"})
        )
        cr._model = "phi3:mini"
        cr._max_rounds = 2

        _, _, corrections = await cr.retrieve("vague query")
        assert "Better phrased Docker question" in corrections[0].expanded_query
