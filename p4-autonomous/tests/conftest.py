"""P4 Autonomous test fixtures."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.models.schemas import AgentStep, RelevanceGrade, SelfCritique, ToolCall
from rag_core.models.schemas import AskResponse, Citation, RetrievalResult
from rag_core.testing.conftest_base import *  # noqa: F401, F403


@pytest.fixture
def sample_grades() -> list[RelevanceGrade]:
    return [
        RelevanceGrade(
            chunk_id="abc123",
            relevant=True,
            confidence=0.9,
            reasoning="Directly discusses system architecture.",
        ),
        RelevanceGrade(
            chunk_id="def456",
            relevant=False,
            confidence=0.3,
            reasoning="Discusses unrelated deployment configuration.",
        ),
    ]


@pytest.fixture
def sample_critique() -> SelfCritique:
    return SelfCritique(
        faithful=True,
        complete=True,
        hallucination_free=True,
        overall_score=0.85,
        reasoning="Answer is well-supported by the provided context.",
    )


@pytest.fixture
def sample_agent_steps() -> list[AgentStep]:
    return [
        AgentStep(
            step=1,
            thought="Need to find relevant information",
            tool_call=ToolCall(
                tool="retrieve",
                args={"query": "system architecture"},
                result="[architecture.md, abc123]: The system uses microservices...",
            ),
            observation="[architecture.md, abc123]: The system uses microservices...",
        ),
        AgentStep(
            step=2,
            thought="Provide the final answer",
            tool_call=ToolCall(
                tool="answer",
                args={"answer": "The system uses a microservices architecture."},
                result="The system uses a microservices architecture.",
            ),
            observation="The system uses a microservices architecture.",
        ),
    ]


@pytest.fixture
def mock_grader(sample_grades):
    svc = AsyncMock()
    svc.grade_all.return_value = sample_grades
    svc.grade.side_effect = lambda q, r: sample_grades[0] if r.chunk_id == "abc123" else sample_grades[1]
    svc.close.return_value = None
    return svc


@pytest.fixture
def mock_checker(sample_critique):
    svc = AsyncMock()
    svc.check.return_value = sample_critique
    svc.close.return_value = None
    return svc


@pytest.fixture
def mock_self_rag(sample_ask_response, sample_grades, sample_critique):  # noqa: F811
    svc = AsyncMock()
    svc.run.return_value = (sample_ask_response, sample_grades, 1, sample_critique)
    return svc


@pytest.fixture
def mock_tool_registry(sample_retrieval_results):  # noqa: F811
    svc = AsyncMock()
    svc.retrieved_results = sample_retrieval_results
    svc.execute.return_value = "Tool executed successfully."
    svc.reset.return_value = None
    return svc


@pytest.fixture
def mock_agent_executor(sample_agent_steps):
    svc = AsyncMock()
    svc.run.return_value = ("The system uses microservices.", sample_agent_steps)
    svc.close.return_value = None
    return svc


@pytest.fixture
async def client(
    mock_ingestion,  # noqa: F811
    mock_retriever,  # noqa: F811
    mock_generator,  # noqa: F811
    mock_embedder,  # noqa: F811
    mock_reranker,  # noqa: F811
    mock_grader,
    mock_checker,
    mock_self_rag,
    mock_tool_registry,
    mock_agent_executor,
):
    from app.main import app

    settings = Settings()
    mock_generator._default_model = "phi3:mini"
    app.state.settings = settings
    app.state.embedder = mock_embedder
    app.state.reranker = mock_reranker
    app.state.ingestion = mock_ingestion
    app.state.retriever = mock_retriever
    app.state.generator = mock_generator
    app.state.grader = mock_grader
    app.state.checker = mock_checker
    app.state.self_rag = mock_self_rag
    app.state.tool_registry = mock_tool_registry
    app.state.agent_executor = mock_agent_executor

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
