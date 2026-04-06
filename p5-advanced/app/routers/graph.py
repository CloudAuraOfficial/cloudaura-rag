"""P5 graph endpoint — serves knowledge graph as d3.js-compatible JSON."""

from fastapi import APIRouter, Request

from app.models.schemas import GraphData

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph", response_model=GraphData)
async def get_graph(request: Request) -> GraphData:
    graph_exporter = request.app.state.graph_exporter
    lightrag = request.app.state.lightrag
    return graph_exporter.get_graph(lightrag)
