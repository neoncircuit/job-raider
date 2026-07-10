"""
Unit tests for Reciprocal Rank Fusion (RRF).
"""

from src.rag.rrf_fusion import RRFResult, reciprocal_rank_fusion


class TestRRFBasicFusion:
    """Tests for basic RRF fusion of two result lists."""

    def test_fusion_produces_sorted_results(self):
        """RRF fusion returns results sorted by score descending."""
        dense = [
            {"doc_id": "a", "document": "doc a", "metadata": {}},
            {"doc_id": "b", "document": "doc b", "metadata": {}},
        ]
        sparse = [
            {"doc_id": "b", "document": "doc b", "metadata": {}},
            {"doc_id": "c", "document": "doc c", "metadata": {}},
        ]

        results = reciprocal_rank_fusion(dense, sparse)

        assert len(results) == 3
        assert all(isinstance(r, RRFResult) for r in results)
        for i in range(len(results) - 1):
            assert results[i].rrf_score >= results[i + 1].rrf_score

    def test_overlapping_doc_gets_higher_score(self):
        """A document appearing in both lists gets a higher fused score."""
        dense = [
            {"doc_id": "shared", "document": "shared doc"},
            {"doc_id": "dense_only", "document": "dense only"},
        ]
        sparse = [
            {"doc_id": "shared", "document": "shared doc"},
            {"doc_id": "sparse_only", "document": "sparse only"},
        ]

        results = reciprocal_rank_fusion(dense, sparse)

        shared = next(r for r in results if r.doc_id == "shared")
        dense_only = next(r for r in results if r.doc_id == "dense_only")
        assert shared.rrf_score > dense_only.rrf_score


class TestRRFSingleList:
    """Tests for fusion with a single non-empty list."""

    def test_dense_only_preserves_ranking(self):
        """Fusion with only dense results preserves ranking order."""
        dense = [
            {"doc_id": "a", "document": "doc a"},
            {"doc_id": "b", "document": "doc b"},
            {"doc_id": "c", "document": "doc c"},
        ]

        results = reciprocal_rank_fusion(dense, [])

        assert len(results) == 3
        assert results[0].doc_id == "a"
        assert results[0].rrf_score > results[1].rrf_score

    def test_sparse_only_preserves_ranking(self):
        """Fusion with only sparse results preserves ranking order."""
        sparse = [
            {"doc_id": "x", "document": "doc x"},
            {"doc_id": "y", "document": "doc y"},
        ]

        results = reciprocal_rank_fusion([], sparse)

        assert len(results) == 2
        assert results[0].doc_id == "x"


class TestRRFWeights:
    """Tests for weight parameter behavior."""

    def test_equal_weights_same_ranking(self):
        """Equal weights with mirrored rankings produce equal scores."""
        dense = [
            {"doc_id": "a", "document": "doc a"},
            {"doc_id": "b", "document": "doc b"},
        ]
        sparse = [
            {"doc_id": "b", "document": "doc b"},
            {"doc_id": "a", "document": "doc a"},
        ]

        results = reciprocal_rank_fusion(
            dense, sparse, dense_weight=0.5, sparse_weight=0.5
        )
        scores = {r.doc_id: r.rrf_score for r in results}
        assert abs(scores["a"] - scores["b"]) < 1e-10

    def test_zero_sparse_weight(self):
        """Zero sparse weight effectively ignores sparse results."""
        dense = [{"doc_id": "a", "document": "doc a"}]
        sparse = [{"doc_id": "b", "document": "doc b"}]

        results = reciprocal_rank_fusion(
            dense, sparse, dense_weight=1.0, sparse_weight=0.0
        )

        a_result = next(r for r in results if r.doc_id == "a")
        b_result = next(r for r in results if r.doc_id == "b")
        assert a_result.rrf_score > 0
        assert b_result.rrf_score == 0.0


class TestRRFEmptyInput:
    """Tests for empty input handling."""

    def test_both_empty_returns_empty(self):
        """Fusion of two empty lists returns empty."""
        results = reciprocal_rank_fusion([], [])
        assert results == []

    def test_top_n_limits_results(self):
        """top_n parameter limits the number of returned results."""
        dense = [{"doc_id": f"d{i}"} for i in range(10)]
        sparse = [{"doc_id": f"s{i}"} for i in range(10)]

        results = reciprocal_rank_fusion(dense, sparse, top_n=5)
        assert len(results) == 5


class TestRRFKParameter:
    """Tests for the k parameter effect."""

    def test_higher_k_reduces_score_gap(self):
        """Higher k value reduces the advantage of top-ranked items."""
        dense = [{"doc_id": "a"}, {"doc_id": "b"}]

        results_low_k = reciprocal_rank_fusion(dense, [], k=1)
        results_high_k = reciprocal_rank_fusion(dense, [], k=1000)

        gap_low = results_low_k[0].rrf_score - results_low_k[1].rrf_score
        gap_high = results_high_k[0].rrf_score - results_high_k[1].rrf_score
        assert gap_low > gap_high


class TestRRFRankTracking:
    """Tests for rank position tracking in results."""

    def test_dense_rank_tracked(self):
        """RRFResult tracks the dense rank position."""
        dense = [{"doc_id": "a"}, {"doc_id": "b"}]
        results = reciprocal_rank_fusion(dense, [])

        a_result = next(r for r in results if r.doc_id == "a")
        assert a_result.dense_rank == 1
        assert a_result.sparse_rank is None

    def test_sparse_rank_tracked(self):
        """RRFResult tracks the sparse rank position."""
        sparse = [{"doc_id": "x"}, {"doc_id": "y"}]
        results = reciprocal_rank_fusion([], sparse)

        x_result = next(r for r in results if r.doc_id == "x")
        assert x_result.dense_rank is None
        assert x_result.sparse_rank == 1

    def test_both_ranks_tracked_for_shared(self):
        """A document in both lists has both rank positions tracked."""
        dense = [{"doc_id": "shared"}]
        sparse = [{"doc_id": "shared"}]

        results = reciprocal_rank_fusion(dense, sparse)

        shared = results[0]
        assert shared.dense_rank == 1
        assert shared.sparse_rank == 1
