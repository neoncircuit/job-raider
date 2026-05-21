"""
Job Raider - BM25 Sparse Retriever

In-memory BM25 retrieval for lexical search over chunked documents.
Uses the Okapi BM25 variant for term-frequency-based ranking.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BM25Result:
    """Result from BM25 sparse retrieval.

    Attributes:
        doc_id: Unique document identifier.
        score: Normalized relevance score in 0-1 range.
        document: Original document text.
        metadata: Optional metadata dictionary.
    """

    doc_id: str
    score: float
    document: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BM25Retriever:
    """BM25 sparse retriever for lexical search over chunked documents.

    Maintains an in-memory index of chunked documents and provides
    term-frequency-based retrieval using the Okapi BM25 algorithm.
    Tokenization uses regex ``\\w+`` extraction, consistent with the
    rag-404 reference implementation.

    Note:
        The BM25 index is in-memory and not persistent. It must be
        rebuilt on pipeline restart, which is sub-second for typical
        job volumes (50-200 jobs).
    """

    def __init__(self, tokenizer: Optional[Callable[[str], List[str]]] = None) -> None:
        """Initialize BM25 retriever.

        Args:
            tokenizer: Optional custom tokenizer function. Defaults to
                regex ``\\w+`` extraction from lowercased text.
        """
        self._tokenizer = tokenizer or self._default_tokenize
        self._doc_ids: List[str] = []
        self._documents: List[str] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._tokenized_corpus: List[List[str]] = []
        self._bm25: Optional[Any] = None

    def index_documents(
        self,
        doc_ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Build the BM25 index from documents, replacing any existing index.

        Args:
            doc_ids: Unique document identifiers.
            documents: Text content of each document.
            metadatas: Optional metadata dicts for each document.
        """
        self.clear()
        self._store_documents(doc_ids, documents, metadatas)
        self._build_index()
        logger.info("BM25 index built with %d documents", self.doc_count)

    def add_documents(
        self,
        doc_ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add documents to the existing BM25 index.

        Args:
            doc_ids: Unique document identifiers.
            documents: Text content of each document.
            metadatas: Optional metadata dicts for each document.
        """
        existing_ids = set(self._doc_ids)
        new_ids = []
        new_docs = []
        new_metas = []

        for i, doc_id in enumerate(doc_ids):
            if doc_id not in existing_ids:
                new_ids.append(doc_id)
                new_docs.append(documents[i])
                new_metas.append(metadatas[i] if metadatas else {})

        if not new_ids:
            return

        self._doc_ids.extend(new_ids)
        self._documents.extend(new_docs)
        self._metadatas.extend(new_metas)
        self._tokenized_corpus.extend(
            [self._tokenizer(doc) for doc in new_docs]
        )
        self._build_index()
        logger.debug("Added %d documents to BM25 index (total: %d)", len(new_ids), self.doc_count)

    def query(self, query_text: str, n_results: int = 20) -> List[BM25Result]:
        """Query the BM25 index for matching documents.

        Args:
            query_text: Natural language query string.
            n_results: Maximum number of results to return.

        Returns:
            List of BM25Result sorted by score descending, with scores
            normalized to 0-1 range via min-max scaling.
        """
        if not self._bm25 or self.doc_count == 0:
            return []

        tokenized_query = self._tokenizer(query_text)
        scores = self._bm25.get_scores(tokenized_query)

        results = self._build_results(scores)
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:n_results]

    def clear(self) -> None:
        """Clear the BM25 index and all stored documents."""
        self._doc_ids = []
        self._documents = []
        self._metadatas = []
        self._tokenized_corpus = []
        self._bm25 = None

    @property
    def doc_count(self) -> int:
        """Return the number of documents in the index.

        Returns:
            Integer count of indexed documents.
        """
        return len(self._doc_ids)

    def _store_documents(
        self,
        doc_ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Store document data and tokenize corpus.

        Args:
            doc_ids: Document identifiers.
            documents: Document texts.
            metadatas: Optional per-document metadata.
        """
        self._doc_ids = list(doc_ids)
        self._documents = list(documents)
        self._metadatas = list(metadatas) if metadatas else [{}] * len(doc_ids)
        self._tokenized_corpus = [self._tokenizer(doc) for doc in documents]

    def _build_index(self) -> None:
        """Build or rebuild the BM25 index from the tokenized corpus."""
        if not self._tokenized_corpus:
            self._bm25 = None
            return

        try:
            from rank_bm25 import BM25Okapi, BM25Plus

            if len(self._tokenized_corpus) == 0:
                self._bm25 = None
                return

            algorithm = getattr(self, "_algorithm", "okapi")
            if algorithm == "plus":
                self._bm25 = BM25Plus(self._tokenized_corpus)
            else:
                self._bm25 = BM25Okapi(self._tokenized_corpus)
        except ImportError:
            logger.warning(
                "rank-bm25 not installed. BM25 retrieval unavailable. "
                "Install with: pip install rank-bm25"
            )
            self._bm25 = None

    def _build_results(self, scores: Any) -> List[BM25Result]:
        """Convert raw BM25 scores to normalized BM25Result list.

        Uses min-max normalization to scale scores into 0-1 range.

        Args:
            scores: Array-like of raw BM25 scores.

        Returns:
            List of BM25Result with normalized scores.
        """
        score_list = list(scores)
        max_score = max(score_list) if score_list else 0.0
        min_score = min(score_list) if score_list else 0.0
        score_range = max_score - min_score

        results = []
        for i, raw_score in enumerate(score_list):
            normalized = (
                float((raw_score - min_score) / score_range)
                if score_range > 0
                else (1.0 if raw_score > 0 else 0.0)
            )
            results.append(
                BM25Result(
                    doc_id=self._doc_ids[i],
                    score=normalized,
                    document=self._documents[i],
                    metadata=self._metadatas[i],
                )
            )
        return results

    @staticmethod
    def _default_tokenize(text: str) -> List[str]:
        """Tokenize text using regex word extraction.

        Extracts alphanumeric tokens from lowercased text using
        the ``\\w+`` pattern.

        Args:
            text: Input text to tokenize.

        Returns:
            List of lowercase word tokens.
        """
        return re.findall(r"\w+", text.lower())
