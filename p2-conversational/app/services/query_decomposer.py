"""Query decomposition via Ollama LLM.

Splits complex questions into simpler sub-questions for parallel retrieval.
"""

import json

import httpx
import structlog

logger = structlog.get_logger()

DECOMPOSE_PROMPT = """You are a query decomposition assistant. Given a complex question, break it down into 2-4 simpler sub-questions that together would answer the original question.

Rules:
1. Each sub-question should be self-contained and searchable
2. Sub-questions should cover different aspects of the original question
3. Return ONLY a JSON array of strings, no explanation
4. If the question is already simple, return a single-element array with the original question

Example:
Question: "How does Docker compare to Kubernetes for container orchestration?"
Output: ["What is Docker and how does it handle containers?", "What is Kubernetes and how does it orchestrate containers?", "What are the key differences between Docker and Kubernetes?"]

Question: "{question}"
Output:"""


class QueryDecomposer:
    def __init__(
        self,
        ollama_base_url: str = "http://ollama:11434",
        model: str = "phi3:mini",
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(120.0),
        )
        self._model = model

    async def close(self) -> None:
        await self._client.aclose()

    async def decompose(self, question: str) -> list[str]:
        prompt = DECOMPOSE_PROMPT.replace("{question}", question)

        try:
            resp = await self._client.post(
                "/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 512},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()

            sub_questions = self._parse_response(raw)

            logger.info(
                "query_decomposed",
                original=question[:80],
                sub_questions=len(sub_questions),
            )
            return sub_questions

        except Exception as exc:
            logger.warning("decomposition_failed", error=str(exc))
            return [question]

    def _parse_response(self, raw: str) -> list[str]:
        # Try to extract JSON array from the response
        raw = raw.strip()

        # Handle markdown code blocks
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("["):
                    raw = part
                    break

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(q, str) for q in parsed):
                return [q for q in parsed if q.strip()]
        except json.JSONDecodeError:
            pass

        # Fallback: split by numbered lines
        lines = [
            line.strip().lstrip("0123456789.-) ").strip('"').strip()
            for line in raw.split("\n")
            if line.strip() and not line.strip().startswith("[") and not line.strip().startswith("]")
        ]
        if lines:
            return lines

        return [raw] if raw else []
