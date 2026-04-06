"""P4 Autonomous configuration — Self-RAG + Agentic RAG settings."""

from rag_core.config import BaseRAGSettings


class Settings(BaseRAGSettings):
    app_port: int = 8014
    collection_name: str = "p4_documents"

    # Self-RAG
    relevance_threshold: float = 0.6
    hallucination_threshold: float = 0.7
    max_self_rag_retries: int = 1

    # Agentic RAG
    max_agent_steps: int = 5


settings = Settings()
