from fastapi import APIRouter, Request

from app.config import settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    generator = request.app.state.generator
    ingestion = request.app.state.ingestion
    connected = await generator.is_healthy()
    stats = ingestion.get_stats()
    return HealthResponse(
        status="healthy" if connected else "degraded",
        ollama_connected=connected,
        vector_store_chunks=stats["total_chunks"],
        embedding_model=settings.embedding_model,
    )
