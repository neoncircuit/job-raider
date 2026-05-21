"""
Unit tests for CrossEncoderReranker.
"""

from unittest.mock import patch, MagicMock

from src.rag.cross_encoder import CrossEncoderReranker


class TestCrossEncoderDisabled:
    """Tests for the disabled (default) state."""

    def test_disabled_is_not_available(self):
        """A disabled reranker is not available."""
        reranker = CrossEncoderReranker(enabled=False)
        assert not reranker.is_available

    def test_disabled_rerank_returns_input(self):
        """Reranking with disabled reranker returns input unchanged."""
        reranker = CrossEncoderReranker(enabled=False)
        results = [{"doc_id": "a", "document": "test doc"}]

        output = reranker.rerank("query", results)

        assert output is results

    def test_default_is_disabled(self):
        """CrossEncoderReranker is disabled by default."""
        reranker = CrossEncoderReranker()
        assert not reranker._enabled


class TestCrossEncoderNotInstalled:
    """Tests for graceful degradation when sentence-transformers is missing."""

    def test_import_failure_reports_unavailable(self):
        """When sentence-transformers import fails, is_available is False."""
        reranker = CrossEncoderReranker(enabled=True)

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            reranker._import_available = None
            assert not reranker.is_available

    def test_unavailable_rerank_returns_input(self):
        """Reranking with unavailable model returns input unchanged."""
        reranker = CrossEncoderReranker(enabled=True)

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            reranker._import_available = None
            results = [{"doc_id": "a", "document": "test"}]
            output = reranker.rerank("query", results)
            assert output is results


class TestCrossEncoderRerank:
    """Tests for reranking with a mocked model."""

    def test_rerank_adds_cross_encoder_scores(self):
        """Reranking attaches cross_encoder_score to each result."""
        reranker = CrossEncoderReranker(enabled=True)
        reranker._import_available = True

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.3, 0.6]
        reranker._model = mock_model
        reranker._model_loaded = True

        results = [
            {"doc_id": "a", "document": "first doc"},
            {"doc_id": "b", "document": "second doc"},
            {"doc_id": "c", "document": "third doc"},
        ]

        output = reranker.rerank("test query", results)

        assert len(output) == 3
        assert all("cross_encoder_score" in r for r in output)
        assert output[0]["doc_id"] == "a"
        assert output[0]["cross_encoder_score"] == 0.9
        assert output[2]["doc_id"] == "b"

    def test_rerank_top_k_limits_results(self):
        """top_k parameter limits the number of returned results."""
        reranker = CrossEncoderReranker(enabled=True)
        reranker._import_available = True

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.5, 0.8, 0.3]
        reranker._model = mock_model
        reranker._model_loaded = True

        results = [
            {"doc_id": f"doc_{i}", "document": f"doc {i}"}
            for i in range(3)
        ]

        output = reranker.rerank("query", results, top_k=2)
        assert len(output) == 2

    def test_rerank_empty_results_returns_empty(self):
        """Reranking empty results returns empty list."""
        reranker = CrossEncoderReranker(enabled=True)
        output = reranker.rerank("query", [])
        assert output == []

    def test_rerank_preserves_existing_fields(self):
        """Reranking preserves fields from input results."""
        reranker = CrossEncoderReranker(enabled=True)
        reranker._import_available = True

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.7]
        reranker._model = mock_model
        reranker._model_loaded = True

        results = [{"doc_id": "a", "document": "doc", "custom_field": "preserved"}]

        output = reranker.rerank("query", results)

        assert output[0]["custom_field"] == "preserved"
        assert output[0]["doc_id"] == "a"
