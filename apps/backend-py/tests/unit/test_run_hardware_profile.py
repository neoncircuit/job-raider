"""
Tests for the hardware profile in evaluation runs (Step 6, MH-6).

A stub client stands in for llmfit, with made-up hardware.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.evaluation import cover_letter_compare, run_metadata
from src.evaluation.report import _metadata_params
from src.evaluation.run_metadata import RunMetadata, collect_hardware
from src.hardware.llmfit_client import HardwareProfile, LlmfitUnavailable


class StubClient:
    """Answers like LlmfitClient."""

    def __init__(self, unavailable: Optional[str] = None) -> None:
        """
        Initialize the stub.

        Args:
            unavailable: When set, every call raises LlmfitUnavailable.
        """
        self.unavailable = unavailable

    def version(self) -> Tuple[int, int, int]:
        """Return the minimum version, or raise."""
        if self.unavailable:
            raise LlmfitUnavailable(self.unavailable)
        return (1, 1, 20)

    def system(self) -> HardwareProfile:
        """Return made-up hardware."""
        return HardwareProfile(
            has_gpu=True,
            gpu_name="Example GPU",
            gpu_vram_gb=12.0,
            total_ram_gb=32.0,
            cpu_name="Example CPU",
        )


PROFILE = {
    "gpu_name": "Example GPU",
    "gpu_vram_gb": 12.0,
    "ram_gb": 32.0,
    "cpu_name": "Example CPU",
    "hardware_source": "llmfit 1.1.20",
}


def test_collect_hardware_reads_llmfit() -> None:
    """The profile names the GPU, its memory, the RAM, the CPU, and llmfit."""
    assert collect_hardware(lambda: StubClient()) == PROFILE


def test_collect_hardware_without_llmfit_is_empty() -> None:
    """No llmfit gives no profile, and no error."""
    stub = StubClient(unavailable="llmfit is not installed")
    assert collect_hardware(lambda: stub) == {}


def test_collect_hardware_drops_unknown_values() -> None:
    """A machine without a GPU has no GPU fields."""

    class NoGpu(StubClient):
        """Stub with no GPU."""

        def system(self) -> HardwareProfile:
            """Return hardware without a GPU."""
            return HardwareProfile(has_gpu=False, total_ram_gb=16.0)

    assert collect_hardware(lambda: NoGpu()) == {
        "ram_gb": 16.0,
        "hardware_source": "llmfit 1.1.20",
    }


def test_run_metadata_records_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_run_metadata adds the profile, and MLflow params include it."""
    monkeypatch.setattr(run_metadata, "collect_hardware", lambda: dict(PROFILE))
    data = tmp_path / "cases.jsonl"
    data.write_text("{}\n")
    metadata = run_metadata.build_run_metadata("unit", [data], 1, repo_dir=tmp_path)
    assert metadata.gpu_name == "Example GPU"
    assert metadata.hardware_source == "llmfit 1.1.20"
    params = _metadata_params(metadata)
    assert params["gpu_vram_gb"] == 12.0
    assert params["cpu_name"] == "Example CPU"


def test_without_llmfit_the_params_stay_as_before(tmp_path: Path) -> None:
    """The conftest hides any real llmfit, so no hardware param is logged."""
    data = tmp_path / "cases.jsonl"
    data.write_text("{}\n")
    metadata = run_metadata.build_run_metadata("unit", [data], 1, repo_dir=tmp_path)
    params = _metadata_params(metadata)
    assert not {"gpu_name", "gpu_vram_gb", "ram_gb", "cpu_name"} & set(params)


def test_old_reports_still_load() -> None:
    """Metadata saved before Step 6 has no hardware fields."""
    old = RunMetadata.model_validate(
        {
            "suite": "grounding",
            "git_sha": "abc",
            "git_dirty": False,
            "dataset_sha256": "d",
            "case_count": 3,
            "started_at": "2026-11-01T00:00:00Z",
        }
    )
    assert old.gpu_name is None
    assert "gpu_name" not in _metadata_params(old)


class FakeTracker:
    """Records what a compare run logs."""

    def __init__(self) -> None:
        """Start with empty records."""
        self.params: List[Dict[str, Any]] = []

    def start_run(self, run_name: str, tags: Dict[str, str]) -> str:
        """Return a fixed run id."""
        return "run-1"

    def log_params(self, params: Dict[str, Any]) -> None:
        """Record params."""
        self.params.append(params)

    def log_metrics(self, metrics: Dict[str, float]) -> None:
        """Ignore metrics."""

    def log_artifact(self, path: str) -> None:
        """Ignore artifacts."""

    def end_run(self) -> None:
        """Nothing to close."""


def test_compare_run_logs_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cover-letter model compare logs the hardware with its params."""
    monkeypatch.setattr(cover_letter_compare, "collect_hardware", lambda: dict(PROFILE))
    # No real MLflow lookup: it could create a tracking store in the cwd.
    monkeypatch.setattr(cover_letter_compare, "_experiment_id", lambda: "1")
    tracker = FakeTracker()
    report = {
        "generated_at": "2026-11-09T00:00:00Z",
        "winner": "a:7b",
        "protocol": {"cool_down_s": 5},
        "reports": [
            {
                "model": "a:7b",
                "mean_score": 0.8,
                "cases": [{"case_id": "c1", "score": 0.8, "elapsed_ms": 900}],
            }
        ],
    }
    path = tmp_path / "compare.json"
    path.write_text("{}")
    cover_letter_compare.log_to_mlflow(
        report, path, tracker_factory=lambda **_: tracker
    )
    assert tracker.params, "no params were logged"
    assert tracker.params[0]["gpu_name"] == "Example GPU"
    assert tracker.params[0]["models"] == "a:7b"
