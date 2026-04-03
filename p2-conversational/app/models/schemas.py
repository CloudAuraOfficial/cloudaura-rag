"""P2-specific request/response schemas for conversational RAG."""

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ConversationSession(BaseModel):
    session_id: str
    messages: list[ConversationMessage]
    created_at: str
    message_count: int


class ConversationListResponse(BaseModel):
    sessions: list[ConversationSession]
    total: int


class ConversationalAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    session_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    model: str | None = None
    mode: str = Field(default="memory", pattern="^(memory|branched|both)$")


class SubQuestion(BaseModel):
    question: str
    results_count: int


class ConversationalAskResponse(BaseModel):
    question: str
    answer: str
    citations: list
    model: str
    retrieval_method: str
    latency_ms: float
    session_id: str
    conversation_context: int
    sub_questions: list[SubQuestion] | None = None
