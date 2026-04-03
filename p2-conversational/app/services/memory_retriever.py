"""Memory-augmented retrieval.

Prepends conversation context to the query before retrieval,
enabling follow-up questions that reference prior turns.
"""

import structlog

from rag_core.models.schemas import RetrievalResult
from rag_core.services.retriever import HybridRetriever

from app.services.memory_store import MemoryStore

logger = structlog.get_logger()


class MemoryRetriever:
    def __init__(
        self,
        retriever: HybridRetriever,
        memory: MemoryStore,
    ) -> None:
        self._retriever = retriever
        self._memory = memory

    def retrieve(
        self,
        query: str,
        session_id: str,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        context = self._memory.get_context_string(session_id)

        if context:
            augmented_query = (
                f"Conversation context:\n{context}\n\n"
                f"Current question: {query}"
            )
            logger.info(
                "memory_augmented_query",
                session_id=session_id,
                context_turns=len(self._memory.get_history(session_id)),
                original_len=len(query),
                augmented_len=len(augmented_query),
            )
        else:
            augmented_query = query
            logger.info("memory_no_context", session_id=session_id)

        return self._retriever.retrieve(augmented_query, top_k=top_k)
