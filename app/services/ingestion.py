"""Document ingestion and chunking service."""

import hashlib
import os

import chromadb
import structlog
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.services.embedder import EmbeddingService

logger = structlog.get_logger()


class IngestionService:
    def __init__(
        self, embedder: EmbeddingService, chroma_client: chromadb.ClientAPI
    ) -> None:
        self._embedder = embedder
        self._collection = chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    @property
    def collection(self) -> chromadb.Collection:
        return self._collection

    def ingest_text(self, content: str, filename: str) -> int:
        chunks = self._splitter.split_text(content)
        if not chunks:
            return 0

        ids = []
        documents = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(
                f"{filename}:{i}:{chunk[:50]}".encode()
            ).hexdigest()[:12]
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append({"document": filename, "chunk_index": i})

        embeddings = self._embedder.embed(documents)

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(
            "document_ingested",
            filename=filename,
            chunks=len(chunks),
            total=self._collection.count(),
        )
        return len(chunks)

    def ingest_directory(self, directory: str) -> int:
        total_chunks = 0
        if not os.path.isdir(directory):
            logger.warning("corpus_dir_not_found", directory=directory)
            return 0

        for fname in sorted(os.listdir(directory)):
            path = os.path.join(directory, fname)
            if not os.path.isfile(path):
                continue
            if not fname.endswith((".md", ".txt", ".text")):
                continue

            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if content.strip():
                chunks = self.ingest_text(content, fname)
                total_chunks += chunks

        logger.info("corpus_ingestion_complete", total_chunks=total_chunks)
        return total_chunks

    def get_stats(self) -> dict:
        count = self._collection.count()
        all_meta = self._collection.get(include=["metadatas"])
        docs = set()
        for meta in all_meta.get("metadatas", []):
            if meta:
                docs.add(meta.get("document", "unknown"))
        return {"total_documents": len(docs), "total_chunks": count}
