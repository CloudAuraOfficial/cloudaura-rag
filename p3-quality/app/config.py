"""RAG-P3 Quality configuration — extends shared base settings."""

from rag_core.config import BaseRAGSettings


class Settings(BaseRAGSettings):
    """P3-specific settings for adaptive and corrective RAG patterns."""

    app_port: int = 8013
    collection_name: str = "p3_documents"

    # Quality checker settings
    quality_threshold: float = 0.5
    max_correction_rounds: int = 2


settings = Settings()
