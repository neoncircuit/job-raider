"""
Tests for MLflow run history.

Before 2026-10-18, ``MLflowTracker.get_run_history`` passed
``experiment.experiment_name`` as an experiment ID. MLflow ``Experiment``
objects have no such attribute, so the call raised, the error was caught,
and the history was always empty.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.metrics import mlflow_tracker
from src.metrics.mlflow_tracker import ExperimentConfig, MLflowTracker

pytestmark = pytest.mark.skipif(
    not mlflow_tracker.MLFLOW_AVAILABLE, reason="mlflow missing"
)


def test_run_history_queries_by_experiment_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_run_history searches by experiment ID and returns each run.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    fake_mlflow = MagicMock()
    experiment = SimpleNamespace(experiment_id="7", name="job_raider")
    fake_mlflow.get_experiment_by_name.return_value = experiment
    fake_mlflow.search_runs.return_value = pd.DataFrame(
        [
            {
                "run_id": "run-1",
                "start_time": "2026-10-18",
                "status": "FINISHED",
                "metrics.score": 0.8,
            }
        ]
    )
    monkeypatch.setattr(mlflow_tracker, "mlflow", fake_mlflow)

    tracker = MLflowTracker(ExperimentConfig(experiment_name="job_raider"))
    history = tracker.get_run_history(limit=5)

    fake_mlflow.search_runs.assert_called_once_with(
        experiment_ids=["7"],
        max_results=5,
        order_by=["start_time DESC"],
        output_format="pandas",
    )
    assert [run["run_id"] for run in history] == ["run-1"]
    assert history[0]["metrics"] == {"metrics.score": 0.8}
