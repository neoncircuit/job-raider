"""
Job Raider - Response Cache

This module provides caching functionality for LLM responses
to avoid redundant API calls and improve performance.

Author: Job Raider
Date: 2026-04-20
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Union

from ..llm.base import LLMResponse, Message


@dataclass
class CacheEntry:
    """A cached response entry."""

    key: str
    response: LLMResponse
    timestamp: float
    ttl: int  # Time to live in seconds

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.timestamp > self.ttl

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "response": asdict(self.response),
            "timestamp": self.timestamp,
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create CacheEntry from dictionary."""
        response_data = data["response"]
        response = LLMResponse(**response_data)
        return cls(
            key=data["key"],
            response=response,
            timestamp=data["timestamp"],
            ttl=data["ttl"],
        )


class ResponseCache:
    """
    Cache for LLM responses.

    Supports in-memory and file-based caching with automatic expiration.
    """

    def __init__(
        self,
        enabled: bool = True,
        ttl: int = 3600,
        max_size: int = 1000,
        backend: str = "memory",
        cache_path: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize the response cache.

        Args:
            enabled: Whether caching is enabled
            ttl: Default time-to-live for cache entries (seconds)
            max_size: Maximum number of entries in cache
            backend: Cache backend ("memory" or "file")
            cache_path: Path to cache file (for file backend)
        """
        self.enabled = enabled
        self.ttl = ttl
        self.max_size = max_size
        self.backend = backend
        self.cache_path = (
            Path(cache_path) if cache_path else Path("data/cache/llm_cache.json")
        )

        self._memory_cache: Dict[str, CacheEntry] = {}
        self._file_cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()

        # Load existing cache from file if backend is file
        if self.backend == "file" and self.cache_path.exists():
            self._load_from_file()

    def _generate_key(
        self,
        messages: List[Message],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Generate a cache key from request parameters.

        Args:
            messages: List of messages
            model: Model name
            temperature: Temperature setting
            max_tokens: Max tokens setting

        Returns:
            Cache key (hash)
        """
        # Create a normalized representation of the request
        request_data = {
            "messages": [
                {"role": msg.role.value, "content": msg.content} for msg in messages
            ],
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Serialize and hash
        request_str = json.dumps(request_data, sort_keys=True)
        return hashlib.sha256(request_str.encode()).hexdigest()

    def get(
        self,
        messages: List[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Optional[LLMResponse]:
        """
        Get a cached response if available and not expired.

        Args:
            messages: List of messages
            model: Model name
            temperature: Temperature setting
            max_tokens: Max tokens setting

        Returns:
            Cached LLMResponse if found, None otherwise
        """
        if not self.enabled:
            return None

        key = self._generate_key(messages, model, temperature, max_tokens)

        with self._lock:
            # Check memory cache first
            if self.backend == "memory":
                entry = self._memory_cache.get(key)
            else:
                entry = self._file_cache.get(key)

            if entry is None:
                return None

            if entry.is_expired():
                # Remove expired entry
                if self.backend == "memory":
                    del self._memory_cache[key]
                else:
                    del self._file_cache[key]
                    self._save_to_file()
                return None

            # Mark as cached
            response = entry.response
            response.cached = True
            return response

    def set(
        self,
        messages: List[Message],
        response: LLMResponse,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Cache a response.

        Args:
            messages: List of messages
            response: Response to cache
            model: Model name
            temperature: Temperature setting
            max_tokens: Max tokens setting
            ttl: Time-to-live in seconds (defaults to instance ttl)
        """
        if not self.enabled:
            return

        key = self._generate_key(messages, model, temperature, max_tokens)
        entry_ttl = ttl or self.ttl

        with self._lock:
            # Create cache entry
            entry = CacheEntry(
                key=key,
                response=response,
                timestamp=time.time(),
                ttl=entry_ttl,
            )

            # Add to cache
            if self.backend == "memory":
                self._memory_cache[key] = entry

                # Enforce max size
                if len(self._memory_cache) > self.max_size:
                    # Remove oldest entry
                    oldest_key = min(
                        self._memory_cache.keys(),
                        key=lambda k: self._memory_cache[k].timestamp,
                    )
                    del self._memory_cache[oldest_key]
            else:
                self._file_cache[key] = entry

                # Enforce max size
                if len(self._file_cache) > self.max_size:
                    oldest_key = min(
                        self._file_cache.keys(),
                        key=lambda k: self._file_cache[k].timestamp,
                    )
                    del self._file_cache[oldest_key]

                self._save_to_file()

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._memory_cache.clear()
            self._file_cache.clear()

            if self.backend == "file" and self.cache_path.exists():
                self.cache_path.unlink()

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        removed = 0

        with self._lock:
            cache = self._memory_cache if self.backend == "memory" else self._file_cache

            expired_keys = [key for key, entry in cache.items() if entry.is_expired()]

            for key in expired_keys:
                del cache[key]
                removed += 1

            if self.backend == "file" and removed > 0:
                self._save_to_file()

        return removed

    def _load_from_file(self) -> None:
        """Load cache from file."""
        try:
            with open(self.cache_path, "r") as f:
                data = json.load(f)

            for entry_data in data:
                entry = CacheEntry.from_dict(entry_data)
                if not entry.is_expired():
                    self._file_cache[entry.key] = entry

        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Failed to load cache from file: {e}")

    def _save_to_file(self) -> None:
        """Save cache to file."""
        try:
            # Ensure directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert entries to dict
            data = [entry.to_dict() for entry in self._file_cache.values()]

            with open(self.cache_path, "w") as f:
                json.dump(data, f, indent=2)

        except (IOError, TypeError) as e:
            print(f"Failed to save cache to file: {e}")

    @property
    def size(self) -> int:
        """Return the number of cached entries."""
        if self.backend == "memory":
            return len(self._memory_cache)
        return len(self._file_cache)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        cache = self._memory_cache if self.backend == "memory" else self._file_cache

        total_entries = len(cache)
        expired_entries = sum(1 for entry in cache.values() if entry.is_expired())

        return {
            "enabled": self.enabled,
            "backend": self.backend,
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "valid_entries": total_entries - expired_entries,
            "max_size": self.max_size,
            "ttl": self.ttl,
            "cache_path": str(self.cache_path) if self.backend == "file" else None,
        }


# Singleton instance for easy access
_default_cache: Optional[ResponseCache] = None


def get_cache(
    enabled: bool = True,
    ttl: int = 3600,
    max_size: int = 1000,
    backend: str = "memory",
    cache_path: Optional[Union[str, Path]] = None,
) -> ResponseCache:
    """
    Get the default response cache instance.

    Args:
        enabled: Whether caching is enabled
        ttl: Time-to-live for cache entries
        max_size: Maximum cache size
        backend: Cache backend
        cache_path: Path to cache file

    Returns:
        ResponseCache instance
    """
    global _default_cache
    if _default_cache is None:
        _default_cache = ResponseCache(
            enabled=enabled,
            ttl=ttl,
            max_size=max_size,
            backend=backend,
            cache_path=cache_path,
        )
    return _default_cache
