"""Common request/response schemas shared across all RAG sub-projects."""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document: str
    chunk_id: str
    content: str
    score: float


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    model: str | None = None


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    model: str
    retrieval_method: str
    latency_ms: float


class RetrievalResult(BaseModel):
    chunk_id: str
    document: str
    content: str
    bm25_score: float | None = None
    vector_score: float | None = None
    rerank_score: float | None = None
    fused_rank: int | None = None


class DocumentInfo(BaseModel):
    name: str
    chunks: int
    size_bytes: int


class IngestRequest(BaseModel):
    content: str = Field(..., min_length=10)
    filename: str = Field(..., min_length=1)


class IngestResponse(BaseModel):
    filename: str
    chunks_created: int
    total_documents: int


class StatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    embedding_model: str
    reranker_model: str
    llm_model: str


class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    vector_store_chunks: int
    embedding_model: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    status_code: int
