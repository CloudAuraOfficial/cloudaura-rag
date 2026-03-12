from fastapi import APIRouter, Request

from app.config import settings
from app.models.schemas import IngestRequest, IngestResponse, StatsResponse

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/documents", response_model=IngestResponse)
async def ingest_document(request: Request, body: IngestRequest) -> IngestResponse:
    ingestion = request.app.state.ingestion
    retriever = request.app.state.retriever

    chunks = ingestion.ingest_text(body.content, body.filename)
    retriever.refresh_index()
    stats = ingestion.get_stats()

    return IngestResponse(
        filename=body.filename,
        chunks_created=chunks,
        total_documents=stats["total_documents"],
    )


@router.get("/documents/stats", response_model=StatsResponse)
async def get_stats(request: Request) -> StatsResponse:
    ingestion = request.app.state.ingestion
    stats = ingestion.get_stats()
    return StatsResponse(
        total_documents=stats["total_documents"],
        total_chunks=stats["total_chunks"],
        embedding_model=settings.embedding_model,
        reranker_model=settings.reranker_model,
        llm_model=settings.llm_model,
    )
