"""RAG-P3 Quality — Adaptive RAG + Corrective RAG patterns."""

from contextlib import asynccontextmanager

import chromadb
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.routers import ask
from app.services.adaptive_router import AdaptiveRouter
from app.services.corrective_retriever import CorrectiveRetriever
from app.services.quality_checker import QualityChecker
from app.services.query_classifier import QueryClassifier
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
        embedder, chroma_client,
        collection_name=settings.collection_name,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    retriever = HybridRetriever(
        ingestion, embedder, reranker,
        bm25_top_k=settings.bm25_top_k,
        vector_top_k=settings.vector_top_k,
        rerank_top_k=settings.rerank_top_k,
    )
    generator = GeneratorService(
        ollama_base_url=settings.ollama_base_url,
        default_model=settings.llm_model,
    )

    # P3-specific services
    classifier = QueryClassifier(
        ollama_base_url=settings.ollama_base_url,
        model=settings.llm_model,
    )
    quality_checker = QualityChecker(
        reranker=reranker,
        threshold=settings.quality_threshold,
    )
    adaptive_router = AdaptiveRouter(classifier, retriever, generator)
    corrective_retriever = CorrectiveRetriever(
        retriever, quality_checker,
        ollama_base_url=settings.ollama_base_url,
        model=settings.llm_model,
        max_rounds=settings.max_correction_rounds,
    )

    app.state.settings = settings
    app.state.embedder = embedder
    app.state.reranker = reranker
    app.state.ingestion = ingestion
    app.state.retriever = retriever
    app.state.generator = generator
    app.state.classifier = classifier
    app.state.quality_checker = quality_checker
    app.state.adaptive_router = adaptive_router
    app.state.corrective_retriever = corrective_retriever

    stats = ingestion.get_stats()
    if stats["total_chunks"] == 0:
        logger.info("no_documents_found, ingesting_corpus", dir=settings.corpus_dir)
        ingestion.ingest_directory(settings.corpus_dir)
        retriever.refresh_index()

    yield

    await generator.close()
    await classifier.close()
    await corrective_retriever.close()


app = FastAPI(
    title="CloudAura RAG — P3 Quality",
    description="Adaptive RAG + Corrective RAG patterns with query classification and quality-driven retry loops.",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(documents.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
