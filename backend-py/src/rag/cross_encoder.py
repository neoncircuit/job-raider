"""
Job Raider - Cross-Encoder Reranker

Optional cross-encoder reranking using sentence-transformers.
Disabled by default. Gracefully degrades when sentence-transformers
is not installed.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-encoder reranker for refining retrieval results.

    Uses a sentence-transformers CrossEncoder model to score
    (query, document) pairs for improved relevance ranking.

    The model is lazily loaded on first use. If sentence-transformers
    is not installed, the reranker reports unavailable and all calls
    pass through without modification.

    Attributes:
        model_name: Name of the cross-encoder model.
        enabled: Whether the reranker is active.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        enabled: bool = False,
        max_length: int = 512,
        device: Optional[str] = None,
    ) -> None:
        """Initialize the cross-encoder reranker.

        Args:
            model_name: Sentence-transformers cross-encoder model identifier.
            enabled: Whether to activate reranking.
            max_length: Maximum sequence length for the model.
            device: Device string (e.g., "cuda", "cpu"). None for auto-detect.
        """
        self._model_name = model_name
        self._enabled = enabled
        self._max_length = max_length
        self._device = device
        self._model: Optional[Any] = None
        self._model_loaded = False
        self._import_available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        """Check if the reranker is available for use.

        Returns:
            True if enabled, sentence-transformers is installed, and the
            model has been (or can be) loaded.
        """
        if not self._enabled:
            return False

        if self._import_available is None:
            try:
                from sentence_transformers import CrossEncoder  # noqa: F401

                self._import_available = True
            except ImportError:
                self._import_available = False
                logger.warning(
                    "sentence-transformers not installed. "
                    "Cross-encoder reranking unavailable. "
                    "Install with: pip install sentence-transformers"
                )

        return self._import_available

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rerank retrieval results against a query using the cross-encoder.

        Args:
            query: Query text to score against.
            results: List of result dicts, each with ``document`` key and
                optionally ``doc_id``, ``metadata``, etc.
            top_k: Return only top K results after reranking. None returns all.

        Returns:
            Reranked list of result dicts sorted by cross-encoder score,
            with added ``cross_encoder_score`` field. Returns original
            list unchanged if reranking is unavailable.
        """
        if not self._enabled or not results:
            return results

        if not self.is_available:
            return results

        self._load_model()
        if self._model is None:
            return results

        pairs = [(query, r.get("document", "")) for r in results]
        scores = self._model.predict(pairs)

        scored_results = []
        for result, score in zip(results, scores):
            scored_results.append({
                **result,
                "cross_encoder_score": float(score),
            })
        scored_results.sort(key=lambda r: r["cross_encoder_score"], reverse=True)

        logger.debug(
            "Cross-encoder reranked %d results (top score: %.4f)",
            len(scored_results),
            scored_results[0]["cross_encoder_score"] if scored_results else 0.0,
        )

        if top_k is not None:
            return scored_results[:top_k]
        return scored_results

    def _load_model(self) -> None:
        """Lazily load the cross-encoder model on first use."""
        if self._model_loaded:
            return

        self._model_loaded = True

        try:
            from sentence_transformers import CrossEncoder

            logger.info("Loading cross-encoder model: %s", self._model_name)
            self._model = CrossEncoder(
                self._model_name,
                max_length=self._max_length,
                device=self._device,
            )
            logger.info("Cross-encoder model loaded successfully")
        except Exception as e:
            logger.error("Failed to load cross-encoder model: %s", e)
            self._model = None
