"""
Job Raider - Reciprocal Rank Fusion (RRF)

Pure-function module for fusing multiple ranked result lists using RRF.
RRF formula: score(doc) = sum(weight_i / (k + rank_i)) across retrievers.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RRFResult:
    """Result from Reciprocal Rank Fusion.

    Attributes:
        doc_id: Unique document identifier.
        rrf_score: Fused RRF score (not normalized to 0-1).
        document: Original document text.
        metadata: Metadata dictionary from source retriever.
        dense_rank: Rank position from dense retriever (None if absent).
        sparse_rank: Rank position from sparse retriever (None if absent).
    """

    doc_id: str
    rrf_score: float
    document: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None


def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]],
    sparse_results: List[Dict[str, Any]],
    k: int = 60,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.5,
    top_n: Optional[int] = None,
) -> List[RRFResult]:
    """Fuse dense and sparse retrieval results using Reciprocal Rank Fusion.

    Each result dict must contain at minimum a ``doc_id`` key. Additional
    keys ``document`` and ``metadata`` are carried through to the output.

    RRF formula::

        score(doc) = sum(weight_i / (k + rank_i))

    where rank_i is the 1-based position of the document in each input list.

    Args:
        dense_results: Ranked list from dense retrieval (sorted by relevance).
            Each dict must have ``doc_id``, optionally ``document`` and ``metadata``.
        sparse_results: Ranked list from BM25 retrieval (sorted by relevance).
            Same format as dense_results.
        k: RRF constant for rank dampening. Higher k reduces the advantage
            of top-ranked items. Default 60.
        dense_weight: Weight for dense retrieval ranks. Default 0.5.
        sparse_weight: Weight for sparse retrieval ranks. Default 0.5.
        top_n: Return only the top N fused results. None returns all.

    Returns:
        List of RRFResult sorted by rrf_score descending.
    """
    fused: Dict[str, tuple] = {}

    for rank, result in enumerate(dense_results, start=1):
        doc_id = result["doc_id"]
        rrf_contribution = dense_weight / (k + rank)
        if doc_id in fused:
            score, doc, meta, d_rank, s_rank = fused[doc_id]
            fused[doc_id] = (score + rrf_contribution, doc, meta, rank, s_rank)
        else:
            fused[doc_id] = (
                rrf_contribution,
                result.get("document", ""),
                result.get("metadata", {}),
                rank,
                None,
            )

    for rank, result in enumerate(sparse_results, start=1):
        doc_id = result["doc_id"]
        rrf_contribution = sparse_weight / (k + rank)
        if doc_id in fused:
            score, doc, meta, d_rank, s_rank = fused[doc_id]
            fused[doc_id] = (score + rrf_contribution, doc, meta, d_rank, rank)
        else:
            fused[doc_id] = (
                rrf_contribution,
                result.get("document", ""),
                result.get("metadata", {}),
                None,
                rank,
            )

    results = [
        RRFResult(
            doc_id=doc_id,
            rrf_score=data[0],
            document=data[1],
            metadata=data[2],
            dense_rank=data[3],
            sparse_rank=data[4],
        )
        for doc_id, data in fused.items()
    ]
    results.sort(key=lambda r: r.rrf_score, reverse=True)

    logger.debug(
        "RRF fusion: %d dense + %d sparse -> %d unique documents",
        len(dense_results),
        len(sparse_results),
        len(results),
    )

    if top_n is not None:
        return results[:top_n]
    return results
