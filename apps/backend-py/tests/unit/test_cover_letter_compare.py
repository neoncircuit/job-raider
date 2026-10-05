"""
Job Raider - Cover-letter model compare core and API tests.

No Ollama, GPU, or MLflow server is used: the writer, scorer, unload call,
sleep, and tracker are all fakes.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.routes import evaluation
from src.evaluation import cover_letter_compare as compare

CASES = [("case_a", "job_a", "profile", "sel"), ("case_b", "job_b", "profile", "sel")]


class FakeWriter:
    """Writer that returns a canned letter and records calls."""

    def __init__(self, fail_on: str = "") -> None:
        """Create the writer.

        Args:
            fail_on: Job value that raises instead of writing.
        """
        self.calls: List[Dict[str, Any]] = []
        self.fail_on = fail_on

    def write(self, job: Any, profile: Any, selection: Any, model: str) -> Any:
        """Return a fake letter.

        Args:
            job: Job fixture.
            profile: Profile fixture.
            selection: Selection fixture.
            model: Model tag.

        Returns:
            Object with the fields ``run_compare`` reads.
        """
        if job == self.fail_on:
            raise RuntimeError("writer exploded")
        self.calls.append({"job": job, "model": model})
        return SimpleNamespace(
            model_used=model, content="Dear team, hello.", word_count=3
        )


def _scorer(letter: Any, job: Any, profile: Any, selection: Any) -> Dict[str, Any]:
    """Score 80 for the 7b model and 70 otherwise.

    Args:
        letter: Fake letter.
        job: Job fixture.
        profile: Profile fixture.
        selection: Selection fixture.

    Returns:
        Score payload.
    """
    return {"score": 80.0 if "7b" in letter.model_used else 70.0, "is_valid": True}


@pytest.fixture(autouse=True)
def reset_compare_state() -> Iterator[None]:
    """Free the compare slot and clear state around each test.

    Yields:
        None.
    """
    yield
    if evaluation._run_lock.locked():
        evaluation._run_lock.release()
    evaluation._state.clear()
    evaluation._state["status"] = "idle"


class TestCore:
    """``run_compare`` and guards."""

    def test_runs_models_in_order_and_picks_winner(self) -> None:
        """Each model runs every case, is unloaded, then cools down."""
        writer = FakeWriter()
        sleeps: List[float] = []
        progress: List[tuple] = []
        with patch.object(compare.requests, "post") as unload:
            report = compare.run_compare(
                ["qwen3.5:4b", "qwen2.5:7b"],
                base_url="http://ollama:11434",
                cool_down_s=5,
                cases=CASES,
                writer_factory=lambda: writer,
                scorer=_scorer,
                on_progress=lambda *a: progress.append(a),
                sleep=sleeps.append,
            )

        assert [c["model"] for c in writer.calls] == [
            "qwen3.5:4b",
            "qwen3.5:4b",
            "qwen2.5:7b",
            "qwen2.5:7b",
        ]
        assert unload.call_count == 2
        assert unload.call_args.kwargs["json"]["keep_alive"] == 0
        assert sleeps == [5, 5]
        assert progress[0] == ("qwen3.5:4b", "case_a", 0, 4)
        assert progress[-1] == ("qwen2.5:7b", "case_b", 3, 4)
        assert report["winner"] == "qwen2.5:7b"
        assert [r["mean_score"] for r in report["reports"]] == [70.0, 80.0]

    def test_unloads_even_when_writer_fails(self) -> None:
        """A failing case still unloads the model and cools down."""
        sleeps: List[float] = []
        with patch.object(compare.requests, "post") as unload:
            with pytest.raises(RuntimeError, match="writer exploded"):
                compare.run_compare(
                    ["qwen2.5:7b"],
                    base_url="http://ollama:11434",
                    cool_down_s=3,
                    cases=CASES,
                    writer_factory=lambda: FakeWriter(fail_on="job_b"),
                    scorer=_scorer,
                    sleep=sleeps.append,
                )
        unload.assert_called_once()
        assert sleeps == [3]

    @pytest.mark.parametrize("models", [[], ["qwen3.5:9b"], ["gemma3:12b"]])
    def test_validate_models_rejects(self, models: List[str]) -> None:
        """Empty lists and non-allow-list tags are refused."""
        with pytest.raises(ValueError):
            compare.validate_models(models)

    def test_report_roundtrip(self, tmp_path: Path) -> None:
        """Saved reports load back; a missing file returns None."""
        path = tmp_path / "out" / "report.json"
        compare.save_report({"winner": "qwen2.5:7b"}, path)
        assert compare.load_report(path) == {"winner": "qwen2.5:7b"}
        assert compare.load_report(tmp_path / "missing.json") is None


class TestMlflow:
    """``log_to_mlflow`` with a fake tracker."""

    REPORT = {
        "generated_at": "2026-10-05T12:00:00",
        "protocol": {"cool_down_s": 20.0},
        "winner": "qwen2.5:7b",
        "reports": [
            {
                "model": "qwen2.5:7b",
                "mean_score": 80.0,
                "cases": [{"case_id": "case_a", "score": 80.0, "elapsed_ms": 1200.0}],
            }
        ],
    }

    def test_logs_params_metrics_and_artifact(self, tmp_path: Path) -> None:
        """Params, sanitized metric keys, and the report artifact are logged."""
        tracker = MagicMock()
        tracker.start_run.return_value = "run-123"
        path = tmp_path / "report.json"
        path.write_text("{}")
        with patch.object(compare, "_experiment_id", return_value="7"):
            info = compare.log_to_mlflow(
                self.REPORT, path, tracker_factory=lambda **kw: tracker
            )

        assert info == {
            "run_id": "run-123",
            "experiment_id": "7",
            "ui_url": "http://localhost:5000/#/experiments/7/runs/run-123",
        }
        params = tracker.log_params.call_args.args[0]
        assert params["models"] == "qwen2.5:7b" and params["case_count"] == 1
        metrics = tracker.log_metrics.call_args.args[0]
        assert metrics == {
            "mean_score.qwen2_5_7b": 80.0,
            "score.qwen2_5_7b.case_a": 80.0,
            "latency_ms.qwen2_5_7b.case_a": 1200.0,
        }
        tracker.log_artifact.assert_called_once_with(str(path))
        tracker.end_run.assert_called_once()

    def test_tracker_failure_is_swallowed(self, tmp_path: Path) -> None:
        """A down tracking server returns None instead of raising."""

        def broken(**kwargs: Any) -> Any:
            raise ConnectionError("mlflow down")

        assert compare.log_to_mlflow(self.REPORT, tmp_path, broken) is None


class TestEvaluationRoutes:
    """``/api/evaluation/cover-letter-compare*``."""

    def test_rejects_large_model(self, client: TestClient) -> None:
        """Non-allow-list models are a 400 before Ollama is called."""
        response = client.post(
            "/api/evaluation/cover-letter-compare", json={"models": ["qwen3.5:9b"]}
        )
        assert response.status_code == 400

    def test_rejects_missing_model(self, client: TestClient) -> None:
        """Models that are not installed are a 400 with a hint."""
        with patch.object(
            compare, "list_installed_models", return_value=["qwen2.5:7b"]
        ):
            response = client.post("/api/evaluation/cover-letter-compare", json={})
        assert response.status_code == 400
        assert "qwen3.5:4b" in response.json()["message"]

    def test_second_run_conflicts(self, client: TestClient) -> None:
        """Only one compare runs at a time."""
        evaluation._run_lock.acquire()
        with patch.object(
            compare, "list_installed_models", return_value=list(compare.ALLOWED_MODELS)
        ):
            response = client.post("/api/evaluation/cover-letter-compare", json={})
        assert response.status_code == 409

    def test_run_completes_and_reports(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """A started compare finishes, saves, logs to MLflow, and frees the slot."""
        report = {"winner": "qwen2.5:7b", "reports": []}
        with (
            patch.object(
                compare,
                "list_installed_models",
                return_value=list(compare.ALLOWED_MODELS),
            ),
            patch.object(compare, "run_compare", return_value=report) as run,
            patch.object(compare, "save_report", return_value=tmp_path / "r.json"),
            patch.object(
                compare, "log_to_mlflow", return_value={"run_id": "r1"}
            ) as log,
        ):
            response = client.post(
                "/api/evaluation/cover-letter-compare",
                json={"models": ["qwen2.5:7b"], "cool_down_s": 0},
            )
        assert response.status_code == 202
        assert response.json()["status"] == "running"
        assert run.call_args.args[0] == ["qwen2.5:7b"]
        assert run.call_args.kwargs["cool_down_s"] == 0
        log.assert_called_once()

        status = client.get("/api/evaluation/cover-letter-compare/status").json()
        assert status["status"] == "completed"
        assert status["report"]["mlflow"] == {"run_id": "r1"}
        assert not evaluation._run_lock.locked()

    def test_failed_run_reports_error(self, client: TestClient) -> None:
        """A failing compare is reported and frees the slot."""
        with (
            patch.object(
                compare,
                "list_installed_models",
                return_value=list(compare.ALLOWED_MODELS),
            ),
            patch.object(compare, "run_compare", side_effect=RuntimeError("gpu gone")),
        ):
            client.post("/api/evaluation/cover-letter-compare", json={})
        status = client.get("/api/evaluation/cover-letter-compare/status").json()
        assert status["status"] == "failed"
        assert "gpu gone" in status["error"]
        assert not evaluation._run_lock.locked()

    def test_latest_returns_saved_report(self, client: TestClient) -> None:
        """The latest endpoint returns the saved report."""
        with patch.object(compare, "load_report", return_value={"winner": "x"}):
            data = client.get("/api/evaluation/cover-letter-compare/latest").json()
        assert data == {"report": {"winner": "x"}}
