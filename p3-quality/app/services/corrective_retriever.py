"""Corrective retrieval — expands and retries when quality is low.

If initial retrieval quality is below threshold, the query is expanded
via LLM and retrieval is retried (up to max_rounds).
"""

import json

import httpx
import structlog

from rag_core.models.schemas import RetrievalResult
from rag_core.services.retriever import HybridRetriever

from app.models.schemas import CorrectionRound, QualityScore
from app.services.quality_checker import QualityChecker

logger = structlog.get_logger()

EXPAND_PROMPT = """The following search query did not return high-quality results. Rewrite it to be more specific, using different keywords or phrasing that might match relevant documents better.

Original query: "{query}"
Quality score: {score}

Return ONLY the rewritten query as a single line of text, nothing else."""


class CorrectiveRetriever:
    def __init__(
        self,
        retriever: HybridRetriever,
        quality_checker: QualityChecker,
        ollama_base_url: str = "http://ollama:11434",
        model: str = "phi3:mini",
        max_rounds: int = 2,
    ) -> None:
        self._retriever = retriever
        self._checker = quality_checker
        self._client = httpx.AsyncClient(
            base_url=ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(60.0),
        )
        self._model = model
        self._max_rounds = max_rounds

    async def close(self) -> None:
        await self._client.aclose()

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> tuple[list[RetrievalResult], QualityScore, list[CorrectionRound]]:
        """Retrieve with quality checking and corrective retry.

        Returns (final_results, final_quality, correction_rounds).
        """
        corrections: list[CorrectionRound] = []

        # Initial retrieval
        results = self._retriever.retrieve(query, top_k=top_k)
        quality = self._checker.check(query, results)

        if quality.passed:
            logger.info("corrective_first_pass", score=quality.score)
            return results, quality, corrections

        # Corrective rounds
        current_query = query
        for round_num in range(1, self._max_rounds + 1):
            expanded = await self._expand_query(current_query, quality.score)

            logger.info(
                "corrective_round",
                round=round_num,
                original_score=quality.score,
                expanded_query=expanded[:80],
            )

            results = self._retriever.retrieve(expanded, top_k=top_k)
            quality = self._checker.check(expanded, results)

            corrections.append(CorrectionRound(
                round=round_num,
                expanded_query=expanded,
                quality_score=quality.score,
                passed=quality.passed,
                results_count=len(results),
            ))

            if quality.passed:
                logger.info("corrective_resolved", round=round_num, score=quality.score)
                break

            current_query = expanded

        if not quality.passed:
            logger.warning("corrective_exhausted", rounds=self._max_rounds, final_score=quality.score)

        return results, quality, corrections

    async def _expand_query(self, query: str, score: float) -> str:
        prompt = EXPAND_PROMPT.replace("{query}", query).replace("{score}", f"{score:.3f}")

        try:
            resp = await self._client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            expanded = resp.json().get("response", "").strip()
            # Clean up: take first line only
            expanded = expanded.split("\n")[0].strip().strip('"')
            return expanded if expanded else query

        except Exception as exc:
            logger.warning("query_expansion_failed", error=str(exc))
            return query
