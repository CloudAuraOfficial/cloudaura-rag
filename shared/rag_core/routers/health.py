"""Standard /health endpoint shared across all RAG sub-projects."""

from fastapi import APIRouter, Request

from rag_core.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    generator = request.app.state.generator
    ingestion = request.app.state.ingestion
    settings = request.app.state.settings
    connected = await generator.is_healthy()
    stats = ingestion.get_stats()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        ollama_connected=connected,
        vector_store_chunks=stats["total_chunks"],
        embedding_model=settings.embedding_model,
    )
