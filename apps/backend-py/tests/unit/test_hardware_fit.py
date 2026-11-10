"""
Tests for the hardware fit rules and the hardware setting (Step 6, MH-2).
"""

import json
from pathlib import Path
from typing import List

import pytest
from pydantic import ValidationError

from src.api.settings import HardwareSettings, UserSettings, merge_preserving_api_keys
from src.hardware.fit import (
    DEFAULT_VRAM_HEADROOM_PERCENT,
    FitLabel,
    FitSource,
    catalog_by_ollama_name,
    is_low_quant,
    label_for,
    label_installed,
    ollama_key,
    rough_need_gb,
    suggest_models,
    vram_budget_gb,
)
from src.hardware.llmfit_client import LLAMA_CPP_RUNTIME, CatalogModel

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llmfit"


def catalog_rows() -> List[CatalogModel]:
    """
    Load the llama.cpp rows of the fit fixture that parse.

    Returns:
        Catalog rows, as ``LlmfitClient.catalog`` returns them.
    """
    rows = json.loads((FIXTURES / "fit.json").read_text())["models"]
    parsed = []
    for row in rows:
        if "memory_required_gb" in row and row["runtime"] == LLAMA_CPP_RUNTIME:
            parsed.append(CatalogModel.model_validate(row))
    return parsed


class TestBudget:
    """The safety budget."""

    def test_default_is_75_percent(self) -> None:
        """The user chose 75% of the VRAM (2026-11-08)."""
        assert DEFAULT_VRAM_HEADROOM_PERCENT == 75
        assert vram_budget_gb(8.0, 75) == 6.0
        assert vram_budget_gb(12.0, 75) == 9.0

    def test_no_gpu_gives_no_budget(self) -> None:
        """Without VRAM the budget is zero."""
        assert vram_budget_gb(None, 75) == 0.0
        assert vram_budget_gb(0.0, 75) == 0.0


class TestLabel:
    """Labels against the budget and the total VRAM."""

    def test_boundaries(self) -> None:
        """The budget and the total are inclusive."""
        assert label_for(6.0, 6.0, 8.0) == FitLabel.FITS
        assert label_for(6.01, 6.0, 8.0) == FitLabel.OVER_BUDGET
        assert label_for(8.0, 6.0, 8.0) == FitLabel.OVER_BUDGET
        assert label_for(8.01, 6.0, 8.0) == FitLabel.TOO_LARGE

    def test_unknown_without_need_or_gpu(self) -> None:
        """No estimate or no GPU gives unknown, never fits."""
        assert label_for(None, 6.0, 8.0) == FitLabel.UNKNOWN
        assert label_for(2.0, 0.0, None) == FitLabel.UNKNOWN

    def test_rough_need_adds_the_allowance(self) -> None:
        """A file of 4.68e9 bytes (4.36 GiB) needs about 5.36 GiB."""
        assert rough_need_gb(4_680_000_000) == 5.36
        assert rough_need_gb(None) is None
        assert rough_need_gb(0) is None

    def test_installed_prefers_the_plan(self) -> None:
        """The llmfit plan for the installed quant wins over the file size."""
        fit = label_installed("examplechat:7b", "Q4_K_M", 4_680_000_000, 5.35, 6.0, 8.0)
        assert fit.source == FitSource.LLMFIT_PLAN
        assert fit.need_gb == 5.35
        assert fit.label == FitLabel.FITS

    def test_the_file_size_is_a_floor_for_the_plan(self) -> None:
        """A plan below the installed file is not used: Ollama loads the file."""
        # gemma4:e4b on the user's machine: llmfit planned 5.79 GiB for a
        # 9.61e9-byte file, which alone is more than the 8 GiB card.
        fit = label_installed("gemma4:e4b", "Q4_K_M", 9_610_000_000, 5.79, 6.0, 8.0)
        assert fit.need_gb == 9.95
        assert fit.source == FitSource.ROUGH_ESTIMATE
        assert fit.label == FitLabel.TOO_LARGE

    def test_a_plan_without_a_file_size_is_used(self) -> None:
        """With no file size there is no floor, so the plan decides."""
        fit = label_installed("x:7b", "Q4_K_M", None, 5.35, 6.0, 8.0)
        assert fit.source == FitSource.LLMFIT_PLAN
        assert fit.need_gb == 5.35

    def test_installed_falls_back_to_a_rough_estimate(self) -> None:
        """Without a plan the file size decides, and the source says so."""
        fit = label_installed(
            "mine-16k:latest", "Q4_K_M", 6_590_000_000, None, 6.0, 8.0
        )
        assert fit.source == FitSource.ROUGH_ESTIMATE
        assert fit.need_gb == 7.14
        assert fit.label == FitLabel.OVER_BUDGET

    def test_installed_without_size_or_plan_is_unknown(self) -> None:
        """No data gives unknown."""
        fit = label_installed("x", None, None, None, 6.0, 8.0)
        assert fit.source == FitSource.NONE
        assert fit.label == FitLabel.UNKNOWN


class TestCatalog:
    """Matching and suggestions."""

    def test_ollama_key(self) -> None:
        """ ":latest" is dropped and case does not matter."""
        assert ollama_key("Mistral:latest") == "mistral"
        assert ollama_key("qwen2.5-coder:7b") == "qwen2.5-coder:7b"

    def test_index_keeps_the_best_score(self) -> None:
        """Two rows with one Ollama name keep the higher score."""
        low = CatalogModel(
            name="a", ollama_name="m:7b", memory_required_gb=5.0, score=60.0
        )
        high = CatalogModel(
            name="b", ollama_name="M:7b", memory_required_gb=5.0, score=70.0
        )
        assert catalog_by_ollama_name([low, high])["m:7b"].name == "b"

    @pytest.mark.parametrize(
        ("quant", "low"),
        [
            ("Q2_K", True),
            ("Q3_K_M", True),
            ("IQ3_XS", True),
            ("Q4_K_M", False),
            ("Q8_0", False),
        ],
    )
    def test_low_quant(self, quant: str, low: bool) -> None:
        """Below 4 bits says nothing about the default Ollama tag."""
        assert is_low_quant(quant) is low

    def test_suggestions(self) -> None:
        """Installed, embedding, too large, low quant, and over budget are out."""
        picks = suggest_models(
            catalog_rows(),
            budget_gb=9.0,
            installed_tags=[],
            max_params_billion=9.0,
        )
        # examplecoder is installed (llmfit says so), exampleembed is an
        # embedding model, examplebig is 14.7B at Q3_K_M.
        assert [p.ollama_name for p in picks] == ["examplechat:7b"]
        assert picks[0].memory_required_gb == 6.4

    def test_suggestions_respect_installed_tags_and_budget(self) -> None:
        """An installed tag and a budget below the need both remove a row."""
        rows = catalog_rows()
        assert suggest_models(rows, 9.0, ["ExampleChat:7b"], 9.0) == []
        assert suggest_models(rows, 6.0, [], 9.0) == []

    def test_suggestions_skip_a_row_that_fits_only_below_q4(self) -> None:
        """A small model that fits only at Q3 is not a suggestion; at Q4 it is."""
        low = CatalogModel(
            name="s",
            ollama_name="small:4b",
            best_quant="Q3_K_M",
            memory_required_gb=3.0,
            score=90.0,
            params_b=4.0,
        )
        assert suggest_models([low], 6.0, [], 9.0) == []
        q4 = low.model_copy(update={"best_quant": "Q4_K_M"})
        assert [p.ollama_name for p in suggest_models([q4], 6.0, [], 9.0)] == [
            "small:4b"
        ]

    def test_suggestions_are_sorted_and_limited(self) -> None:
        """Best score first, and no more than the limit."""
        rows = [
            CatalogModel(
                name=f"m{i}",
                ollama_name=f"m{i}:3b",
                best_quant="Q4_K_M",
                memory_required_gb=3.0,
                score=float(i),
                params_b=3.0,
            )
            for i in range(5)
        ]
        picks = suggest_models(rows, 6.0, [], 9.0, limit=3)
        assert [p.ollama_name for p in picks] == ["m4:3b", "m3:3b", "m2:3b"]


class TestHardwareSetting:
    """The headroom setting."""

    def test_default_and_bounds(self) -> None:
        """75 by default; 30 to 100 are allowed."""
        assert HardwareSettings().vram_headroom_percent == 75
        assert HardwareSettings(vram_headroom_percent=30).vram_headroom_percent == 30
        with pytest.raises(ValidationError):
            HardwareSettings(vram_headroom_percent=29)
        with pytest.raises(ValidationError):
            HardwareSettings(vram_headroom_percent=101)

    def test_old_settings_files_load(self) -> None:
        """A settings file from before Step 6 gets the default."""
        assert UserSettings.model_validate({}).hardware.vram_headroom_percent == 75

    def test_a_save_without_the_section_keeps_the_stored_value(self) -> None:
        """An older client does not send "hardware"; the stored value stays."""
        current = UserSettings(hardware=HardwareSettings(vram_headroom_percent=60))
        incoming = UserSettings.model_validate({"version": "1.0"})
        merged = merge_preserving_api_keys(current, incoming)
        assert merged.hardware.vram_headroom_percent == 60

    def test_a_save_with_the_section_uses_the_new_value(self) -> None:
        """A client that sends "hardware" changes it."""
        current = UserSettings(hardware=HardwareSettings(vram_headroom_percent=60))
        incoming = UserSettings.model_validate(
            {"hardware": {"vram_headroom_percent": 85}}
        )
        merged = merge_preserving_api_keys(current, incoming)
        assert merged.hardware.vram_headroom_percent == 85
