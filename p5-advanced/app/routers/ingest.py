"""P5 multimodal ingest endpoint."""

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import MultimodalIngestRequest, MultimodalIngestResponse

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=MultimodalIngestResponse)
async def ingest_content(request: Request, body: MultimodalIngestRequest) -> MultimodalIngestResponse:
    ingestor = request.app.state.ingestor

    if not ingestor:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ingestor_unavailable",
                "message": "Multimodal ingestor is not available.",
                "status_code": 503,
            },
        )

    success = await ingestor.ingest(
        content=body.content,
        content_type=body.content_type,
        filename=body.filename,
    )

    return MultimodalIngestResponse(
        filename=body.filename,
        content_type=body.content_type,
        status="ingested" if success else "failed",
    )
