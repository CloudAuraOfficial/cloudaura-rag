"""Graph export — converts NetworkX graph to d3.js format, supports demo mode fallback."""

import json
from pathlib import Path

import structlog

from app.models.schemas import GraphData, GraphLink, GraphNode

logger = structlog.get_logger()


class GraphExporter:
    def __init__(self, precomputed_dir: str, demo_mode: bool = True) -> None:
        self._precomputed_dir = Path(precomputed_dir)
        self._demo_mode = demo_mode
        self._precomputed_graph: GraphData | None = None
        self._load_precomputed()

    def _load_precomputed(self) -> None:
        """Load pre-computed graph data if available."""
        graph_path = self._precomputed_dir / "graph_data.json"
        if not graph_path.exists():
            logger.info("no_precomputed_graph", path=str(graph_path))
            return
        try:
            with open(graph_path) as f:
                data = json.load(f)
            nodes = [GraphNode(**n) for n in data.get("nodes", [])]
            links = [GraphLink(**l) for l in data.get("links", [])]
            self._precomputed_graph = GraphData(
                nodes=nodes,
                links=links,
                source="precomputed",
                node_count=len(nodes),
                edge_count=len(links),
            )
            logger.info(
                "precomputed_graph_loaded",
                nodes=len(nodes),
                edges=len(links),
            )
        except Exception as exc:
            logger.error("precomputed_load_failed", error=str(exc))

    @property
    def has_precomputed(self) -> bool:
        return self._precomputed_graph is not None

    def get_precomputed(self) -> GraphData | None:
        return self._precomputed_graph

    def export_live(self, raw_graph: dict) -> GraphData:
        """Convert raw graph dict from LightRAG to d3.js GraphData format."""
        nodes = []
        node_ids = set()
        for n in raw_graph.get("nodes", []):
            node_id = n.get("id", "")
            if node_id and node_id not in node_ids:
                nodes.append(GraphNode(
                    id=node_id,
                    label=n.get("label", node_id),
                    type=n.get("type", "entity"),
                ))
                node_ids.add(node_id)

        links = []
        for e in raw_graph.get("edges", []):
            source = e.get("source", "")
            target = e.get("target", "")
            if source in node_ids and target in node_ids:
                links.append(GraphLink(
                    source=source,
                    target=target,
                    label=e.get("label", ""),
                    weight=float(e.get("weight", 1.0)),
                ))

        return GraphData(
            nodes=nodes,
            links=links,
            source="live",
            node_count=len(nodes),
            edge_count=len(links),
        )

    def get_graph(self, lightrag_wrapper=None) -> GraphData:
        """Get graph data — precomputed in demo mode, live otherwise."""
        if self._demo_mode and self._precomputed_graph:
            return self._precomputed_graph

        if lightrag_wrapper and lightrag_wrapper.is_initialized:
            raw = lightrag_wrapper.get_graph()
            return self.export_live(raw)

        # Fallback: empty graph
        return GraphData(
            nodes=[], links=[], source="empty",
            node_count=0, edge_count=0,
        )

    def get_cached_queries(self) -> list[dict]:
        """Load pre-computed query cache for demo."""
        cache_path = self._precomputed_dir / "query_cache.json"
        if not cache_path.exists():
            return []
        try:
            with open(cache_path) as f:
                return json.load(f)
        except Exception:
            return []
