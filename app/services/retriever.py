"""Hybrid retrieval: BM25 + vector search with reciprocal rank fusion."""

import structlog
from rank_bm25 import BM25Okapi

from app.config import settings
from app.models.schemas import RetrievalResult
from app.services.embedder import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.reranker import RerankerService

logger = structlog.get_logger()


class HybridRetriever:
    def __init__(
        self,
        ingestion: IngestionService,
        embedder: EmbeddingService,
        reranker: RerankerService,
    ) -> None:
        self._ingestion = ingestion
        self._embedder = embedder
        self._reranker = reranker
        self._bm25: BM25Okapi | None = None
        self._bm25_corpus: list[dict] = []

    def _rebuild_bm25_index(self) -> None:
        """Rebuild BM25 index from current ChromaDB contents."""
        data = self._ingestion.collection.get(
            include=["documents", "metadatas"]
        )
        if not data["documents"]:
            self._bm25 = None
            self._bm25_corpus = []
            return

        self._bm25_corpus = []
        tokenized = []
        for doc_id, doc, meta in zip(
            data["ids"], data["documents"], data["metadatas"]
        ):
            self._bm25_corpus.append(
                {
                    "chunk_id": doc_id,
                    "content": doc,
                    "document": meta.get("document", "unknown"),
                }
            )
            tokenized.append(doc.lower().split())

        self._bm25 = BM25Okapi(tokenized)
        logger.info("bm25_index_rebuilt", corpus_size=len(self._bm25_corpus))

    def _bm25_search(self, query: str, top_k: int) -> list[dict]:
        """Keyword search using BM25."""
        if self._bm25 is None or not self._bm25_corpus:
            self._rebuild_bm25_index()
        if self._bm25 is None:
            return []

        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)

        scored = list(zip(self._bm25_corpus, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc, score in scored[:top_k]:
            results.append({**doc, "bm25_score": float(score)})
        return results

    def _vector_search(self, query: str, top_k: int) -> list[dict]:
        """Semantic search using ChromaDB."""
        query_embedding = self._embedder.embed_query(query)
        results = self._ingestion.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._ingestion.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        docs = []
        for doc_id, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            docs.append(
                {
                    "chunk_id": doc_id,
                    "content": doc,
                    "document": meta.get("document", "unknown"),
                    "vector_score": 1.0 - float(dist),
                }
            )
        return docs

    def _reciprocal_rank_fusion(
        self, bm25_results: list[dict], vector_results: list[dict], k: int = 60
    ) -> list[dict]:
        """Combine BM25 and vector results using RRF."""
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        for rank, doc in enumerate(bm25_results):
            cid = doc["chunk_id"]
            scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
            if cid not in docs:
                docs[cid] = {**doc}

        for rank, doc in enumerate(vector_results):
            cid = doc["chunk_id"]
            scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
            if cid not in docs:
                docs[cid] = {**doc}
            else:
                docs[cid]["vector_score"] = doc.get("vector_score")

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        fused = []
        for fused_rank, (cid, _) in enumerate(ranked):
            doc = docs[cid]
            doc["fused_rank"] = fused_rank + 1
            fused.append(doc)

        return fused

    def retrieve(
        self, query: str, top_k: int | None = None
    ) -> list[RetrievalResult]:
        """Full hybrid retrieval pipeline: BM25 + vector + RRF + rerank."""
        rerank_top_k = top_k or settings.rerank_top_k

        logger.info("retrieval_start", query_len=len(query))

        bm25_results = self._bm25_search(query, settings.bm25_top_k)
        vector_results = self._vector_search(query, settings.vector_top_k)

        logger.info(
            "retrieval_initial",
            bm25_hits=len(bm25_results),
            vector_hits=len(vector_results),
        )

        fused = self._reciprocal_rank_fusion(bm25_results, vector_results)

        reranked = self._reranker.rerank(query, fused, top_k=rerank_top_k)

        results = [
            RetrievalResult(
                chunk_id=doc["chunk_id"],
                document=doc["document"],
                content=doc["content"],
                bm25_score=doc.get("bm25_score"),
                vector_score=doc.get("vector_score"),
                rerank_score=doc.get("rerank_score"),
                fused_rank=doc.get("fused_rank"),
            )
            for doc in reranked
        ]

        logger.info(
            "retrieval_complete",
            results=len(results),
            top_rerank_score=results[0].rerank_score if results else None,
        )
        return results

    def refresh_index(self) -> None:
        """Force rebuild BM25 index after new documents ingested."""
        self._rebuild_bm25_index()
