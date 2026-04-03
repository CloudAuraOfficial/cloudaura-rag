"""Adaptive routing — routes queries to different retrieval strategies based on classification."""

import structlog

from rag_core.models.schemas import RetrievalResult
from rag_core.services.generator import GeneratorService
from rag_core.services.retriever import HybridRetriever

from app.models.schemas import QueryClassification
from app.services.query_classifier import QueryClassifier

logger = structlog.get_logger()


class AdaptiveRouter:
    def __init__(
        self,
        classifier: QueryClassifier,
        retriever: HybridRetriever,
        generator: GeneratorService,
    ) -> None:
        self._classifier = classifier
        self._retriever = retriever
        self._generator = generator

    async def route(
        self,
        question: str,
        top_k: int = 5,
    ) -> tuple[list[RetrievalResult], QueryClassification, str]:
        """Classify the query and route to appropriate retrieval strategy.

        Returns (results, classification, route_description).
        """
        classification = await self._classifier.classify(question)

        if classification.category == "no_retrieval":
            logger.info("adaptive_route", route="direct_llm", confidence=classification.confidence)
            return [], classification, "direct LLM (no retrieval needed)"

        if classification.category == "simple":
            # Vector-only search (skip BM25 and reranking for speed)
            logger.info("adaptive_route", route="simple_vector", confidence=classification.confidence)
            query_embedding = self._retriever._embedder.embed_query(question)
            chroma_results = self._retriever._ingestion.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._retriever._ingestion.collection.count()),
                include=["documents", "metadatas", "distances"],
            )

            results = []
            if chroma_results["ids"] and chroma_results["ids"][0]:
                for doc_id, doc, meta, dist in zip(
                    chroma_results["ids"][0],
                    chroma_results["documents"][0],
                    chroma_results["metadatas"][0],
                    chroma_results["distances"][0],
                ):
                    results.append(RetrievalResult(
                        chunk_id=doc_id,
                        document=meta.get("document", "unknown"),
                        content=doc,
                        vector_score=1.0 - float(dist),
                    ))

            return results, classification, "simple vector search (fast path)"

        # Complex: full hybrid pipeline
        logger.info("adaptive_route", route="full_hybrid", confidence=classification.confidence)
        results = self._retriever.retrieve(question, top_k=top_k)
        return results, classification, "full hybrid (BM25 + vector + RRF + rerank)"
