"""Local embedding service using sentence-transformers."""

import structlog
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = structlog.get_logger()


class EmbeddingService:
    def __init__(self, model_name: str | None = None) -> None:
        name = model_name or settings.embedding_model
        logger.info("loading_embedding_model", model=name)
        self._model = SentenceTransformer(name)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info("embedding_model_loaded", model=name, dimension=self._dimension)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]
