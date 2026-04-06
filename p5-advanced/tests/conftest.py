"""P5 Advanced test fixtures — all LightRAG deps are mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.models.schemas import GraphData, GraphLink, GraphNode


@pytest.fixture
def sample_graph_data() -> GraphData:
    return GraphData(
        nodes=[
            GraphNode(id="kubernetes", label="Kubernetes", type="technology", size=3.0),
            GraphNode(id="docker", label="Docker", type="technology", size=2.5),
            GraphNode(id="container", label="Container", type="concept", size=2.0),
        ],
        links=[
            GraphLink(source="kubernetes", target="docker", label="runs containers from", weight=1.5),
            GraphLink(source="docker", target="container", label="creates", weight=2.0),
        ],
        source="precomputed",
        node_count=3,
        edge_count=2,
    )


@pytest.fixture
def mock_lightrag():
    svc = AsyncMock()
    svc.is_initialized = True
    svc.ingest.return_value = True
    svc.query.return_value = "Kubernetes orchestrates Docker containers across a cluster."
    svc.get_graph.return_value = {
        "nodes": [
            {"id": "kubernetes", "label": "Kubernetes", "type": "technology"},
            {"id": "docker", "label": "Docker", "type": "technology"},
        ],
        "edges": [
            {"source": "kubernetes", "target": "docker", "label": "runs", "weight": 1.5},
        ],
    }
    svc.get_graph_path.return_value = MagicMock()
    return svc


@pytest.fixture
def mock_graph_exporter(sample_graph_data):
    svc = MagicMock()
    svc.has_precomputed = True
    svc.get_precomputed.return_value = sample_graph_data
    svc.get_graph.return_value = sample_graph_data
    svc.get_cached_queries.return_value = [
        {
            "question": "What is Kubernetes?",
            "mode": "hybrid",
            "answer": "Kubernetes is a container orchestration platform.",
            "model": "cached",
        }
    ]
    return svc


@pytest.fixture
def mock_ingestor():
    svc = AsyncMock()
    svc.ingest.return_value = True
    return svc


@pytest.fixture
async def client(mock_lightrag, mock_graph_exporter, mock_ingestor):
    from app.main import app

    settings = Settings(demo_mode=True, precomputed_dir="/tmp/precomputed")
    app.state.settings = settings
    app.state.lightrag = mock_lightrag
    app.state.graph_exporter = mock_graph_exporter
    app.state.ingestor = mock_ingestor

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
