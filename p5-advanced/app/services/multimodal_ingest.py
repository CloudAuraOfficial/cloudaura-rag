"""Multimodal ingestion — processes images and tables into text for LightRAG."""

import structlog

from app.services.lightrag_wrapper import LightRAGWrapper

logger = structlog.get_logger()


class MultimodalIngestor:
    """Accepts pre-parsed content (image descriptions, table markdown) and
    feeds them into LightRAG for entity extraction and graph building.

    Vendored processors from RAG Anything are used for:
    - Images: base64 → description via LLM (llava or phi3:mini)
    - Tables: markdown → structured extraction via LLM
    """

    def __init__(self, lightrag: LightRAGWrapper, ollama_base_url: str, model: str) -> None:
        self._lightrag = lightrag
        self._ollama_base_url = ollama_base_url
        self._model = model

    async def ingest_text(self, content: str, filename: str) -> bool:
        """Ingest plain text content."""
        enriched = f"Document: {filename}\n\n{content}"
        return await self._lightrag.ingest(enriched)

    async def ingest_image_description(self, description: str, filename: str) -> bool:
        """Ingest a pre-generated image description."""
        enriched = (
            f"Image: {filename}\n"
            f"Visual Description: {description}"
        )
        return await self._lightrag.ingest(enriched)

    async def ingest_table(self, table_markdown: str, filename: str) -> bool:
        """Ingest a markdown table with contextual enrichment."""
        enriched = (
            f"Table: {filename}\n"
            f"Structured Data:\n{table_markdown}"
        )
        return await self._lightrag.ingest(enriched)

    async def ingest(self, content: str, content_type: str, filename: str) -> bool:
        """Route to appropriate ingestion method."""
        handler = {
            "text": self.ingest_text,
            "image_description": self.ingest_image_description,
            "table_markdown": self.ingest_table,
        }.get(content_type, self.ingest_text)

        success = await handler(content, filename)
        logger.info(
            "multimodal_ingested",
            filename=filename,
            content_type=content_type,
            success=success,
        )
        return success
