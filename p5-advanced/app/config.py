"""P5 Advanced configuration — Multimodal + Graph RAG settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8015
    log_level: str = "info"

    ollama_base_url: str = "http://ollama:11434"
    llm_model: str = "phi3:mini"
    embedding_model: str = "all-MiniLM-L6-v2"

    # LightRAG
    lightrag_working_dir: str = "/app/lightrag_data"
    lightrag_embedding_model: str = "nomic-embed-text:latest"

    # Demo mode
    demo_mode: bool = True
    precomputed_dir: str = "/app/precomputed"

    # Corpus
    corpus_dir: str = "/app/corpus"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
