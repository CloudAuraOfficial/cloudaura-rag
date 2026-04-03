"""P3-specific schemas for adaptive and corrective RAG."""

from pydantic import BaseModel, Field


class QueryClassification(BaseModel):
    category: str  # "no_retrieval", "simple", "complex"
    confidence: float
    reasoning: str


class QualityScore(BaseModel):
    score: float
    passed: bool
    details: str


class CorrectionRound(BaseModel):
    round: int
    expanded_query: str
    quality_score: float
    passed: bool
    results_count: int


class AdaptiveAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    model: str | None = None
    mode: str = Field(default="adaptive", pattern="^(adaptive|corrective|both)$")


class AdaptiveAskResponse(BaseModel):
    question: str
    answer: str
    citations: list
    model: str
    retrieval_method: str
    latency_ms: float
    classification: QueryClassification | None = None
    quality: QualityScore | None = None
    corrections: list[CorrectionRound] | None = None
    route_taken: str | None = None
