"""P5 Advanced request/response schemas."""

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "entity"
    size: float = 1.0


class GraphLink(BaseModel):
    source: str
    target: str
    label: str = ""
    weight: float = 1.0


class GraphData(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]
    source: str = "live"
    node_count: int = 0
    edge_count: int = 0


class GraphAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    mode: str = Field(default="hybrid", pattern="^(naive|local|global|hybrid|mix)$")
    top_k: int = Field(default=60, ge=1, le=200)


class GraphAskResponse(BaseModel):
    question: str
    answer: str
    mode: str
    model: str
    latency_ms: float
    context: str | None = None


class MultimodalIngestRequest(BaseModel):
    content: str = Field(..., min_length=1)
    content_type: str = Field(default="text", pattern="^(text|image_description|table_markdown)$")
    filename: str = Field(..., min_length=1)


class MultimodalIngestResponse(BaseModel):
    filename: str
    content_type: str
    status: str


class CachedQuery(BaseModel):
    question: str
    mode: str
    answer: str
    model: str


class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    demo_mode: bool
    graph_nodes: int
    graph_edges: int
