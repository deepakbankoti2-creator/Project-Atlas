"""
Persistent ChromaDB Vector Store for Project Atlas
Manages persistent chunk storage, deduplication via upsert, and entitlement-filtered queries.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.app.core.config import settings
from backend.app.services.embedding import OllamaEmbeddingFunction, OllamaEmbeddingService

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages persistent ChromaDB vector storage and semantic search."""

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_service: Optional[OllamaEmbeddingService] = None
    ):
        self.persist_dir = Path(persist_dir or settings.CHROMA_PERSIST_DIR)
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.embedding_service = embedding_service or OllamaEmbeddingService()
        self.embedding_function = OllamaEmbeddingFunction(self.embedding_service)

        # Ensure persistence directory exists
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize persistent ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        self._collection = None

    @property
    def collection(self):
        """Lazy-loaded Chroma collection with custom embedding function."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Store chunks idempotently.
        Existing chunks with identical IDs are updated, preventing duplicates.

        Args:
            chunks: List of chunk dictionaries containing 'chunk_id', 'text', and 'metadata'.

        Returns:
            Number of chunks processed.
        """
        if not chunks:
            return 0

        ids = [c["chunk_id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Use native Chroma upsert for automatic deduplication by stable chunk_id
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        logger.info("Successfully upserted %d chunk(s) into collection '%s'", len(chunks), self.collection_name)
        return len(chunks)

    def delete_report(self, report_id: str) -> None:
        """Delete all chunks belonging to a specific report_id."""
        try:
            self.collection.delete(where={"report_id": report_id})
            logger.info("Deleted existing chunks for report_id '%s'", report_id)
        except Exception as e:
            logger.warning("Error deleting chunks for report_id '%s': %s", report_id, e)

    def query_similar(
        self,
        query_text: str,
        n_results: int = 5,
        allowed_report_ids: Optional[List[str]] = None,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic similarity search with optional entitlement metadata filtering.

        Args:
            query_text: Query string.
            n_results: Number of top results to return.
            allowed_report_ids: Optional list of report IDs the client has purchased.
            where_filter: Additional ChromaDB where filter dict.

        Returns:
            List of matching records with id, document, metadata, and distance.
        """
        filter_clause = {}
        if allowed_report_ids:
            if len(allowed_report_ids) == 1:
                filter_clause["report_id"] = allowed_report_ids[0]
            else:
                filter_clause["report_id"] = {"$in": allowed_report_ids}

        if where_filter:
            if filter_clause:
                filter_clause = {"$and": [filter_clause, where_filter]}
            else:
                filter_clause = where_filter

        query_params: Dict[str, Any] = {
            "query_texts": [query_text],
            "n_results": n_results
        }
        if filter_clause:
            query_params["where"] = filter_clause

        raw_results = self.collection.query(**query_params)

        matches: List[Dict[str, Any]] = []
        if raw_results and raw_results["ids"] and len(raw_results["ids"][0]) > 0:
            for idx in range(len(raw_results["ids"][0])):
                matches.append({
                    "id": raw_results["ids"][0][idx],
                    "text": raw_results["documents"][0][idx] if raw_results["documents"] else "",
                    "metadata": raw_results["metadatas"][0][idx] if raw_results["metadatas"] else {},
                    "distance": raw_results["distances"][0][idx] if raw_results["distances"] else None
                })

        return matches

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic metrics about the collection."""
        count = self.collection.count()
        # Retrieve sample metadatas to find unique report_ids
        unique_reports = set()
        if count > 0:
            sample = self.collection.get(limit=min(count, 500), include=["metadatas"])
            if sample and sample.get("metadatas"):
                for m in sample["metadatas"]:
                    if m and "report_id" in m:
                        unique_reports.add(m["report_id"])

        return {
            "collection_name": self.collection_name,
            "persist_dir": str(self.persist_dir),
            "total_chunks": count,
            "indexed_reports": sorted(list(unique_reports))
        }


# Global default instance
vector_store = VectorStore()
