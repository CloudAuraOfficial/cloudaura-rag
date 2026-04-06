"""Vendored modal processors from RAG Anything (HKUDS/RAG-Anything).

Only ImageModalProcessor and TableModalProcessor are included.
MinerU is excluded due to 16GB RAM minimum requirement.

These processors take pre-parsed content and produce text descriptions
via LLM calls. They do NOT depend on MinerU.

Source: https://github.com/HKUDS/RAG-Anything
License: MIT
"""

import httpx
import structlog

logger = structlog.get_logger()


class ImageModalProcessor:
    """Processes image content into text descriptions using an LLM.

    In production, this would use llava for vision-language understanding.
    Falls back to phi3:mini with a text prompt describing the image context.
    """

    def __init__(self, ollama_base_url: str, model: str = "phi3:mini") -> None:
        self._ollama_base_url = ollama_base_url
        self._model = model

    async def describe(self, image_context: str, filename: str) -> str:
        """Generate a text description from image context metadata."""
        prompt = (
            f"Given the following metadata about an image named '{filename}', "
            f"produce a detailed textual description suitable for knowledge extraction:\n\n"
            f"{image_context}\n\n"
            f"Description:"
        )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                resp = await client.post(
                    f"{self._ollama_base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 512},
                    },
                )
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
        except Exception as exc:
            logger.warning("image_processing_failed", filename=filename, error=str(exc))
            return image_context


class TableModalProcessor:
    """Processes table content into structured text using an LLM."""

    def __init__(self, ollama_base_url: str, model: str = "phi3:mini") -> None:
        self._ollama_base_url = ollama_base_url
        self._model = model

    async def extract(self, table_markdown: str, filename: str) -> str:
        """Extract structured information from a markdown table."""
        prompt = (
            f"Given the following markdown table from '{filename}', "
            f"extract and describe the key information, relationships, "
            f"and patterns in plain text:\n\n"
            f"{table_markdown}\n\n"
            f"Analysis:"
        )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                resp = await client.post(
                    f"{self._ollama_base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 512},
                    },
                )
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
        except Exception as exc:
            logger.warning("table_processing_failed", filename=filename, error=str(exc))
            return table_markdown
