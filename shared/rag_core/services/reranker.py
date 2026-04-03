"""Local cross-encoder reranking service."""

import structlog
from sentence_transformers import CrossEncoder

logger = structlog.get_logger()


class RerankerService:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        logger.info("loading_reranker_model", model=model_name)
        self._model = CrossEncoder(model_name)
        logger.info("reranker_model_loaded", model=model_name)

    def rerank(
        self, query: str, documents: list[dict], top_k: int = 5
    ) -> list[dict]:
        if not documents:
            return []

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
