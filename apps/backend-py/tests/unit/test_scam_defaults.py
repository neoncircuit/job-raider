"""
Shared scam default and Pipeline page cross-check (Stage B B2a).
"""

from __future__ import annotations

from src.api.models.requests import PipelineStartRequest
from src.evaluation.run_metadata import BACKEND_DIR
from src.pipeline.orchestrator import PipelineConfig
from src.scoring.scam_detector import DEFAULT_SCAM_ACTION, DEFAULT_SCAM_THRESHOLD
from src.scoring.trust_analyzer import TrustAnalyzer


class TestSharedScamDefaults:
    """Every listed default reads ``DEFAULT_SCAM_THRESHOLD`` and action."""

    def test_request_defaults(self) -> None:
        """``PipelineStartRequest`` uses the shared threshold and action."""
        request = PipelineStartRequest(keywords=["clerk"], locations=["Singapore"])
        assert request.scam_threshold == DEFAULT_SCAM_THRESHOLD
        assert request.scam_action == DEFAULT_SCAM_ACTION

    def test_pipeline_config_defaults(self) -> None:
        """``PipelineConfig`` uses the shared threshold and action."""
        config = PipelineConfig(keywords=["clerk"], locations=["Singapore"])
        assert config.scam_threshold == DEFAULT_SCAM_THRESHOLD
        assert config.scam_action == DEFAULT_SCAM_ACTION

    def test_trust_analyzer_reads_the_shared_threshold(self) -> None:
        """``TrustAnalyzer`` uses the shared detector threshold."""
        analyzer = TrustAnalyzer()
        assert analyzer.detector.threshold == DEFAULT_SCAM_THRESHOLD

    def test_pipeline_page_matches_shared_defaults(self) -> None:
        """
        The Pipeline page default and help text match the backend defaults.

        Returns:
            None.
        """
        page = (
            BACKEND_DIR.parent / "frontend-ts" / "src" / "app" / "pipeline" / "page.tsx"
        ).read_text(encoding="utf-8")
        assert f"scamThreshold: {DEFAULT_SCAM_THRESHOLD}" in page
        assert 'step="0.05"' in page
        if DEFAULT_SCAM_ACTION == "drop":
            assert "Jobs at or above this score are removed." in page
            assert "Jobs at or above this score are flagged and kept." not in page
        else:
            assert "Jobs at or above this score are flagged and kept." in page
            assert "Jobs at or above this score are removed." not in page
