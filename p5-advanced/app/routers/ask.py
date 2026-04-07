"""P5 ask endpoint — query the knowledge graph with mode selection."""

import asyncio
import time

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import GraphAskRequest, GraphAskResponse

QUERY_TIMEOUT_S = 30

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

        # Demo mode but query not cached — return guidance instead of 503
        if not lightrag.is_initialized:
            available = [e.get("question", "") for e in cached]
            elapsed = (time.perf_counter() - start) * 1000
            return GraphAskResponse(
                question=body.question,
                answer=(
                    "This is a demo instance with pre-computed knowledge graph queries. "
                    "Try one of the available questions, or select a different query mode. "
                    f"Available queries: {'; '.join(available)}"
                ),
                mode=body.mode,
                model="demo",
                latency_ms=round(elapsed, 1),
                context=None,
            )

    # Live query via LightRAG
    if not lightrag.is_initialized:
        # Fall back to cache if available
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
        raise HTTPException(
            status_code=503,
            detail={
                "error": "lightrag_unavailable",
                "message": "LightRAG is not initialized. Ensure Ollama is running and models are available.",
                "status_code": 503,
            },
        )

    # Skip live query if graph is empty (ingestion incomplete)
    live_graph = lightrag.get_graph()
    has_live_data = len(live_graph.get("nodes", [])) > 0

    if not has_live_data:
        cached = graph_exporter.get_cached_queries()
        for entry in cached:
            if entry.get("question", "").lower() == body.question.lower() and entry.get("mode") == body.mode:
                elapsed = (time.perf_counter() - start) * 1000
                return GraphAskResponse(
                    question=body.question,
                    answer=entry["answer"],
                    mode=body.mode,
                    model=entry.get("model", "cached-fallback"),
                    latency_ms=round(elapsed, 1),
                    context=None,
                )

    try:
        answer = await asyncio.wait_for(
            lightrag.query(body.question, mode=body.mode, top_k=body.top_k),
            timeout=QUERY_TIMEOUT_S,
        )
    except (asyncio.TimeoutError, Exception) as exc:
        # Fall back to cache on query failure or timeout
        cached = graph_exporter.get_cached_queries()
        for entry in cached:
            if entry.get("question", "").lower() == body.question.lower() and entry.get("mode") == body.mode:
                elapsed = (time.perf_counter() - start) * 1000
                return GraphAskResponse(
                    question=body.question,
                    answer=entry["answer"],
                    mode=body.mode,
                    model=entry.get("model", "cached-fallback"),
                    latency_ms=round(elapsed, 1),
                    context=None,
                )
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
