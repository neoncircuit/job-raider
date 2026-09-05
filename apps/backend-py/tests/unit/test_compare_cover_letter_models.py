"""
Unit tests for the safe cover-letter model A/B helper functions.

Does not call Ollama or load GPU models.

Author: Job Raider
Date: 2026-08-25
"""

import pytest

from scripts.compare_cover_letter_models import (
    ALLOWED_MODELS,
    choose_winner,
    model_is_installed,
    validate_models,
)


class TestCompareCoverLetterModelsHelpers:
    """Offline validation for the A/B harness guards."""

    def test_allowed_models_are_only_7b_and_4b(self) -> None:
        """Allow-list must stay limited to the safe pair."""
        assert ALLOWED_MODELS == ("qwen2.5:7b", "qwen3.5:4b")

    def test_validate_models_rejects_9b(self) -> None:
        """9B tags must be rejected before any generate call."""
        with pytest.raises(ValueError, match="not in the safe allow-list"):
            validate_models(["qwen3.5:9b"])

    def test_validate_models_accepts_allow_list(self) -> None:
        """Both allow-list tags should pass validation."""
        validate_models(["qwen2.5:7b", "qwen3.5:4b"])

    def test_model_is_installed_exact_and_prefix(self) -> None:
        """Installed tag matching should accept exact names."""
        installed = ["qwen2.5:7b", "qwen2.5:3b"]
        assert model_is_installed("qwen2.5:7b", installed) is True
        assert model_is_installed("qwen3.5:4b", installed) is False

    def test_choose_winner_by_mean_score(self) -> None:
        """Highest mean validator score wins."""
        reports = [
            {"model": "qwen2.5:7b", "mean_score": 78.0},
            {"model": "qwen3.5:4b", "mean_score": 71.5},
        ]
        assert choose_winner(reports) == "qwen2.5:7b"
