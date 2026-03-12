from contextlib import asynccontextmanager

import chromadb
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.logging import logger, setup_logging
from app.routers import ask, documents, health
from app.services.embedder import EmbeddingService
from app.services.generator import GeneratorService
from app.services.ingestion import IngestionService
from app.services.reranker import RerankerService
from app.services.retriever import HybridRetriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)

    embedder = EmbeddingService()
    reranker = RerankerService()

    chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)

    ingestion = IngestionService(embedder, chroma_client)
    retriever = HybridRetriever(ingestion, embedder, reranker)
    generator = GeneratorService()

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
    title="CloudAura RAG — Ask My Docs",
    description="Production RAG with hybrid retrieval, cross-encoder reranking, and citation enforcement.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(documents.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
