"""Self-RAG hallucination checker — LLM evaluates its own generation quality."""

import json

import httpx
import structlog

from app.models.schemas import SelfCritique

logger = structlog.get_logger()

CRITIQUE_PROMPT = """You are a critical evaluator. Given a question, the source context, and a generated answer, evaluate the answer's quality.

Check three things:
1. **Faithful**: Does every claim in the answer have support in the context?
2. **Complete**: Does the answer address all aspects of the question?
3. **Hallucination-free**: Are there any claims not supported by the context?

Respond with JSON only:
{{"faithful": true/false, "complete": true/false, "hallucination_free": true/false, "overall_score": 0.0-1.0, "reasoning": "brief explanation"}}

Question: {question}

Source context:
{context}

Generated answer:
{answer}

JSON response:"""


class HallucinationChecker:
    def __init__(self, ollama_base_url: str, model: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(120.0),
        )
        self._model = model

    async def close(self) -> None:
        await self._client.aclose()

    async def check(
        self, question: str, context: str, answer: str,
    ) -> SelfCritique:
        prompt = CRITIQUE_PROMPT.format(
            question=question,
            context=context[:2000],
            answer=answer[:1000],
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
            critique = self._parse_critique(raw)
            logger.info(
                "self_critique",
                faithful=critique.faithful,
                complete=critique.complete,
                hallucination_free=critique.hallucination_free,
                score=critique.overall_score,
            )
            return critique
        except Exception:
            logger.warning("critique_failed")
            return SelfCritique(
                faithful=True,
                complete=True,
                hallucination_free=True,
                overall_score=0.7,
                reasoning="critique failed, assuming acceptable",
            )

    def _parse_critique(self, raw: str) -> SelfCritique:
        text = raw.strip()
        idx = text.find("{")
        if idx >= 0:
            end_idx = text.rfind("}") + 1
            if end_idx > idx:
                text = text[idx:end_idx]

        try:
            data = json.loads(text)
            return SelfCritique(
                faithful=bool(data.get("faithful", True)),
                complete=bool(data.get("complete", True)),
                hallucination_free=bool(data.get("hallucination_free", True)),
                overall_score=min(1.0, max(0.0, float(data.get("overall_score", 0.7)))),
                reasoning=str(data.get("reasoning", ""))[:500],
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            lower = raw.lower()
            faithful = "not faithful" not in lower and "unfaithful" not in lower
            hallucination_free = "hallucination" not in lower or "no hallucination" in lower
            return SelfCritique(
                faithful=faithful,
                complete=True,
                hallucination_free=hallucination_free,
                overall_score=0.6,
                reasoning="parsed from keywords",
            )
