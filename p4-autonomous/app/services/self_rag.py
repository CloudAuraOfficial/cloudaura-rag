"""Self-RAG orchestrator — retrieve, grade, filter, generate, self-critique."""

import structlog

from app.models.schemas import RelevanceGrade, SelfCritique
from app.services.hallucination_checker import HallucinationChecker
from app.services.relevance_grader import RelevanceGrader
from rag_core.models.schemas import AskResponse, RetrievalResult
from rag_core.services.generator import GeneratorService
from rag_core.services.retriever import HybridRetriever

logger = structlog.get_logger()


class SelfRAG:
    def __init__(
        self,
        retriever: HybridRetriever,
        generator: GeneratorService,
        grader: RelevanceGrader,
        checker: HallucinationChecker,
        relevance_threshold: float = 0.6,
        hallucination_threshold: float = 0.7,
        max_retries: int = 1,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._grader = grader
        self._checker = checker
        self._relevance_threshold = relevance_threshold
        self._hallucination_threshold = hallucination_threshold
        self._max_retries = max_retries

    async def run(
        self, question: str, top_k: int = 5, model: str | None = None,
    ) -> tuple[AskResponse | None, list[RelevanceGrade], int, SelfCritique | None]:
        """Execute Self-RAG pipeline.

        Returns:
            (answer, relevance_grades, filtered_count, critique)
        """
        # Step 1: Retrieve
        results = self._retriever.retrieve(question, top_k=top_k)
        if not results:
            return None, [], 0, None

        # Step 2: Grade relevance of each chunk
        grades = await self._grader.grade_all(question, results)

        # Step 3: Filter to only relevant chunks
        relevant_results = self._filter_relevant(results, grades)
        filtered_count = len(results) - len(relevant_results)

        logger.info(
            "self_rag_filtered",
            original=len(results),
            relevant=len(relevant_results),
            filtered=filtered_count,
        )

        if not relevant_results:
            # All chunks were irrelevant — return grades but no answer
            return None, grades, filtered_count, None

        # Step 4: Generate answer with filtered context
        answer = await self._generator.generate_answer(
            question=question,
            results=relevant_results,
            model=model,
        )

        # Step 5: Self-critique the generated answer
        context = self._generator.build_context(relevant_results)
        critique = await self._checker.check(question, context, answer.answer)

        # Step 6: If critique fails and retries available, re-retrieve with refined query
        if critique.overall_score < self._hallucination_threshold and self._max_retries > 0:
            logger.info(
                "self_rag_retry",
                score=critique.overall_score,
                threshold=self._hallucination_threshold,
            )
            refined_query = f"Provide factual details about: {question}"
            retry_results = self._retriever.retrieve(refined_query, top_k=top_k)
            if retry_results:
                retry_grades = await self._grader.grade_all(question, retry_results)
                retry_relevant = self._filter_relevant(retry_results, retry_grades)
                if retry_relevant:
                    answer = await self._generator.generate_answer(
                        question=question,
                        results=retry_relevant,
                        model=model,
                    )
                    retry_context = self._generator.build_context(retry_relevant)
                    critique = await self._checker.check(
                        question, retry_context, answer.answer,
                    )
                    grades = retry_grades
                    filtered_count = len(retry_results) - len(retry_relevant)

        return answer, grades, filtered_count, critique

    def _filter_relevant(
        self,
        results: list[RetrievalResult],
        grades: list[RelevanceGrade],
    ) -> list[RetrievalResult]:
        grade_map = {g.chunk_id: g for g in grades}
        return [
            r for r in results
            if grade_map.get(r.chunk_id, RelevanceGrade(
                chunk_id=r.chunk_id, relevant=True, confidence=0.5, reasoning="",
            )).relevant
            and grade_map.get(r.chunk_id, RelevanceGrade(
                chunk_id=r.chunk_id, relevant=True, confidence=1.0, reasoning="",
            )).confidence >= self._relevance_threshold
        ]
