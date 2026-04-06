"""RAG-P4 Autonomous — Self-RAG + Agentic RAG patterns."""

from contextlib import asynccontextmanager

import chromadb
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.routers import ask
from app.services.agent_executor import AgentExecutor
from app.services.hallucination_checker import HallucinationChecker
from app.services.relevance_grader import RelevanceGrader
from app.services.self_rag import SelfRAG
from app.services.tool_registry import ToolRegistry
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

    # P4-specific: Self-RAG services
    grader = RelevanceGrader(
        ollama_base_url=settings.ollama_base_url,
        model=settings.llm_model,
    )
    checker = HallucinationChecker(
        ollama_base_url=settings.ollama_base_url,
        model=settings.llm_model,
    )
    self_rag = SelfRAG(
        retriever, generator, grader, checker,
        relevance_threshold=settings.relevance_threshold,
        hallucination_threshold=settings.hallucination_threshold,
        max_retries=settings.max_self_rag_retries,
    )

    # P4-specific: Agentic RAG services
    tool_registry = ToolRegistry(retriever, generator)
    agent_executor = AgentExecutor(
        tool_registry,
        ollama_base_url=settings.ollama_base_url,
        model=settings.llm_model,
        max_steps=settings.max_agent_steps,
    )

    app.state.settings = settings
    app.state.embedder = embedder
    app.state.reranker = reranker
    app.state.ingestion = ingestion
    app.state.retriever = retriever
    app.state.generator = generator
    app.state.grader = grader
    app.state.checker = checker
    app.state.self_rag = self_rag
    app.state.tool_registry = tool_registry
    app.state.agent_executor = agent_executor

    stats = ingestion.get_stats()
    if stats["total_chunks"] == 0:
        logger.info("no_documents_found, ingesting_corpus", dir=settings.corpus_dir)
        ingestion.ingest_directory(settings.corpus_dir)
        retriever.refresh_index()

    yield

    await generator.close()
    await grader.close()
    await checker.close()
    await agent_executor.close()


app = FastAPI(
    title="CloudAura RAG — P4 Autonomous",
    description="Self-RAG + Agentic RAG patterns with relevance grading, self-critique, and tool orchestration.",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(documents.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
