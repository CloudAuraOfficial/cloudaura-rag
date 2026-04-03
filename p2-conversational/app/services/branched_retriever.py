"""Branched retrieval — parallel retrieval per sub-question, merge + deduplicate + rerank.

Decomposes complex queries into sub-questions, retrieves for each in parallel,
then merges and deduplicates results before final reranking.
"""

import asyncio
import time

import structlog

from rag_core.models.schemas import RetrievalResult
from rag_core.services.reranker import RerankerService
from rag_core.services.retriever import HybridRetriever

from app.services.query_decomposer import QueryDecomposer

logger = structlog.get_logger()


class BranchedRetriever:
    def __init__(
        self,
        retriever: HybridRetriever,
        decomposer: QueryDecomposer,
        reranker: RerankerService,
        merge_top_k: int = 10,
    ) -> None:
        self._retriever = retriever
        self._decomposer = decomposer
        self._reranker = reranker
        self._merge_top_k = merge_top_k

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
    ) -> tuple[list[RetrievalResult], list[dict]]:
        """Decompose, retrieve per branch, merge, rerank.

        Returns (final_results, sub_question_info).
        """
        start = time.perf_counter()
        final_top_k = top_k or 5

        sub_questions = await self._decomposer.decompose(query)
        if not sub_questions:
            sub_questions = [query]

        logger.info(
            "branched_retrieval_start",
            original_query=query[:80],
            branches=len(sub_questions),
        )

        # Retrieve for each sub-question (run in thread pool since retriever is sync)
        loop = asyncio.get_event_loop()
        branch_results = await asyncio.gather(*[
            loop.run_in_executor(
                None, self._retriever.retrieve, sq, self._merge_top_k
            )
            for sq in sub_questions
        ])

        # Build sub-question info for response
        sub_question_info = [
            {"question": sq, "results_count": len(results)}
            for sq, results in zip(sub_questions, branch_results)
        ]

        # Merge and deduplicate
        seen: dict[str, RetrievalResult] = {}
        for results in branch_results:
            for r in results:
                if r.chunk_id not in seen:
                    seen[r.chunk_id] = r
                else:
                    existing = seen[r.chunk_id]
                    # Keep higher rerank score
                    if (r.rerank_score or 0) > (existing.rerank_score or 0):
                        seen[r.chunk_id] = r

        merged = list(seen.values())

        logger.info(
            "branched_merge_complete",
            total_retrieved=sum(len(r) for r in branch_results),
            after_dedup=len(merged),
        )

        # Final rerank against original query
        if merged:
            docs_for_rerank = [
                {
                    "chunk_id": r.chunk_id,
                    "document": r.document,
                    "content": r.content,
                }
                for r in merged
            ]
            reranked = self._reranker.rerank(query, docs_for_rerank, top_k=final_top_k)
            final = [
                RetrievalResult(
                    chunk_id=doc["chunk_id"],
                    document=doc["document"],
                    content=doc["content"],
                    rerank_score=doc.get("rerank_score"),
                )
                for doc in reranked
            ]
        else:
            final = []

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "branched_retrieval_complete",
            branches=len(sub_questions),
            final_results=len(final),
            latency_ms=round(elapsed_ms, 1),
        )

        return final, sub_question_info
