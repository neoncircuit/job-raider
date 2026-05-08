"""
Job Raider - ChromaDB Vector Store

Persistent vector store using ChromaDB for storing and querying
job listing and user profile embeddings.

Author: Job Raider
Date: 2026-04-26
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import VectorStoreConfig
from .chunker import TextChunk

logger = logging.getLogger("job_raider.rag")


class ChromaStore:
    """ChromaDB-backed vector store for job and profile embeddings.

    Uses ChromaDB's embedded PersistentClient for zero-container vector storage.
    Stores document chunks with metadata for filtering and retrieval.

    Attributes:
        config: Vector store configuration.
    """

    def __init__(
        self,
        config: VectorStoreConfig,
    ):
        """Initialize the ChromaDB vector store.

        Args:
            config: Vector store configuration with persistence path and collection names.
        """
        self.config = config
        self._client = None
        self._collections: Dict[str, Any] = {}

    def initialize(self) -> None:
        """Initialize ChromaDB client and create collections.

        Creates the persist directory if it doesn't exist, then creates
        or loads the job_listings and user_profiles collections with
        cosine distance metric.
        """
        import chromadb

        persist_dir = Path(self.config.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(persist_dir))

        # Create or get collections
        for key, name in self.config.collections.items():
            self._collections[key] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": self.config.distance_metric},
            )

        logger.info(
            "ChromaDB initialized at %s with collections: %s",
            persist_dir,
            list(self.config.collections.keys()),
        )

    def add_job(
        self,
        job_id: str,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
    ) -> None:
        """Add a job listing's chunks and embeddings to the store.

        Args:
            job_id: Unique job identifier.
            chunks: Text chunks for the job.
            embeddings: Corresponding embedding vectors.
        """
        collection = self._get_collection("jobs")
        if not collection:
            return

        ids = [f"{job_id}_chunk_{c.chunk_index}" for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "job_id": job_id,
                "source_type": "job",
                "section": c.section or "",
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def add_jobs_batch(
        self,
        job_ids: List[str],
        all_chunks: List[List[TextChunk]],
        all_embeddings: List[List[List[float]]],
    ) -> None:
        """Add multiple job listings in a single operation.

        Args:
            job_ids: List of job identifiers.
            all_chunks: List of chunk lists, one per job.
            all_embeddings: List of embedding lists, one per job.
        """
        collection = self._get_collection("jobs")
        if not collection:
            return

        all_ids: List[str] = []
        all_docs: List[str] = []
        all_embeddings_flat: List[List[float]] = []
        all_metadatas: List[Dict[str, Any]] = []

        for job_id, chunks, embeddings in zip(job_ids, all_chunks, all_embeddings):
            for chunk, embedding in zip(chunks, embeddings):
                all_ids.append(f"{job_id}_chunk_{chunk.chunk_index}")
                all_docs.append(chunk.content)
                all_embeddings_flat.append(embedding)
                all_metadatas.append({
                    "job_id": job_id,
                    "source_type": "job",
                    "section": chunk.section or "",
                    "chunk_index": chunk.chunk_index,
                })

        if all_ids:
            collection.upsert(
                ids=all_ids,
                embeddings=all_embeddings_flat,
                documents=all_docs,
                metadatas=all_metadatas,
            )

    def add_profile(
        self,
        profile_id: str,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
    ) -> None:
        """Add or update user profile embeddings.

        Uses upsert semantics, replacing existing profile chunks.

        Args:
            profile_id: Profile identifier.
            chunks: Text chunks for the profile.
            embeddings: Corresponding embedding vectors.
        """
        collection = self._get_collection("profiles")
        if not collection:
            return

        # Delete existing profile chunks first
        try:
            existing = collection.get(
                where={"profile_id": profile_id},
            )
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass

        ids = [f"profile_{profile_id}_chunk_{c.chunk_index}" for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "profile_id": profile_id,
                "source_type": "profile",
                "section": c.section or "",
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query_similar(
        self,
        query_embedding: List[float],
        collection: str = "jobs",
        n_results: int = 20,
        filter_criteria: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query for similar embeddings.

        Args:
            query_embedding: The embedding vector to compare against.
            collection: Collection key ("jobs" or "profiles").
            n_results: Maximum number of results.
            filter_criteria: Optional ChromaDB metadata filter.

        Returns:
            List of dicts with keys: id, similarity, metadata, document.
        """
        coll = self._get_collection(collection)
        if not coll:
            return []

        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if filter_criteria:
            query_kwargs["where"] = filter_criteria

        try:
            results = coll.query(**query_kwargs)
        except Exception as e:
            logger.error("ChromaDB query failed: %s", e)
            return []

        # Convert to list of dicts with cosine similarity
        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0.0
                similarity = max(0.0, 1.0 - distance)  # cosine distance -> similarity
                output.append({
                    "id": doc_id,
                    "similarity": similarity,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "document": results["documents"][0][i] if results["documents"] else "",
                })

        return output

    def get_job_embeddings(self, job_id: str) -> Optional[List[List[float]]]:
        """Retrieve all embeddings for a specific job.

        Args:
            job_id: Job identifier.

        Returns:
            List of embedding vectors, or None if job not found.
        """
        collection = self._get_collection("jobs")
        if not collection:
            return None

        try:
            results = collection.get(
                where={"job_id": job_id},
                include=["embeddings"],
            )
            if results["embeddings"] is not None and len(results["embeddings"]) > 0:
                return [e.tolist() if hasattr(e, "tolist") else e for e in results["embeddings"]]
        except Exception:
            pass
        return None

    def get_profile_embeddings(self, profile_id: str = "default") -> Optional[List[List[float]]]:
        """Retrieve all embeddings for a profile.

        Args:
            profile_id: Profile identifier.

        Returns:
            List of embedding vectors, or None if profile not found.
        """
        collection = self._get_collection("profiles")
        if not collection:
            return None

        try:
            results = collection.get(
                where={"profile_id": profile_id},
                include=["embeddings"],
            )
            if results["embeddings"] is not None and len(results["embeddings"]) > 0:
                return [e.tolist() if hasattr(e, "tolist") else e for e in results["embeddings"]]
        except Exception:
            pass
        return None

    def delete_job(self, job_id: str) -> None:
        """Remove a job and its embeddings from the store.

        Args:
            job_id: Job identifier to remove.
        """
        collection = self._get_collection("jobs")
        if not collection:
            return

        try:
            existing = collection.get(where={"job_id": job_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception as e:
            logger.error("Failed to delete job %s: %s", job_id, e)

    def delete_profile(self, profile_id: str = "default") -> None:
        """Remove a profile and its embeddings.

        Args:
            profile_id: Profile identifier to remove.
        """
        collection = self._get_collection("profiles")
        if not collection:
            return

        try:
            existing = collection.get(where={"profile_id": profile_id})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception as e:
            logger.error("Failed to delete profile %s: %s", profile_id, e)

    def job_exists(self, job_id: str) -> bool:
        """Check if a job is already stored.

        Args:
            job_id: Job identifier to check.

        Returns:
            True if the job has embeddings in the store.
        """
        collection = self._get_collection("jobs")
        if not collection:
            return False

        try:
            results = collection.get(
                where={"job_id": job_id},
                limit=1,
            )
            return len(results["ids"]) > 0
        except Exception:
            return False

    def get_collection_stats(self, collection_key: str) -> Dict[str, Any]:
        """Get statistics for a collection.

        Args:
            collection_key: Collection key ("jobs" or "profiles").

        Returns:
            Dictionary with count and collection name.
        """
        coll = self._get_collection(collection_key)
        if not coll:
            return {"count": 0, "name": ""}

        return {
            "count": coll.count(),
            "name": self.config.collections.get(collection_key, ""),
        }

    def reset_collection(self, collection_key: str) -> None:
        """Delete and recreate a collection.

        Args:
            collection_key: Collection key to reset.
        """
        if not self._client:
            return

        name = self.config.collections.get(collection_key)
        if not name:
            return

        try:
            self._client.delete_collection(name)
        except Exception:
            pass

        self._collections[collection_key] = self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": self.config.distance_metric},
        )
        logger.info("Reset collection: %s", name)

    def health_check(self) -> Dict[str, Any]:
        """Check ChromaDB health for monitoring.

        Returns:
            Dictionary with status, collection counts, and persist path.
        """
        result: Dict[str, Any] = {
            "status": "unhealthy",
            "persist_path": self.config.persist_directory,
            "collections": {},
        }

        if not self._client:
            return result

        try:
            for key in self.config.collections:
                stats = self.get_collection_stats(key)
                result["collections"][key] = stats

            result["status"] = "healthy"
        except Exception as e:
            result["error"] = str(e)

        return result

    def _get_collection(self, key: str) -> Optional[Any]:
        """Get a ChromaDB collection by key.

        Args:
            key: Collection key ("jobs" or "profiles").

        Returns:
            ChromaDB collection object, or None if not initialized.
        """
        coll = self._collections.get(key)
        if not coll:
            logger.warning("Collection '%s' not initialized", key)
        return coll
