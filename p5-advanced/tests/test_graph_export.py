"""Graph exporter unit tests."""

import json
import os
import tempfile

import pytest

from app.models.schemas import GraphData
from app.services.graph_export import GraphExporter


class TestGraphExporter:
    def test_export_live_graph(self):
        exporter = GraphExporter(precomputed_dir="/nonexistent", demo_mode=False)
        raw = {
            "nodes": [
                {"id": "a", "label": "Node A", "type": "entity"},
                {"id": "b", "label": "Node B", "type": "concept"},
            ],
            "edges": [
                {"source": "a", "target": "b", "label": "connects", "weight": 1.5},
            ],
        }
        result = exporter.export_live(raw)
        assert result.node_count == 2
        assert result.edge_count == 1
        assert result.source == "live"

    def test_export_live_deduplicates_nodes(self):
        exporter = GraphExporter(precomputed_dir="/nonexistent", demo_mode=False)
        raw = {
            "nodes": [
                {"id": "a", "label": "A"},
                {"id": "a", "label": "A duplicate"},
            ],
            "edges": [],
        }
        result = exporter.export_live(raw)
        assert result.node_count == 1

    def test_export_live_filters_dangling_edges(self):
        exporter = GraphExporter(precomputed_dir="/nonexistent", demo_mode=False)
        raw = {
            "nodes": [{"id": "a", "label": "A"}],
            "edges": [
                {"source": "a", "target": "b", "label": "broken"},
            ],
        }
        result = exporter.export_live(raw)
        assert result.edge_count == 0

    def test_load_precomputed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = os.path.join(tmpdir, "graph_data.json")
            with open(graph_path, "w") as f:
                json.dump({
                    "nodes": [{"id": "x", "label": "X", "type": "test"}],
                    "links": [],
                }, f)
            exporter = GraphExporter(precomputed_dir=tmpdir, demo_mode=True)
            assert exporter.has_precomputed
            graph = exporter.get_precomputed()
            assert graph.node_count == 1

    def test_no_precomputed_returns_none(self):
        exporter = GraphExporter(precomputed_dir="/nonexistent", demo_mode=True)
        assert not exporter.has_precomputed
        assert exporter.get_precomputed() is None

    def test_demo_mode_returns_precomputed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = os.path.join(tmpdir, "graph_data.json")
            with open(graph_path, "w") as f:
                json.dump({
                    "nodes": [{"id": "x", "label": "X", "type": "test"}],
                    "links": [],
                }, f)
            exporter = GraphExporter(precomputed_dir=tmpdir, demo_mode=True)
            result = exporter.get_graph()
            assert result.source == "precomputed"

    def test_live_mode_empty_without_lightrag(self):
        exporter = GraphExporter(precomputed_dir="/nonexistent", demo_mode=False)
        result = exporter.get_graph()
        assert result.source == "empty"

    def test_cached_queries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "query_cache.json")
            with open(cache_path, "w") as f:
                json.dump([{"question": "test?", "mode": "hybrid", "answer": "yes", "model": "test"}], f)
            exporter = GraphExporter(precomputed_dir=tmpdir, demo_mode=True)
            queries = exporter.get_cached_queries()
            assert len(queries) == 1
            assert queries[0]["answer"] == "yes"

    def test_cached_queries_missing(self):
        exporter = GraphExporter(precomputed_dir="/nonexistent", demo_mode=True)
        assert exporter.get_cached_queries() == []
