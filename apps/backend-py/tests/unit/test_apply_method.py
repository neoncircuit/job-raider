"""
Unit tests for the _compute_apply_method heuristic in the jobs API route.
"""

from src.api.routes.jobs import _compute_apply_method


class TestComputeApplyMethod:
    """Tests for the source-based apply-method heuristic."""

    def test_jsearch_returns_external_site(self):
        """JSearch jobs are always external (link to original posting)."""
        assert _compute_apply_method("jsearch", False) == "external_site"

    def test_linkedin_returns_easy_apply(self):
        """LinkedIn jobs default to easy_apply (optimistic)."""
        assert _compute_apply_method("linkedin", False) == "easy_apply"

    def test_jsearch_already_applied_takes_priority(self):
        """Already-applied status overrides source heuristic."""
        assert _compute_apply_method("jsearch", True) == "already_applied"

    def test_linkedin_already_applied_takes_priority(self):
        """Already-applied status overrides source heuristic."""
        assert _compute_apply_method("linkedin", True) == "already_applied"

    def test_unknown_source_defaults_to_easy_apply(self):
        """Unknown sources default to easy_apply."""
        assert _compute_apply_method("unknown_source", False) == "easy_apply"
