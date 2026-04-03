"""RAG-P1 Foundations configuration — extends shared base settings."""

from rag_core.config import BaseRAGSettings


class Settings(BaseRAGSettings):
    """P1-specific settings. Inherits all shared fields."""

    app_port: int = 8001
    collection_name: str = "p1_documents"


settings = Settings()
