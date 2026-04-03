"""Answer generation service using Ollama with citation enforcement."""

import time

import httpx
import structlog

from rag_core.models.schemas import AskResponse, Citation, RetrievalResult

logger = structlog.get_logger()

DEFAULT_SYSTEM_PROMPT = """You are a precise document Q&A assistant. Answer the user's question using ONLY the provided context chunks. Follow these rules strictly:

1. Base your answer exclusively on the provided context.
2. After every claim or fact, include a citation in the format [Source: filename, chunk_id].
3. If the context does not contain enough information, say "I don't have enough information in the provided documents to answer this question."
4. Be concise and direct. Do not speculate beyond what the context states.
5. If multiple sources support the same point, cite all of them."""


class GeneratorService:
    def __init__(
        self,
        ollama_base_url: str = "http://ollama:11434",
        default_model: str = "phi3:mini",
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(300.0),
        )
        self._default_model = default_model

    async def close(self) -> None:
        await self._client.aclose()

    async def is_healthy(self) -> bool:
        try:
            resp = await self._client.get("/")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def get_system_prompt(self) -> str:
        """Override in sub-projects to customize the system prompt."""
        return DEFAULT_SYSTEM_PROMPT

    def build_context(self, results: list[RetrievalResult]) -> str:
        """Override in sub-projects to customize context formatting."""
        parts = []
        for r in results:
            parts.append(
                f"[Source: {r.document}, {r.chunk_id}]\n{r.content}"
            )
        return "\n\n---\n\n".join(parts)

    def get_retrieval_method(self) -> str:
        """Override in sub-projects to describe the retrieval method used."""
        return "hybrid (BM25 + vector + cross-encoder rerank)"

    async def generate_answer(
        self,
        question: str,
        results: list[RetrievalResult],
        model: str | None = None,
    ) -> AskResponse:
        llm_model = model or self._default_model
        context = self.build_context(results)
        system_prompt = self.get_system_prompt()

        prompt = f"""Context:
{context}

Question: {question}

Answer (cite every claim with [Source: filename, chunk_id]):"""

        start = time.perf_counter()

        resp = await self._client.post(
            "/api/generate",
            json={
                "model": llm_model,
                "system": system_prompt,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1024},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        elapsed_ms = (time.perf_counter() - start) * 1000

        answer = data.get("response", "")

        citations = [
            Citation(
                document=r.document,
                chunk_id=r.chunk_id,
                content=r.content[:200],
                score=r.rerank_score or 0.0,
            )
            for r in results
        ]

        logger.info(
            "answer_generated",
            model=llm_model,
            latency_ms=round(elapsed_ms, 1),
            citations=len(citations),
            tokens=data.get("eval_count", 0),
        )

        return AskResponse(
            question=question,
            answer=answer,
            citations=citations,
            model=llm_model,
            retrieval_method=self.get_retrieval_method(),
            latency_ms=round(elapsed_ms, 1),
        )
