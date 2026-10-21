"""
Tests for the offline evaluation harness (Step 3.1).

Covers the metric functions, the JSONL loader and dataset hash, the run
metadata, the JSON report, MLflow logging (a temporary SQLite store, and an
unreachable server), and the grounding suite on a small temporary dataset.
None of these tests write under ``apps/backend-py/data``.
"""

from __future__ import annotations

import json
import math
import re
import time
from datetime import timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic import BaseModel

from src.evaluation.datasets import dataset_sha256, load_jsonl, text_sha256
from src.evaluation.metrics import (
    clean_case_false_positive_rate,
    micro_scores,
    multilabel_scores,
    ndcg_at_k,
    recall_at_k,
)
from src.evaluation.report import (
    EvalReport,
    log_report_to_mlflow,
    resolve_tracking_uri,
    write_report,
)
from src.evaluation.run_metadata import RunMetadata, build_run_metadata

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMultilabelScores:
    """Per-label precision, recall, and F1 over multi-label cases."""

    def test_counts_and_ratios_match_hand_computation(self) -> None:
        """Three cases with two labels give the hand-computed counts."""
        expected = [{"a"}, {"a", "b"}, set()]
        predicted = [{"a"}, {"b"}, {"a"}]

        scores = multilabel_scores(expected, predicted, labels=["a", "b"])

        a = scores["a"]
        assert (a.true_positives, a.false_positives, a.false_negatives) == (1, 1, 1)
        assert a.precision == pytest.approx(0.5)
        assert a.recall == pytest.approx(0.5)
        assert a.f1 == pytest.approx(0.5)
        assert a.support == 2

        b = scores["b"]
        assert (b.true_positives, b.false_positives, b.false_negatives) == (1, 0, 0)
        assert b.precision == pytest.approx(1.0)
        assert b.recall == pytest.approx(1.0)

    def test_undefined_ratios_are_none(self) -> None:
        """A label never expected and never predicted has no precision or recall."""
        scores = multilabel_scores([set()], [set()], labels=["a"])

        assert scores["a"].precision is None
        assert scores["a"].recall is None
        assert scores["a"].f1 is None

    def test_labels_outside_the_label_set_are_ignored(self) -> None:
        """Predictions for labels that are not scored do not count."""
        scores = multilabel_scores([{"a"}], [{"a", "too_short"}], labels=["a"])

        assert set(scores) == {"a"}
        assert scores["a"].false_positives == 0

    def test_length_mismatch_raises(self) -> None:
        """Expected and predicted lists must have the same length."""
        with pytest.raises(ValueError):
            multilabel_scores([{"a"}], [], labels=["a"])

    def test_micro_scores_pool_all_labels(self) -> None:
        """Micro scores sum the counts over every label."""
        expected = [{"a"}, {"a", "b"}, set()]
        predicted = [{"a"}, {"b"}, {"a"}]

        micro = micro_scores(multilabel_scores(expected, predicted, ["a", "b"]))

        assert (micro.true_positives, micro.false_positives) == (2, 1)
        assert micro.false_negatives == 1
        assert micro.precision == pytest.approx(2 / 3)
        assert micro.recall == pytest.approx(2 / 3)

    def test_clean_case_false_positive_rate(self) -> None:
        """Only cases with no expected label count, and any prediction is a miss."""
        expected = [set(), set(), {"a"}]
        predicted = [{"a"}, set(), {"a"}]

        assert clean_case_false_positive_rate(expected, predicted) == pytest.approx(0.5)
        assert clean_case_false_positive_rate([{"a"}], [set()]) is None


class TestRankingMetrics:
    """NDCG@k and recall@k with graded relevance."""

    def test_ndcg_matches_hand_computation(self) -> None:
        """Gains 2^rel - 1 with a log2 position discount."""
        relevance = {"a": 2, "b": 0, "c": 1}
        dcg = 3 / math.log2(2) + 0 + 1 / math.log2(4)
        idcg = 3 / math.log2(2) + 1 / math.log2(3)

        assert ndcg_at_k(["a", "b", "c"], relevance, k=3) == pytest.approx(dcg / idcg)

    def test_ideal_order_scores_one(self) -> None:
        """The ideal ranking has NDCG 1."""
        relevance = {"a": 2, "b": 1, "c": 0}
        assert ndcg_at_k(["a", "b", "c"], relevance, k=3) == pytest.approx(1.0)

    def test_ties_in_relevance_do_not_change_the_score(self) -> None:
        """Swapping two items with the same relevance gives the same NDCG."""
        relevance = {"a": 1, "b": 1, "c": 2}
        first = ndcg_at_k(["c", "a", "b"], relevance, k=3)
        second = ndcg_at_k(["c", "b", "a"], relevance, k=3)
        assert first == pytest.approx(second)

    def test_no_relevant_item_gives_none(self) -> None:
        """NDCG is undefined when no labeled item is relevant."""
        assert ndcg_at_k(["a", "b"], {"a": 0, "b": 0}, k=2) is None

    def test_unlabeled_items_count_as_not_relevant(self) -> None:
        """A ranked item without a label has relevance 0."""
        score = ndcg_at_k(["x", "a"], {"a": 1}, k=2)
        assert score == pytest.approx((1 / math.log2(3)) / 1.0)

    def test_k_cuts_the_ranking(self) -> None:
        """Only the first k ranked items count."""
        assert ndcg_at_k(["b", "a"], {"a": 2, "b": 0}, k=1) == pytest.approx(0.0)

    def test_recall_at_k(self) -> None:
        """Recall@k counts relevant items in the first k."""
        relevance = {"a": 2, "b": 1, "c": 0, "d": 1}
        assert recall_at_k(["a", "c", "b", "d"], relevance, k=2) == pytest.approx(1 / 3)
        assert recall_at_k(["a"], {"a": 0}, k=1) is None


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


class _Row(BaseModel):
    """Small schema for loader tests."""

    case_id: str
    value: int


class TestDatasets:
    """JSONL loading and dataset hashing."""

    def test_load_jsonl_skips_blank_lines(self, tmp_path: Path) -> None:
        """Each non-blank line is one validated case."""
        path = tmp_path / "cases.jsonl"
        path.write_text(
            '{"case_id": "a", "value": 1}\n\n{"case_id": "b", "value": 2}\n',
            encoding="utf-8",
        )

        rows = load_jsonl(path, _Row)

        assert [r.case_id for r in rows] == ["a", "b"]

    def test_load_jsonl_names_the_bad_line(self, tmp_path: Path) -> None:
        """A case that fails validation raises with its line number."""
        path = tmp_path / "cases.jsonl"
        path.write_text(
            '{"case_id": "a", "value": 1}\n{"case_id": "b"}\n', encoding="utf-8"
        )

        with pytest.raises(ValueError, match="line 2"):
            load_jsonl(path, _Row)

    def test_hash_changes_when_one_case_changes(self, tmp_path: Path) -> None:
        """Editing one case gives a new dataset hash."""
        path = tmp_path / "cases.jsonl"
        path.write_text('{"case_id": "a", "value": 1}\n', encoding="utf-8")
        before = dataset_sha256(path)

        path.write_text('{"case_id": "a", "value": 2}\n', encoding="utf-8")

        assert dataset_sha256(path) != before
        assert re.fullmatch(r"[0-9a-f]{64}", before)

    def test_hash_ignores_line_endings(self, tmp_path: Path) -> None:
        """CRLF and LF copies of the same dataset have the same hash."""
        lf = tmp_path / "lf.jsonl"
        crlf = tmp_path / "crlf" / "lf.jsonl"
        crlf.parent.mkdir()
        lf.write_bytes(b'{"case_id": "a", "value": 1}\n')
        crlf.write_bytes(b'{"case_id": "a", "value": 1}\r\n')

        assert dataset_sha256(lf) == dataset_sha256(crlf)

    def test_text_hash_is_stable(self) -> None:
        """The same prompt parts give the same hash; different parts do not."""
        assert text_sha256("a", "b") == text_sha256("a", "b")
        assert text_sha256("a", "b") != text_sha256("ab")


# ---------------------------------------------------------------------------
# Run metadata
# ---------------------------------------------------------------------------


class TestRunMetadata:
    """Git state, dataset hash, and model parameters."""

    def test_metadata_in_this_repository(self, tmp_path: Path) -> None:
        """Inside the repository the SHA is 40 hex characters."""
        path = tmp_path / "cases.jsonl"
        path.write_text('{"case_id": "a", "value": 1}\n', encoding="utf-8")

        metadata = build_run_metadata(
            "grounding", [path], case_count=1, model="none", temperature=0.0
        )

        assert re.fullmatch(r"[0-9a-f]{40}", metadata.git_sha)
        assert isinstance(metadata.git_dirty, bool)
        assert metadata.dataset_sha256 == dataset_sha256(path)
        assert metadata.case_count == 1
        assert metadata.started_at.tzinfo is not None

    def test_slow_git_status_keeps_the_sha(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A timed-out ``git status`` leaves the SHA and makes the flag None.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
        """
        import subprocess

        from src.evaluation import run_metadata

        real_run = subprocess.run

        def fake_run(cmd: List[str], *args: Any, **kwargs: Any) -> Any:
            """Time out ``git status``; run everything else for real.

            Args:
                cmd: Command and arguments.
                *args: Positional arguments for ``subprocess.run``.
                **kwargs: Keyword arguments for ``subprocess.run``.

            Returns:
                The real result for commands other than ``git status``.

            Raises:
                subprocess.TimeoutExpired: For ``git status``.
            """
            if "status" in cmd:
                raise subprocess.TimeoutExpired(cmd, timeout=1)
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(run_metadata.subprocess, "run", fake_run)

        sha, dirty = run_metadata.collect_git_state(run_metadata.BACKEND_DIR)

        assert re.fullmatch(r"[0-9a-f]{40}", sha)
        assert dirty is None

    def test_git_status_takes_no_index_lock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``git status`` runs with ``--no-optional-locks``.

        A killed ``git status`` that holds ``.git/index.lock`` blocks every
        later git command in the repository.

        Args:
            monkeypatch: Pytest monkeypatch fixture.
        """
        import subprocess

        from src.evaluation import run_metadata

        commands: List[List[str]] = []
        real_run = subprocess.run

        def recording_run(cmd: List[str], *args: Any, **kwargs: Any) -> Any:
            """Record each command, then run it for real.

            Args:
                cmd: Command and arguments.
                *args: Positional arguments for ``subprocess.run``.
                **kwargs: Keyword arguments for ``subprocess.run``.

            Returns:
                The real result.
            """
            commands.append(list(cmd))
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(run_metadata.subprocess, "run", recording_run)

        run_metadata.collect_git_state(run_metadata.BACKEND_DIR)

        status_cmds = [c for c in commands if "status" in c]
        assert status_cmds, "git status was not called"
        assert all(
            c[:2] == ["git", "--no-optional-locks"] for c in status_cmds
        ), status_cmds

    def test_metadata_outside_a_repository(self, tmp_path: Path) -> None:
        """Without git history the SHA is "unknown" and the dirty flag is None."""
        path = tmp_path / "cases.jsonl"
        path.write_text('{"case_id": "a", "value": 1}\n', encoding="utf-8")

        metadata = build_run_metadata("grounding", [path], 1, repo_dir=tmp_path)

        assert metadata.git_sha == "unknown"
        assert metadata.git_dirty is None


# ---------------------------------------------------------------------------
# Report and MLflow
# ---------------------------------------------------------------------------


def _report(tmp_path: Path) -> EvalReport:
    """Build a small report for report and MLflow tests.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        A report with two metrics, one of them undefined.
    """
    path = tmp_path / "cases.jsonl"
    path.write_text('{"case_id": "a", "value": 1}\n', encoding="utf-8")
    # Outside the repository: skips the slow git calls; SHA is "unknown".
    metadata = build_run_metadata("grounding", [path], case_count=1, repo_dir=tmp_path)
    return EvalReport(
        suite="grounding",
        metadata=metadata,
        metrics={"micro.precision": 0.75, "micro.recall": None},
        details={"cases": []},
    )


class TestReport:
    """JSON report files and MLflow logging."""

    def test_write_report(self, tmp_path: Path) -> None:
        """The report is written as JSON under the suite folder."""
        report = _report(tmp_path)

        path = write_report(report, out_dir=tmp_path / "eval")

        assert path.parent == tmp_path / "eval" / "grounding"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["metrics"]["micro.precision"] == 0.75
        assert data["metadata"]["git_sha"] == report.metadata.git_sha

    def test_default_tracking_uri_is_absolute_sqlite_under_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without MLFLOW_TRACKING_URI the store is SQLite at an absolute path."""
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

        uri = resolve_tracking_uri()

        assert uri.startswith("sqlite:///")
        db_path = Path(uri[len("sqlite:///") :])
        assert db_path.is_absolute()
        assert db_path.parts[-2:] == ("data", "mlflow.db")

    def test_tracking_uri_from_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MLFLOW_TRACKING_URI wins when it is set."""
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        assert resolve_tracking_uri() == "http://mlflow:5000"

    def test_unreachable_server_skips_mlflow_quickly(self, tmp_path: Path) -> None:
        """A down server is skipped fast, and the report file stays."""
        report = _report(tmp_path)
        path = write_report(report, out_dir=tmp_path / "eval")

        started = time.monotonic()
        run_id = log_report_to_mlflow(
            report, path, tracking_uri="http://127.0.0.1:9", timeout_s=1.0
        )

        assert run_id is None
        assert time.monotonic() - started < 10
        assert path.exists()

    def test_logs_run_to_sqlite_store(self, tmp_path: Path) -> None:
        """A run in a temporary SQLite store has the metadata and the metrics."""
        import mlflow
        from mlflow.tracking import MlflowClient

        report = _report(tmp_path)
        path = write_report(report, out_dir=tmp_path / "eval")
        uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
        previous_uri = mlflow.get_tracking_uri()

        run_id = log_report_to_mlflow(
            report,
            path,
            tracking_uri=uri,
            artifact_location=(tmp_path / "artifacts").as_uri(),
            experiment_name="eval_test",
        )

        assert run_id is not None
        assert mlflow.get_tracking_uri() == previous_uri
        run = MlflowClient(tracking_uri=uri).get_run(run_id)
        assert run.data.tags["git_sha"] == report.metadata.git_sha
        assert run.data.tags["dataset_sha256"] == report.metadata.dataset_sha256
        assert run.data.metrics["micro.precision"] == pytest.approx(0.75)
        assert "micro.recall" not in run.data.metrics


# ---------------------------------------------------------------------------
# Grounding suite
# ---------------------------------------------------------------------------


PROFILE: Dict[str, Any] = {
    "name": "Alex Chen",
    "contact": {"email": "alex@example.com", "location": "Singapore"},
    "summary": "Software engineer focused on Python APIs and data pipelines.",
    "skills": [
        {
            "name": "Python",
            "category": "programming_language",
            "years_of_experience": 4,
        },
        {"name": "FastAPI", "category": "framework", "years_of_experience": 2},
        {"name": "PostgreSQL", "category": "database", "years_of_experience": 2},
    ],
    "experience": [
        {
            "company": "DataWorks",
            "title": "Software Engineer",
            "location": "Singapore",
            "start_date": "2022-01-01T00:00:00",
            "current": True,
            "description": "Built internal APIs and ETL jobs.",
            "highlights": ["Reduced API latency by 35%"],
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
        }
    ],
}

JOB: Dict[str, Any] = {
    "title": "Backend Engineer",
    "company": "Harbor Labs",
    "job_id": "eval-job-1",
    "source": "manual",
    "location": "Singapore",
    "description": "Build FastAPI services and PostgreSQL schemas.",
}


def _write_grounding_dataset(directory: Path, cases: List[Dict[str, Any]]) -> Path:
    """Write a grounding dataset (profiles.json and cases.jsonl).

    Args:
        directory: Target directory.
        cases: Case dicts without the shared job and profile.

    Returns:
        The dataset directory.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "profiles.json").write_text(
        json.dumps({"alex": PROFILE}), encoding="utf-8"
    )
    lines = [json.dumps({"profile_id": "alex", "job": JOB, **case}) for case in cases]
    (directory / "cases.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


class TestGroundingSuite:
    """The grounding suite runs the deterministic validator on labeled cases."""

    def test_runs_validator_and_scores_grounding_labels(self, tmp_path: Path) -> None:
        """A fabricated technology is found; metrics and case details are filled."""
        from src.evaluation.suites.grounding import run_grounding_suite

        dataset = _write_grounding_dataset(
            tmp_path / "grounding",
            [
                {
                    "case_id": "fabricated_tech",
                    "letter": (
                        "Dear Harbor Labs team,\n\nAt DataWorks I build FastAPI "
                        "services in Python. I also run Kubernetes clusters and "
                        "write Terraform modules for every deployment.\n\nI look "
                        "forward to discussing the Backend Engineer role."
                    ),
                    "expected_issues": ["fabricated_technology"],
                }
            ],
        )

        report = run_grounding_suite(dataset)

        assert report.suite == "grounding"
        assert report.metadata.case_count == 1
        case = report.details["cases"][0]
        assert "fabricated_technology" in case["predicted"]
        assert report.metrics["recall.fabricated_technology"] == pytest.approx(1.0)
        assert "micro.f1" in report.metrics

    def test_unknown_expected_label_is_rejected(self, tmp_path: Path) -> None:
        """Expected issues must be grounding labels."""
        from src.evaluation.suites.grounding import run_grounding_suite

        dataset = _write_grounding_dataset(
            tmp_path / "grounding",
            [
                {
                    "case_id": "bad_label",
                    "letter": "Hello.",
                    "expected_issues": ["too_short"],
                }
            ],
        )

        with pytest.raises(ValueError, match="line 1"):
            run_grounding_suite(dataset)


def test_report_metadata_round_trips(tmp_path: Path) -> None:
    """A report read back from JSON keeps the metadata types."""
    report = _report(tmp_path)
    path = write_report(report, out_dir=tmp_path / "eval")

    loaded = EvalReport.model_validate_json(path.read_text(encoding="utf-8"))

    assert isinstance(loaded.metadata, RunMetadata)
    assert loaded.metadata.started_at == report.metadata.started_at
    assert loaded.metadata.started_at.utcoffset() == timezone.utc.utcoffset(None)
