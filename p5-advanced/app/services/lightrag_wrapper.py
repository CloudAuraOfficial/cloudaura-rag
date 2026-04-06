"""Thin adapter around LightRAG for knowledge graph RAG."""

import os
from pathlib import Path

import httpx
import structlog

logger = structlog.get_logger()


class LightRAGWrapper:
    """Wraps LightRAG to provide ingest(), query(), and get_graph() methods.

    LightRAG handles: entity extraction, graph construction, multi-hop
    traversal (local/global/hybrid/mix query modes), and NanoVectorDB storage.
    """

    def __init__(
        self,
        working_dir: str,
        ollama_base_url: str,
        llm_model: str,
        embedding_model: str,
    ) -> None:
        self._working_dir = working_dir
        self._ollama_base_url = ollama_base_url
        self._llm_model = llm_model
        self._embedding_model = embedding_model
        self._rag = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize LightRAG with Ollama backend."""
        try:
            from functools import partial

            from lightrag import LightRAG
            from lightrag.llm.ollama import ollama_embed

            os.makedirs(self._working_dir, exist_ok=True)

            async def _llm_func(prompt: str, **kwargs) -> str:
                async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                    resp = await client.post(
                        f"{self._ollama_base_url}/api/generate",
                        json={
                            "model": self._llm_model,
                            "prompt": prompt,
                            "stream": False,
                        },
                    )
                    resp.raise_for_status()
                    return resp.json().get("response", "")

            self._rag = LightRAG(
                working_dir=self._working_dir,
                llm_model_func=partial(_llm_func),
                embedding_func=partial(
                    ollama_embed,
                    embedding_model=self._embedding_model,
                    base_url=self._ollama_base_url,
                ),
            )
            await self._rag.initialize_storages()
            self._initialized = True
            logger.info("lightrag_initialized", working_dir=self._working_dir)

        except ImportError:
            logger.warning("lightrag_not_installed, running_without_graph_rag")
            self._initialized = False
        except Exception as exc:
            logger.error("lightrag_init_failed", error=str(exc))
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def ingest(self, text: str) -> bool:
        """Insert text into LightRAG for entity extraction and graph building."""
        if not self._initialized or not self._rag:
            logger.warning("lightrag_not_initialized, skipping_ingest")
            return False
        try:
            await self._rag.ainsert(text)
            logger.info("lightrag_ingested", length=len(text))
            return True
        except Exception as exc:
            logger.error("lightrag_ingest_failed", error=str(exc))
            return False

    async def query(
        self, question: str, mode: str = "hybrid", top_k: int = 60,
    ) -> str:
        """Query the knowledge graph using specified mode."""
        if not self._initialized or not self._rag:
            return "LightRAG is not initialized. Please check the configuration."
        try:
            from lightrag import QueryParam

            result = await self._rag.aquery(
                question,
                param=QueryParam(mode=mode, top_k=top_k),
            )
            logger.info("lightrag_queried", mode=mode, answer_length=len(result or ""))
            return result or ""
        except Exception as exc:
            logger.error("lightrag_query_failed", mode=mode, error=str(exc))
            return f"Query failed: {exc}"

    def get_graph_path(self) -> Path:
        """Get path to the GraphML file."""
        return Path(self._working_dir) / "graph_chunk_entity_relation.graphml"

    def get_graph(self) -> dict:
        """Load the NetworkX graph and return as dict {nodes, edges}."""
        graph_path = self.get_graph_path()
        if not graph_path.exists():
            return {"nodes": [], "edges": []}

        try:
            import networkx as nx
            G = nx.read_graphml(str(graph_path))
            nodes = []
            for node_id, data in G.nodes(data=True):
                nodes.append({
                    "id": node_id,
                    "label": data.get("label", node_id),
                    "type": data.get("type", "entity"),
                })
            edges = []
            for source, target, data in G.edges(data=True):
                edges.append({
                    "source": source,
                    "target": target,
                    "label": data.get("label", ""),
                    "weight": float(data.get("weight", 1.0)),
                })
            return {"nodes": nodes, "edges": edges}
        except Exception as exc:
            logger.error("graph_load_failed", error=str(exc))
            return {"nodes": [], "edges": []}
