"""P5 ask endpoint — query the knowledge graph with mode selection."""

import time

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import GraphAskRequest, GraphAskResponse

router = APIRouter(prefix="/api", tags=["ask"])


@router.post("/ask", response_model=GraphAskResponse)
async def ask_question(request: Request, body: GraphAskRequest) -> GraphAskResponse:
    lightrag = request.app.state.lightrag
    settings = request.app.state.settings
    graph_exporter = request.app.state.graph_exporter

    start = time.perf_counter()

    # Check query cache first (demo mode)
    if settings.demo_mode:
        cached = graph_exporter.get_cached_queries()
        for entry in cached:
            if entry.get("question", "").lower() == body.question.lower() and entry.get("mode") == body.mode:
                elapsed = (time.perf_counter() - start) * 1000
                return GraphAskResponse(
                    question=body.question,
                    answer=entry["answer"],
                    mode=body.mode,
                    model=entry.get("model", "cached"),
                    latency_ms=round(elapsed, 1),
                    context=None,
                )

    # Live query via LightRAG
    if not lightrag.is_initialized:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "lightrag_unavailable",
                "message": "LightRAG is not initialized. Ensure Ollama is running and models are available.",
                "status_code": 503,
            },
        )

    try:
        answer = await lightrag.query(
            body.question, mode=body.mode, top_k=body.top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "query_error", "message": str(exc), "status_code": 502},
        ) from exc

    elapsed = (time.perf_counter() - start) * 1000

    return GraphAskResponse(
        question=body.question,
        answer=answer,
        mode=body.mode,
        model=settings.llm_model,
        latency_ms=round(elapsed, 1),
    )
