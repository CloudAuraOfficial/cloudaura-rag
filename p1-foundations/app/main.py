"""RAG-P1 Foundations — Simple RAG + HyDE patterns."""

from contextlib import asynccontextmanager

import chromadb
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.routers import ask
from rag_core.logging import logger, setup_logging
from rag_core.routers import documents, health
from rag_core.services.embedder import EmbeddingService
from rag_core.services.generator import GeneratorService
from rag_core.services.ingestion import IngestionService
from rag_core.services.reranker import RerankerService
from rag_core.services.retriever import HybridRetriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)

    embedder = EmbeddingService(model_name=settings.embedding_model)
    reranker = RerankerService(model_name=settings.reranker_model)

    chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    ingestion = IngestionService(
        embedder,
        chroma_client,
        collection_name=settings.collection_name,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    retriever = HybridRetriever(
        ingestion,
        embedder,
        reranker,
        bm25_top_k=settings.bm25_top_k,
        vector_top_k=settings.vector_top_k,
        rerank_top_k=settings.rerank_top_k,
    )
    generator = GeneratorService(
        ollama_base_url=settings.ollama_base_url,
        default_model=settings.llm_model,
    )

    app.state.settings = settings
    app.state.embedder = embedder
    app.state.reranker = reranker
    app.state.ingestion = ingestion
    app.state.retriever = retriever
    app.state.generator = generator

    stats = ingestion.get_stats()
    if stats["total_chunks"] == 0:
        logger.info("no_documents_found, ingesting_corpus", dir=settings.corpus_dir)
        ingestion.ingest_directory(settings.corpus_dir)
        retriever.refresh_index()

    yield

    await generator.close()


app = FastAPI(
    title="CloudAura RAG — P1 Foundations",
    description="Simple RAG + HyDE patterns with hybrid retrieval, cross-encoder reranking, and citation enforcement.",
    version="2.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(documents.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
