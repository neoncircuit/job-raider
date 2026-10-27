"""
Tests for cost-run scope, the run file, and MLflow (Step 3.6, A4).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.metrics.cost_tracker import (
    cost_run_scope,
    get_cost_tracker,
    reset_cost_tracker,
    write_cost_run_summary,
)
from src.models.pipeline_stage import PipelineStage
from src.pipeline.orchestrator import PipelineConfig, PipelineOrchestrator
from src.pipeline.stages import StageResult


@pytest.fixture(autouse=True)
def _empty_tracker() -> None:
    """Each test starts from an empty process-wide tracker."""
    reset_cost_tracker()
    yield
    reset_cost_tracker()


def _record(task_type: str = "selection") -> None:
    """Write one Ollama selection record on the process tracker."""
    get_cost_tracker().record_call(
        task_type=task_type,
        provider="ollama",
        model="qwen2.5:3b",
        prompt_tokens=2,
        completion_tokens=3,
        latency_ms=4,
    )


def test_scope_sets_run_id_and_outside_has_none() -> None:
    """Calls inside a scope carry its run ID; a call outside has none."""
    with cost_run_scope("run-inside"):
        _record()
    _record()
    records = get_cost_tracker().recent_calls()
    assert records[0].run_id == "run-inside"
    assert records[1].run_id == ""


def test_two_threads_keep_run_ids_apart() -> None:
    """Two scopes in two threads keep their calls apart."""

    def worker(run_id: str) -> None:
        with cost_run_scope(run_id):
            _record()

    first = Thread(target=worker, args=("run-a",))
    second = Thread(target=worker, args=("run-b",))
    first.start()
    second.start()
    first.join()
    second.join()
    assert [c.run_id for c in get_cost_tracker().run_calls("run-a")] == ["run-a"]
    assert [c.run_id for c in get_cost_tracker().run_calls("run-b")] == ["run-b"]


def test_run_file_contains_only_that_run(tmp_path: Path) -> None:
    """The run file lists only the calls of that run."""
    with cost_run_scope("keep"):
        _record("selection")
    with cost_run_scope("other"):
        _record("scoring")
    write_cost_run_summary("keep", storage_dir=tmp_path, tracker_factory=MagicMock())
    data = json.loads((tmp_path / "cost_run_keep.json").read_text(encoding="utf-8"))
    assert data["run_id"] == "keep"
    assert len(data["calls"]) == 1
    assert data["calls"][0]["task_type"] == "selection"
    assert data["summary"]["total_calls"] == 1


def _ok(stage: PipelineStage) -> StageResult:
    """Return a successful empty stage result."""
    return StageResult(
        stage_name=stage.value,
        success=True,
        data=[],
        metadata={},
        timestamp=datetime.now(),
    )


def test_cancelled_run_writes_its_file(
    tmp_path: Path, sample_user_profile: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancelled run still writes cost_run_<id>.json."""
    orchestrator = PipelineOrchestrator(
        config=PipelineConfig(
            keywords=["python"],
            locations=["Remote"],
            data_dir=str(tmp_path / "data"),
            results_dir=str(tmp_path / "results"),
            mode="full",
        ),
        user_profile=sample_user_profile,
    )
    ran: list[PipelineStage] = []

    def fake(*_args: Any, **_kwargs: Any) -> StageResult:
        ran.append(PipelineStage.SCRAPE)
        return _ok(PipelineStage.SCRAPE)

    monkeypatch.setattr(orchestrator.stages, "stage_scrape", fake)
    monkeypatch.setattr(
        orchestrator.stages,
        "stage_deduplicate",
        lambda *_a, **_k: _ok(PipelineStage.DEDUPLICATE),
    )
    result = orchestrator.run(
        run_id="cancel-1",
        should_stop=lambda: len(ran) >= 1,
        cost_storage_dir=tmp_path,
        cost_mlflow_factory=MagicMock(),
    )
    assert result.metadata["cancelled"] is True
    assert (tmp_path / "cost_run_cancel-1.json").is_file()
    assert "cost" in result.metadata


def test_mlflow_called_once_and_error_is_fail_open(tmp_path: Path) -> None:
    """MLflow is called once with the expected metrics; an error is ignored."""
    with cost_run_scope("ml-1"):
        _record()
    factory = MagicMock()
    tracker = MagicMock()
    factory.return_value = tracker
    tracker.start_run.return_value = "mlflow-run"
    summary = write_cost_run_summary(
        "ml-1",
        storage_dir=tmp_path,
        mode="discover",
        tracker_factory=factory,
    )
    factory.assert_called_once()
    tracker.log_metrics.assert_called_once()
    metrics = tracker.log_metrics.call_args[0][0]
    assert metrics["calls"] == 1
    assert metrics["prompt_tokens"] == 2
    assert metrics["completion_tokens"] == 3
    assert metrics["total_tokens"] == 5
    assert metrics["fallback_count"] == 0
    assert metrics["error_count"] == 0
    assert "cost_usd" in metrics
    broken = MagicMock(side_effect=RuntimeError("mlflow down"))
    result = write_cost_run_summary(
        "ml-1",
        storage_dir=tmp_path / "again",
        tracker_factory=broken,
    )
    assert result["total_calls"] == summary["total_calls"]


def test_orchestrator_mlflow_error_does_not_change_result(
    tmp_path: Path, sample_user_profile: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An MLflow error does not change the pipeline result."""
    orchestrator = PipelineOrchestrator(
        config=PipelineConfig(
            keywords=["python"],
            locations=["Remote"],
            data_dir=str(tmp_path / "data"),
            results_dir=str(tmp_path / "results"),
            skip_submission=True,
        ),
        user_profile=sample_user_profile,
    )
    monkeypatch.setattr(
        orchestrator.stages,
        "stage_scrape",
        lambda *_a, **_k: _ok(PipelineStage.SCRAPE),
    )
    monkeypatch.setattr(
        "src.metrics.cost_tracker.log_cost_run_to_mlflow",
        MagicMock(side_effect=RuntimeError("mlflow down")),
    )
    result = orchestrator.run(
        run_id="pipe-1",
        stop_at=PipelineStage.SCRAPE,
        cost_storage_dir=tmp_path,
    )
    assert result.success is True
    assert result.metadata["cost"]["total_calls"] >= 0
