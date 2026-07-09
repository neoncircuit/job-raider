"""Unit tests for the EmbeddingClient."""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.llm.embedding_client import EmbeddingClient, EmbeddingError


class TestEmbedSingle:
    """Tests for single text embedding."""

    @patch("src.llm.embedding_client.requests.post")
    def test_returns_embedding_vector(self, mock_post):
        """Embed should return a list of floats from the API."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"embedding": [0.1] * 768}

        client = EmbeddingClient(model="nomic-embed-text", cache_enabled=False)
        result = client.embed("hello world")

        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)
        mock_post.assert_called_once()

    @patch("src.llm.embedding_client.requests.post")
    def test_caches_result(self, mock_post):
        """Second embed call with same text should hit cache."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"embedding": [0.1] * 768}

        client = EmbeddingClient(
            model="nomic-embed-text", cache_enabled=True, cache_ttl=60
        )
        r1 = client.embed("hello")
        r2 = client.embed("hello")

        assert r1 == r2
        assert mock_post.call_count == 1  # only one API call
        assert client.stats["cache_hits"] == 1

    @patch("src.llm.embedding_client.requests.post")
    def test_cache_expires(self, mock_post):
        """Cache entries should expire after TTL."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"embedding": [0.1] * 768}

        client = EmbeddingClient(
            model="nomic-embed-text", cache_enabled=True, cache_ttl=0
        )
        client.embed("hello")
        # TTL=0 means immediately expired
        client.embed("hello")

        assert mock_post.call_count == 2


class TestEmbedBatch:
    """Tests for batch embedding."""

    @patch("src.llm.embedding_client.requests.post")
    def test_embeds_multiple_texts(self, mock_post):
        """Batch should embed all provided texts."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"embedding": [0.1] * 768}

        client = EmbeddingClient(model="nomic-embed-text", cache_enabled=False)
        results = client.embed_batch(["text1", "text2", "text3"])

        assert len(results) == 3
        assert all(len(r) == 768 for r in results)


class TestModelAvailability:
    """Tests for model availability checks."""

    @patch("src.llm.embedding_client.requests.get")
    def test_model_available(self, mock_get):
        """Should return True when model is in Ollama tags."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "nomic-embed-text:latest"}]
        }

        client = EmbeddingClient(model="nomic-embed-text")
        assert client.is_model_available() is True

    @patch("src.llm.embedding_client.requests.get")
    def test_model_not_available(self, mock_get):
        """Should return False when model is missing."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": []}

        client = EmbeddingClient(model="nomic-embed-text")
        assert client.is_model_available() is False

    @patch("src.llm.embedding_client.requests.get")
    def test_ollama_unreachable(self, mock_get):
        """Should return False when Ollama is unreachable."""
        mock_get.side_effect = Exception("connection refused")

        client = EmbeddingClient(model="nomic-embed-text")
        assert client.is_model_available() is False


class TestErrorHandling:
    """Tests for error handling."""

    @patch("src.llm.embedding_client.requests.post")
    def test_timeout_raises_error(self, mock_post):
        """Should raise EmbeddingError on timeout."""
        import requests

        mock_post.side_effect = requests.Timeout("timed out")

        client = EmbeddingClient(model="nomic-embed-text", cache_enabled=False)
        with pytest.raises(EmbeddingError, match="timed out"):
            client.embed("hello")

    @patch("src.llm.embedding_client.requests.post")
    def test_empty_response_raises_error(self, mock_post):
        """Should raise EmbeddingError when no embedding in response."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {}

        client = EmbeddingClient(model="nomic-embed-text", cache_enabled=False)
        with pytest.raises(EmbeddingError, match="No embedding"):
            client.embed("hello")


class TestProperties:
    """Tests for client properties."""

    def test_dimension_property(self):
        """Should return correct dimension for known models."""
        client = EmbeddingClient(model="nomic-embed-text")
        assert client.dimension == 768

    def test_stats_tracking(self):
        """Stats should track usage counts."""
        client = EmbeddingClient(model="nomic-embed-text")
        stats = client.stats
        assert "total_embedded" in stats
        assert "cache_hits" in stats
        assert "cache_size" in stats
