"""RAG-P5 Advanced — Multimodal + Graph RAG with LightRAG."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.routers import ask, graph, health, ingest
from app.services.graph_export import GraphExporter
from app.services.lightrag_wrapper import LightRAGWrapper
from app.services.multimodal_ingest import MultimodalIngestor

import structlog

logger = structlog.get_logger()


LEVEL_MAP = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}


def setup_logging(level: str = "info") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            LEVEL_MAP.get(level.lower(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def _background_ingest(lightrag: LightRAGWrapper, corpus_dir: str) -> None:
    """Ingest corpus files in background after server starts."""
    corpus_path = Path(corpus_dir)
    if not corpus_path.exists():
        return

    raw_graph = lightrag.get_graph()
    if raw_graph.get("nodes"):
        logger.info("graph_already_populated", node_count=len(raw_graph["nodes"]))
        return

    files = sorted(corpus_path.glob("**/*.md")) + sorted(corpus_path.glob("**/*.txt"))
    total = len(files)
    for i, f in enumerate(files, 1):
        content = f.read_text(encoding="utf-8")
        if content.strip():
            logger.info("corpus_ingesting", file=f.name, progress=f"{i}/{total}")
            success = await lightrag.ingest(content)
            if success:
                logger.info("corpus_ingested", file=f.name, progress=f"{i}/{total}")
            else:
                logger.error("corpus_ingest_failed", file=f.name)
    logger.info("corpus_ingest_complete", total=total)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)

    # Initialize LightRAG wrapper
    lightrag = LightRAGWrapper(
        working_dir=settings.lightrag_working_dir,
        ollama_base_url=settings.ollama_base_url,
        llm_model=settings.llm_model,
        embedding_model=settings.lightrag_embedding_model,
    )
    await lightrag.initialize()

    # Graph exporter (handles demo/live mode)
    graph_exporter = GraphExporter(
        precomputed_dir=settings.precomputed_dir,
        demo_mode=settings.demo_mode,
    )

    # Multimodal ingestor
    ingestor = MultimodalIngestor(
        lightrag=lightrag,
        ollama_base_url=settings.ollama_base_url,
        model=settings.llm_model,
    )

    app.state.settings = settings
    app.state.lightrag = lightrag
    app.state.graph_exporter = graph_exporter
    app.state.ingestor = ingestor

    logger.info(
        "p5_started",
        demo_mode=settings.demo_mode,
        lightrag_initialized=lightrag.is_initialized,
        precomputed_available=graph_exporter.has_precomputed,
    )

    # Auto-ingest corpus in background (doesn't block startup)
    ingest_task = None
    if lightrag.is_initialized:
        ingest_task = asyncio.create_task(
            _background_ingest(lightrag, settings.corpus_dir)
        )

    yield

    if ingest_task and not ingest_task.done():
        ingest_task.cancel()


app = FastAPI(
    title="CloudAura RAG — P5 Advanced",
    description="Multimodal + Graph RAG with LightRAG knowledge graphs, d3.js visualization, and 5 query modes.",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(health.router)
app.include_router(ask.router)
app.include_router(graph.router)
app.include_router(ingest.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
