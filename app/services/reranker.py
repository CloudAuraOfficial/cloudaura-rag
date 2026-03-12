"""Local cross-encoder reranking service."""

import structlog
from sentence_transformers import CrossEncoder

from app.config import settings

logger = structlog.get_logger()


class RerankerService:
    def __init__(self, model_name: str | None = None) -> None:
        name = model_name or settings.reranker_model
        logger.info("loading_reranker_model", model=name)
        self._model = CrossEncoder(name)
        logger.info("reranker_model_loaded", model=name)

    def rerank(
        self, query: str, documents: list[dict], top_k: int | None = None
    ) -> list[dict]:
        if not documents:
            return []

        top_k = top_k or settings.rerank_top_k
        pairs = [(query, doc["content"]) for doc in documents]
        scores = self._model.predict(pairs)

        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        ranked = sorted(documents, key=lambda x: x["rerank_score"], reverse=True)
        logger.info(
            "reranking_complete",
            input_docs=len(documents),
            output_docs=min(top_k, len(ranked)),
            top_score=ranked[0]["rerank_score"] if ranked else 0,
        )
        return ranked[:top_k]
