"""P5 health endpoint."""

from fastapi import APIRouter, Request

from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
@router.head("/health", include_in_schema=False)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    graph_exporter = request.app.state.graph_exporter
    lightrag = request.app.state.lightrag

    # Check Ollama connectivity
    import httpx
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(settings.ollama_base_url)
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    graph = graph_exporter.get_graph(lightrag)

    return HealthResponse(
        status="healthy" if ollama_ok or settings.demo_mode else "degraded",
        ollama_connected=ollama_ok,
        demo_mode=settings.demo_mode,
        graph_nodes=graph.node_count,
        graph_edges=graph.edge_count,
    )
