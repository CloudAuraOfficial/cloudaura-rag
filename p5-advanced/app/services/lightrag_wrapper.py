"""Thin adapter around LightRAG for knowledge graph RAG."""

import os
from pathlib import Path

import structlog

logger = structlog.get_logger()


class LightRAGWrapper:
    """Wraps LightRAG to provide ingest(), query(), and get_graph() methods.

    LightRAG handles: entity extraction, graph construction, multi-hop
    traversal (local/global/hybrid/mix/naive query modes), and NanoVectorDB storage.
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

            import numpy as np
            from lightrag import LightRAG
            from lightrag.llm.ollama import ollama_model_complete
            from lightrag.utils import EmbeddingFunc

            os.makedirs(self._working_dir, exist_ok=True)

            ollama_url = self._ollama_base_url
            embed_model = self._embedding_model

            async def _embed_func(texts: list[str]) -> np.ndarray:
                import ollama as ollama_client
                client = ollama_client.AsyncClient(host=ollama_url)
                resp = await client.embed(model=embed_model, input=texts)
                return np.array(resp["embeddings"], dtype=np.float32)

            self._rag = LightRAG(
                working_dir=self._working_dir,
                llm_model_func=partial(
                    ollama_model_complete,
                    host=self._ollama_base_url,
                    options={"num_ctx": 4096, "temperature": 0.0},
                ),
                llm_model_name=self._llm_model,
                llm_model_max_async=1,
                embedding_func=EmbeddingFunc(
                    embedding_dim=768,
                    max_token_size=8192,
                    func=_embed_func,
                    model_name=self._embedding_model,
                ),
                embedding_func_max_async=2,
                # Quality tuning
                entity_extract_max_gleaning=1,
                chunk_token_size=800,
                chunk_overlap_token_size=100,
                max_entity_tokens=4000,
                max_relation_tokens=4000,
                max_parallel_insert=1,
                top_k=60,
                cosine_threshold=0.15,
                enable_llm_cache=True,
                enable_llm_cache_for_entity_extract=True,
                default_llm_timeout=600,
            )
            await self._rag.initialize_storages()
            self._initialized = True
            logger.info(
                "lightrag_initialized",
                working_dir=self._working_dir,
                llm_model=self._llm_model,
                embedding_model=self._embedding_model,
            )

        except ImportError as exc:
            logger.warning("lightrag_not_installed", error=str(exc))
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
