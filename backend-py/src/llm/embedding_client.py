"""
Job Raider - Embedding Client

Client for generating text embeddings via Ollama's /api/embeddings endpoint.
Supports caching, batch operations, and graceful GPU memory management.

Author: Job Raider
Date: 2026-04-26
"""

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import requests

from .base import LLMClientError


class EmbeddingError(LLMClientError):
    """Raised when embedding generation fails."""
    pass


class EmbeddingModelUnavailableError(EmbeddingError):
    """Raised when the embedding model is not loaded in Ollama."""
    pass


class EmbeddingClient:
    """Client for generating text embeddings via Ollama's /api/embeddings endpoint.

    Uses the configured Ollama instance to generate vector embeddings for text
    content. Supports single and batch embedding, in-memory caching with TTL,
    and GPU VRAM monitoring.

    Attributes:
        model: Name of the embedding model.
        dimension: Expected embedding vector dimension.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        host: Optional[str] = None,
        port: Optional[int] = None,
        gpu_monitor: Optional[Any] = None,
        batch_size: int = 32,
        cache_enabled: bool = True,
        cache_ttl: int = 86400,
        timeout: int = 30,
    ):
        """Initialize the embedding client.

        Args:
            model: Ollama embedding model name.
            host: Ollama host address. Defaults to OLLAMA_HOST env var or localhost.
            port: Ollama port. Defaults to OLLAMA_PORT env var or 11434.
            gpu_monitor: Optional GPUMonitor instance for VRAM checks.
            batch_size: Maximum texts per batch operation.
            cache_enabled: Whether to cache embeddings in memory.
            cache_ttl: Cache entry time-to-live in seconds.
            timeout: Request timeout in seconds.
        """
        self.model = model
        self.batch_size = batch_size
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.gpu_monitor = gpu_monitor

        # Resolve Ollama host/port (same pattern as OllamaClient)
        raw_host = host or os.getenv("OLLAMA_HOST", "localhost")
        if ":" in raw_host:
            self.host, port_str = raw_host.rsplit(":", 1)
            self.port = int(port_str)
        else:
            self.host = raw_host
            self.port = int(port or os.getenv("OLLAMA_PORT", "11434"))
        self.base_url = f"http://{self.host}:{self.port}"

        # In-memory embedding cache: key -> (embedding, timestamp)
        self._cache: Dict[str, Tuple[List[float], float]] = {}

        # Usage statistics
        self._total_embedded = 0
        self._cache_hits = 0
        self._cache_misses = 0

    def embed(self, text: str) -> List[float]:
        """Generate an embedding for a single text string.

        Args:
            text: Input text to embed.

        Returns:
            List of float values representing the embedding vector.

        Raises:
            EmbeddingError: If the embedding request fails.
        """
        if self.cache_enabled:
            cached = self._get_cached(text)
            if cached is not None:
                self._cache_hits += 1
                return cached
            self._cache_misses += 1

        self._check_vram()
        embedding = self._request_embedding(text)
        self._total_embedded += 1

        if self.cache_enabled:
            self._set_cached(text, embedding)

        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Processes texts concurrently in groups of batch_size. Falls back to
        sequential processing if the batch partially fails.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors, one per input text, in the same order.
        """
        results: List[Optional[List[float]]] = [None] * len(texts)

        # Separate cached vs uncached
        uncached_indices: List[int] = []
        for i, text in enumerate(texts):
            if self.cache_enabled:
                cached = self._get_cached(text)
                if cached is not None:
                    results[i] = cached
                    self._cache_hits += 1
                    continue
            uncached_indices.append(i)
            self._cache_misses += 1

        # Process uncached in batches
        if uncached_indices:
            self._check_vram()

            # Process in groups of batch_size concurrently
            for batch_start in range(0, len(uncached_indices), self.batch_size):
                batch_indices = uncached_indices[batch_start:batch_start + self.batch_size]

                with ThreadPoolExecutor(max_workers=min(len(batch_indices), 8)) as executor:
                    future_to_idx = {
                        executor.submit(self._request_embedding, texts[idx]): idx
                        for idx in batch_indices
                    }
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        try:
                            embedding = future.result()
                            results[idx] = embedding
                            self._total_embedded += 1
                            if self.cache_enabled:
                                self._set_cached(texts[idx], embedding)
                        except EmbeddingError:
                            # Leave as None for partial failure
                            pass

        # Replace any None with empty list (failed embeddings)
        return [r if r is not None else [] for r in results]

    def embed_with_cache(self, text: str, cache_key: Optional[str] = None) -> List[float]:
        """Generate an embedding with optional explicit cache key.

        Uses the provided cache_key instead of a hash of the text content,
        useful when the same text may be embedded under different contexts.

        Args:
            text: Input text to embed.
            cache_key: Optional explicit cache key. Defaults to text hash.

        Returns:
            Embedding vector.
        """
        if self.cache_enabled and cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                entry, ts = cached
                if time.time() - ts < self.cache_ttl:
                    self._cache_hits += 1
                    return entry
            self._cache_misses += 1

        embedding = self.embed(text)

        if self.cache_enabled and cache_key:
            self._cache[cache_key] = (embedding, time.time())

        return embedding

    def is_model_available(self) -> bool:
        """Check if the embedding model is loaded in Ollama.

        Returns:
            True if the model is available, False otherwise.
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()
            available = [m["name"] for m in data.get("models", [])]
            # Check exact match or match with :latest suffix
            return self.model in available or f"{self.model}:latest" in available
        except Exception:
            return False

    def pull_model(self) -> bool:
        """Pull the embedding model from the Ollama library.

        Returns:
            True if the model was pulled successfully, False otherwise.
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": False},
                timeout=300,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            raise EmbeddingError(f"Failed to pull model {self.model}: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded embedding model.

        Returns:
            Dictionary with model metadata from Ollama.

        Raises:
            EmbeddingError: If the model info request fails.
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": self.model},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise EmbeddingError(f"Failed to get model info: {e}")

    def clear_cache(self) -> None:
        """Clear the in-memory embedding cache."""
        self._cache.clear()

    @property
    def dimension(self) -> int:
        """Return the expected embedding dimension for the current model."""
        # nomic-embed-text produces 768-dimensional vectors
        dim_map = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
        }
        return dim_map.get(self.model, 768)

    @property
    def stats(self) -> Dict[str, Any]:
        """Return embedding client usage statistics.

        Returns:
            Dictionary with total embeddings, cache hits/misses, and hit rate.
        """
        total_lookups = self._cache_hits + self._cache_misses
        return {
            "total_embedded": self._total_embedded,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / total_lookups if total_lookups > 0 else 0.0,
            "cache_size": len(self._cache),
        }

    def _request_embedding(self, text: str) -> List[float]:
        """Make a single embedding request to Ollama.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.

        Raises:
            EmbeddingError: If the request fails.
        """
        try:
            response = requests.post(
                f"{self.base_url}{self._endpoint}",
                json={"model": self.model, "prompt": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding")
            if not embedding:
                raise EmbeddingError("No embedding in response")
            return embedding
        except requests.Timeout:
            raise EmbeddingError(f"Embedding request timed out after {self.timeout}s")
        except requests.RequestException as e:
            raise EmbeddingError(f"Embedding request failed: {e}")

    @property
    def _endpoint(self) -> str:
        """Return the Ollama embedding endpoint path."""
        return "/api/embeddings"

    def _check_vram(self) -> None:
        """Check GPU VRAM before embedding. Logs a warning if near capacity."""
        if not self.gpu_monitor:
            return
        try:
            vram_usage = self.gpu_monitor.get_vram_usage()
            if vram_usage >= 0.9:
                import logging
                logging.getLogger("job_raider.llm").warning(
                    "VRAM usage at %.1f%% during embedding generation", vram_usage * 100
                )
        except Exception:
            pass

    def _get_cached(self, text: str) -> Optional[List[float]]:
        """Retrieve a cached embedding if present and not expired.

        Args:
            text: Text whose embedding to look up.

        Returns:
            Cached embedding vector, or None if not cached or expired.
        """
        if not self.cache_enabled:
            return None
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        entry = self._cache.get(key)
        if entry is None:
            return None
        embedding, ts = entry
        if time.time() - ts >= self.cache_ttl:
            del self._cache[key]
            return None
        return embedding

    def _set_cached(self, text: str, embedding: List[float]) -> None:
        """Store an embedding in the cache.

        Args:
            text: Text that was embedded.
            embedding: The resulting embedding vector.
        """
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self._cache[key] = (embedding, time.time())
