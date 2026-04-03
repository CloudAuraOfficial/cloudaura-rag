"""Quality checker — scores retrieval relevance using cross-encoder.

Evaluates whether retrieved results are relevant enough to generate
a good answer, flagging below-threshold results for correction.
"""

import structlog

from rag_core.models.schemas import RetrievalResult
from rag_core.services.reranker import RerankerService

from app.models.schemas import QualityScore

logger = structlog.get_logger()


class QualityChecker:
    def __init__(
        self,
        reranker: RerankerService,
        threshold: float = 0.5,
    ) -> None:
        self._reranker = reranker
        self._threshold = threshold

    def check(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> QualityScore:
        """Score retrieval quality. Returns QualityScore with pass/fail."""
        if not results:
            return QualityScore(
                score=0.0,
                passed=False,
                details="No results to evaluate",
            )

        # Use cross-encoder to score each result against the query
        docs = [{"content": r.content, "chunk_id": r.chunk_id} for r in results]
        scored = self._reranker.rerank(query, docs, top_k=len(docs))

        if not scored:
            return QualityScore(score=0.0, passed=False, details="Reranking produced no scores")

        scores = [doc.get("rerank_score", 0.0) for doc in scored]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)

        passed = max_score >= self._threshold

        logger.info(
            "quality_check",
            avg_score=round(avg_score, 3),
            max_score=round(max_score, 3),
            threshold=self._threshold,
            passed=passed,
            results_checked=len(results),
        )

        return QualityScore(
            score=round(max_score, 4),
            passed=passed,
            details=f"Best relevance: {max_score:.3f} (threshold: {self._threshold}), avg: {avg_score:.3f} across {len(results)} results",
        )
