# Pre-computed Graph Data

This directory contains pre-computed knowledge graph data and cached query
responses generated with a high-quality model for portfolio demonstration.

## Files

- `graph_data.json` — NetworkX knowledge graph exported as d3.js-compatible JSON
  (30 nodes, 39 edges covering Kubernetes, Docker, observability concepts)
- `query_cache.json` — 5 cached queries across all modes (naive/local/global/hybrid/mix)

## Generation Details

- **Model**: Claude Sonnet (claude-sonnet-4-20250514)
- **Corpus**: kubernetes.md, docker.md, observability.md (shared corpus)
- **Generated**: 2026-04-06

## How DEMO_MODE Works

- `DEMO_MODE=true` (default): `/api/graph` serves `graph_data.json`. Cached queries
  return pre-computed answers. Live queries still go through Ollama (phi3:mini).
- `DEMO_MODE=false`: Everything is live — graph and queries both use phi3:mini.

The quality difference between models is intentionally visible as a teaching point.
