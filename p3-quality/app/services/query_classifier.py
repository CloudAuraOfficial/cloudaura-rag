"""Query classifier using Ollama LLM.

Classifies queries as no_retrieval (direct LLM answer), simple (vector-only),
or complex (full hybrid retrieval with reranking).
"""

import json

import httpx
import structlog

from app.models.schemas import QueryClassification

logger = structlog.get_logger()

CLASSIFY_PROMPT = """You are a query classifier. Given a user question, classify it into one of three categories:

1. "no_retrieval" — General knowledge questions, greetings, or requests that don't need document retrieval (e.g., "What is 2+2?", "Hello", "Define recursion")
2. "simple" — Straightforward factual questions that can be answered with a single document chunk (e.g., "What port does the app run on?", "What is the health check endpoint?")
3. "complex" — Multi-faceted questions requiring multiple sources, comparison, or synthesis (e.g., "How does the monitoring setup compare to the deployment pipeline?", "Explain the full request lifecycle")

Return ONLY a JSON object with exactly these fields:
- "category": one of "no_retrieval", "simple", "complex"
- "confidence": a float between 0.0 and 1.0
- "reasoning": a brief one-sentence explanation

Example output:
{{"category": "complex", "confidence": 0.85, "reasoning": "Question requires comparing two different system aspects"}}

Question: "{question}"
Output:"""


class QueryClassifier:
    def __init__(
        self,
        ollama_base_url: str = "http://ollama:11434",
        model: str = "phi3:mini",
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(60.0),
        )
        self._model = model

    async def close(self) -> None:
        await self._client.aclose()

    async def classify(self, question: str) -> QueryClassification:
        prompt = CLASSIFY_PROMPT.replace("{question}", question)

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
            raw = resp.json().get("response", "").strip()
            classification = self._parse_response(raw)

            logger.info(
                "query_classified",
                category=classification.category,
                confidence=classification.confidence,
            )
            return classification

        except Exception as exc:
            logger.warning("classification_failed", error=str(exc))
            return QueryClassification(
                category="complex",
                confidence=0.5,
                reasoning="Classification failed, defaulting to complex",
            )

    def _parse_response(self, raw: str) -> QueryClassification:
        raw = raw.strip()

        # Handle markdown code blocks
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        try:
            data = json.loads(raw)
            category = data.get("category", "complex")
            if category not in ("no_retrieval", "simple", "complex"):
                category = "complex"
            return QueryClassification(
                category=category,
                confidence=min(1.0, max(0.0, float(data.get("confidence", 0.5)))),
                reasoning=str(data.get("reasoning", "Parsed from LLM response")),
            )
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: look for keywords
        lower = raw.lower()
        if "no_retrieval" in lower:
            return QueryClassification(category="no_retrieval", confidence=0.6, reasoning="Keyword match fallback")
        if "simple" in lower:
            return QueryClassification(category="simple", confidence=0.6, reasoning="Keyword match fallback")

        return QueryClassification(category="complex", confidence=0.5, reasoning="Parse failed, defaulting to complex")
