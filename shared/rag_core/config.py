"""Base configuration shared across all RAG sub-projects."""

from pydantic_settings import BaseSettings


class BaseRAGSettings(BaseSettings):
    """Base settings with fields common to all RAG sub-projects.

    Each sub-project extends this with project-specific settings.
    """

    app_host: str = "0.0.0.0"
    app_port: int = 8001
    log_level: str = "info"

    ollama_base_url: str = "http://ollama:11434"
    llm_model: str = "phi3:mini"

    embedding_model: str = "all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    chunk_size: int = 512
    chunk_overlap: int = 64
    bm25_top_k: int = 20
    vector_top_k: int = 20
    rerank_top_k: int = 5

    chroma_persist_dir: str = "/app/chroma_data"
    corpus_dir: str = "/app/corpus"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
