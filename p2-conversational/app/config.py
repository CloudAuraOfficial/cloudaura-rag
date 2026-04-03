"""RAG-P2 Conversational configuration — extends shared base settings."""

from rag_core.config import BaseRAGSettings


class Settings(BaseRAGSettings):
    """P2-specific settings for conversational RAG patterns."""

    app_port: int = 8012
    collection_name: str = "p2_documents"

    # Memory settings
    memory_window: int = 10
    max_sessions: int = 100

    # Branched RAG settings
    max_sub_questions: int = 4
    merge_top_k: int = 10


settings = Settings()
