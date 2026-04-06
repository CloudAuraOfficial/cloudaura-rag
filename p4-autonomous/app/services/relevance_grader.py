"""Self-RAG relevance grading — LLM evaluates each retrieved chunk."""

import json

import httpx
import structlog

from app.models.schemas import RelevanceGrade
from rag_core.models.schemas import RetrievalResult

logger = structlog.get_logger()

GRADING_PROMPT = """You are a relevance grader. Given a user question and a retrieved document chunk, determine whether the chunk is relevant to answering the question.

Respond with JSON only:
{{"relevant": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

Question: {question}

Document chunk ({chunk_id} from {document}):
{content}

JSON response:"""


class RelevanceGrader:
    def __init__(self, ollama_base_url: str, model: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(120.0),
        )
        self._model = model

    async def close(self) -> None:
        await self._client.aclose()

    async def grade(
        self, question: str, result: RetrievalResult,
    ) -> RelevanceGrade:
        prompt = GRADING_PROMPT.format(
            question=question,
            chunk_id=result.chunk_id,
            document=result.document,
            content=result.content[:800],
        )

        try:
            resp = await self._client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            return self._parse_grade(raw, result.chunk_id)
        except Exception:
            logger.warning("grade_failed", chunk_id=result.chunk_id)
            return RelevanceGrade(
                chunk_id=result.chunk_id,
                relevant=True,
                confidence=0.5,
                reasoning="grading failed, assuming relevant",
            )

    async def grade_all(
        self, question: str, results: list[RetrievalResult],
    ) -> list[RelevanceGrade]:
        grades = []
        for result in results:
            grade = await self.grade(question, result)
            grades.append(grade)
        logger.info(
            "relevance_graded",
            total=len(grades),
            relevant=sum(1 for g in grades if g.relevant),
        )
        return grades

    def _parse_grade(self, raw: str, chunk_id: str) -> RelevanceGrade:
        text = raw.strip()
        # Try to extract JSON from response
        for start_char in ("{",):
            idx = text.find(start_char)
            if idx >= 0:
                end_idx = text.rfind("}") + 1
                if end_idx > idx:
                    text = text[idx:end_idx]
                    break

        try:
            data = json.loads(text)
            return RelevanceGrade(
                chunk_id=chunk_id,
                relevant=bool(data.get("relevant", True)),
                confidence=min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
                reasoning=str(data.get("reasoning", ""))[:500],
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Keyword fallback
            lower = raw.lower()
            relevant = "not relevant" not in lower and "irrelevant" not in lower
            return RelevanceGrade(
                chunk_id=chunk_id,
                relevant=relevant,
                confidence=0.5,
                reasoning="parsed from keywords",
            )
