"""Agentic RAG tool definitions and execution."""

import math
import re

import structlog

from rag_core.models.schemas import RetrievalResult
from rag_core.services.generator import GeneratorService
from rag_core.services.retriever import HybridRetriever

logger = structlog.get_logger()

TOOL_DESCRIPTIONS = {
    "retrieve": "Search the document corpus for information. Args: {\"query\": \"search query\"}",
    "summarize": "Summarize a piece of text. Args: {\"text\": \"text to summarize\"}",
    "compare": "Compare two concepts or items. Args: {\"item_a\": \"first item\", \"item_b\": \"second item\"}",
    "calculate": "Evaluate a math expression. Args: {\"expression\": \"2 + 3 * 4\"}",
    "answer": "Provide the final answer. Args: {\"answer\": \"your final answer\"}",
}


class ToolRegistry:
    def __init__(
        self,
        retriever: HybridRetriever,
        generator: GeneratorService,
    ) -> None:
        self._retriever = retriever
        self._generator = generator
        self._retrieved_results: list[RetrievalResult] = []

    @property
    def retrieved_results(self) -> list[RetrievalResult]:
        return self._retrieved_results

    def reset(self) -> None:
        self._retrieved_results = []

    async def execute(self, tool: str, args: dict) -> str:
        handler = {
            "retrieve": self._tool_retrieve,
            "summarize": self._tool_summarize,
            "compare": self._tool_compare,
            "calculate": self._tool_calculate,
            "answer": self._tool_answer,
        }.get(tool)

        if not handler:
            logger.warning("unknown_tool", tool=tool)
            return f"Unknown tool: {tool}"

        result = await handler(args)
        logger.info("tool_executed", tool=tool, result_length=len(result))
        return result

    async def _tool_retrieve(self, args: dict) -> str:
        query = args.get("query", "")
        if not query:
            return "Error: query argument required"
        results = self._retriever.retrieve(query, top_k=5)
        self._retrieved_results.extend(results)
        if not results:
            return "No relevant documents found."
        parts = []
        for r in results:
            parts.append(f"[{r.document}, {r.chunk_id}]: {r.content[:300]}")
        return "\n\n".join(parts)

    async def _tool_summarize(self, args: dict) -> str:
        text = args.get("text", "")
        if not text:
            return "Error: text argument required"
        try:
            resp = await self._generator._client.post(
                "/api/generate",
                json={
                    "model": self._generator._default_model,
                    "prompt": f"Summarize the following text concisely:\n\n{text[:2000]}\n\nSummary:",
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception:
            return "Summarization failed."

    async def _tool_compare(self, args: dict) -> str:
        item_a = args.get("item_a", "")
        item_b = args.get("item_b", "")
        if not item_a or not item_b:
            return "Error: item_a and item_b arguments required"

        # Retrieve context for both items
        results_a = self._retriever.retrieve(item_a, top_k=3)
        results_b = self._retriever.retrieve(item_b, top_k=3)
        self._retrieved_results.extend(results_a + results_b)

        context_a = "\n".join(r.content[:200] for r in results_a) or "No information found."
        context_b = "\n".join(r.content[:200] for r in results_b) or "No information found."

        try:
            resp = await self._generator._client.post(
                "/api/generate",
                json={
                    "model": self._generator._default_model,
                    "prompt": (
                        f"Compare these two items based on the provided context:\n\n"
                        f"Item A ({item_a}):\n{context_a}\n\n"
                        f"Item B ({item_b}):\n{context_b}\n\n"
                        f"Comparison:"
                    ),
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 512},
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception:
            return "Comparison failed."

    async def _tool_calculate(self, args: dict) -> str:
        expression = args.get("expression", "")
        if not expression:
            return "Error: expression argument required"
        # Safe math evaluation
        cleaned = re.sub(r"[^0-9+\-*/().,%^ ]", "", expression)
        if not cleaned:
            return "Error: invalid expression"
        try:
            safe_env = {"__builtins__": {}, "math": math}
            result = eval(cleaned, safe_env)  # noqa: S307
            return str(result)
        except Exception:
            return f"Error: could not evaluate '{cleaned}'"

    async def _tool_answer(self, args: dict) -> str:
        return args.get("answer", "No answer provided.")
