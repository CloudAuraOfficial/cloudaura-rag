"""Self-RAG orchestrator unit tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import RelevanceGrade, SelfCritique
from app.services.self_rag import SelfRAG
from rag_core.models.schemas import AskResponse, Citation, RetrievalResult


@pytest.fixture
def retrieval_results():
    return [
        RetrievalResult(
            chunk_id="abc123",
            document="architecture.md",
            content="Microservices architecture with event-driven communication.",
            rerank_score=0.95,
        ),
        RetrievalResult(
            chunk_id="def456",
            document="deployment.md",
            content="Unrelated deployment details.",
            rerank_score=0.40,
        ),
    ]


@pytest.fixture
def all_relevant_grades():
    return [
        RelevanceGrade(chunk_id="abc123", relevant=True, confidence=0.9, reasoning="Relevant"),
        RelevanceGrade(chunk_id="def456", relevant=True, confidence=0.8, reasoning="Relevant too"),
    ]


@pytest.fixture
def mixed_grades():
    return [
        RelevanceGrade(chunk_id="abc123", relevant=True, confidence=0.9, reasoning="Relevant"),
        RelevanceGrade(chunk_id="def456", relevant=False, confidence=0.2, reasoning="Not relevant"),
    ]


@pytest.fixture
def passing_critique():
    return SelfCritique(
        faithful=True, complete=True, hallucination_free=True,
        overall_score=0.9, reasoning="Good answer",
    )


@pytest.fixture
def failing_critique():
    return SelfCritique(
        faithful=False, complete=False, hallucination_free=False,
        overall_score=0.3, reasoning="Poor answer",
    )


@pytest.fixture
def mock_answer():
    return AskResponse(
        question="test",
        answer="The system uses microservices.",
        citations=[Citation(document="architecture.md", chunk_id="abc123", content="Micro...", score=0.95)],
        model="phi3:mini",
        retrieval_method="hybrid",
        latency_ms=100.0,
    )


@pytest.mark.asyncio
async def test_self_rag_filters_irrelevant(retrieval_results, mixed_grades, passing_critique, mock_answer):
    retriever = MagicMock()
    retriever.retrieve.return_value = retrieval_results
    generator = AsyncMock()
    generator.generate_answer.return_value = mock_answer
    generator.build_context.return_value = "context"
    grader = AsyncMock()
    grader.grade_all.return_value = mixed_grades
    checker = AsyncMock()
    checker.check.return_value = passing_critique

    self_rag = SelfRAG(retriever, generator, grader, checker)
    answer, grades, filtered, critique = await self_rag.run("test", top_k=5)

    assert answer is not None
    assert filtered == 1  # def456 was filtered
    assert len(grades) == 2
    # Generator called with only relevant results
    call_args = generator.generate_answer.call_args
    assert len(call_args.kwargs.get("results", call_args[1].get("results", []))) == 1


@pytest.mark.asyncio
async def test_self_rag_no_results(retrieval_results, mixed_grades, passing_critique):
    retriever = MagicMock()
    retriever.retrieve.return_value = []
    generator = AsyncMock()
    grader = AsyncMock()
    checker = AsyncMock()

    self_rag = SelfRAG(retriever, generator, grader, checker)
    answer, grades, filtered, critique = await self_rag.run("test", top_k=5)

    assert answer is None
    assert grades == []
    assert critique is None


@pytest.mark.asyncio
async def test_self_rag_all_irrelevant(retrieval_results):
    all_irrelevant = [
        RelevanceGrade(chunk_id="abc123", relevant=False, confidence=0.1, reasoning="No"),
        RelevanceGrade(chunk_id="def456", relevant=False, confidence=0.1, reasoning="No"),
    ]
    retriever = MagicMock()
    retriever.retrieve.return_value = retrieval_results
    generator = AsyncMock()
    grader = AsyncMock()
    grader.grade_all.return_value = all_irrelevant
    checker = AsyncMock()

    self_rag = SelfRAG(retriever, generator, grader, checker)
    answer, grades, filtered, critique = await self_rag.run("test", top_k=5)

    assert answer is None
    assert filtered == 2
    assert critique is None


@pytest.mark.asyncio
async def test_self_rag_retry_on_failing_critique(retrieval_results, all_relevant_grades, failing_critique, mock_answer):
    retriever = MagicMock()
    retriever.retrieve.return_value = retrieval_results
    generator = AsyncMock()
    generator.generate_answer.return_value = mock_answer
    generator.build_context.return_value = "context"
    grader = AsyncMock()
    grader.grade_all.return_value = all_relevant_grades
    checker = AsyncMock()
    # First check fails, second passes
    passing = SelfCritique(faithful=True, complete=True, hallucination_free=True, overall_score=0.9, reasoning="Ok")
    checker.check.side_effect = [failing_critique, passing]

    self_rag = SelfRAG(retriever, generator, grader, checker, max_retries=1)
    answer, grades, filtered, critique = await self_rag.run("test", top_k=5)

    assert answer is not None
    assert checker.check.call_count == 2


@pytest.mark.asyncio
async def test_self_rag_returns_critique(retrieval_results, all_relevant_grades, passing_critique, mock_answer):
    retriever = MagicMock()
    retriever.retrieve.return_value = retrieval_results
    generator = AsyncMock()
    generator.generate_answer.return_value = mock_answer
    generator.build_context.return_value = "context"
    grader = AsyncMock()
    grader.grade_all.return_value = all_relevant_grades
    checker = AsyncMock()
    checker.check.return_value = passing_critique

    self_rag = SelfRAG(retriever, generator, grader, checker)
    answer, grades, filtered, critique = await self_rag.run("test", top_k=5)

    assert critique is not None
    assert critique.overall_score == 0.9
    assert critique.faithful is True
