"""P4 Autonomous request/response schemas."""

from pydantic import BaseModel, Field

from rag_core.models.schemas import AskResponse, Citation


class RelevanceGrade(BaseModel):
    chunk_id: str
    relevant: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SelfCritique(BaseModel):
    faithful: bool
    complete: bool
    hallucination_free: bool
    overall_score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ToolCall(BaseModel):
    tool: str
    args: dict
    result: str | None = None


class AgentStep(BaseModel):
    step: int
    thought: str
    tool_call: ToolCall | None = None
    observation: str | None = None


class AutonomousAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    model: str | None = None
    mode: str = Field(default="self_rag", pattern="^(self_rag|agentic|both)$")


class AutonomousAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    model: str
    retrieval_method: str
    latency_ms: float
    mode: str
    # Self-RAG fields
    relevance_grades: list[RelevanceGrade] | None = None
    filtered_count: int | None = None
    critique: SelfCritique | None = None
    # Agentic RAG fields
    agent_steps: list[AgentStep] | None = None
