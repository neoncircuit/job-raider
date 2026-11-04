"""
CI gate for the ranking suite on the committed set (Step 3.4).

The heuristic and BM25 methods are deterministic, so the gate pins their
NDCG@10 and recall@10 for each profile with no margin: a metric must stay at
or above its pin. It also pins the dataset SHA-256, so a changed set fails
before any metric is compared. Dense and hybrid need the embedding model, so
they run locally and are not part of this gate.
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest

from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import RunMetadata
from src.evaluation.suites.ranking import (
    CI_METHODS,
    DEFAULT_DATASET_DIR,
    TOP_K,
    load_ranking_set,
    run_ranking_suite,
)

THRESHOLDS_PATH = DEFAULT_DATASET_DIR / "thresholds.json"


def threshold_check(
    report: EvalReport, thresholds: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """
    Compare a ranking report with the pinned minimums.

    The dataset SHA-256 is checked first. When it differs, no metric is
    compared.

    Args:
        report: Report from ``run_ranking_suite``.
        thresholds: Parsed ``thresholds.json``.

    Returns:
        ``(violations, tightenable)``: values below their pins or not in the
        report, and values above their pins.
    """
    pinned_sha = thresholds["dataset_sha256"]
    if report.metadata.dataset_sha256 != pinned_sha:
        return [
            f"dataset changed: {report.metadata.dataset_sha256} is not the pinned "
            f"{pinned_sha}; run a new baseline and pin new metrics"
        ], []

    violations: List[str] = []
    tightenable: List[str] = []
    for metric, pin in sorted(thresholds["minimums"].items()):
        value = report.metrics.get(metric)
        if value is None:
            violations.append(f"{metric}: no value (pin {pin})")
        elif value < pin:
            violations.append(f"{metric}: {value} (pin {pin})")
        elif value > pin:
            tightenable.append(f"{metric}: {value} (pin {pin})")
    return violations, tightenable


def assert_pins_met(report: EvalReport, thresholds: Dict[str, Any]) -> None:
    """
    Fail on a pin violation, and warn about pins that can go up.

    Args:
        report: Report from ``run_ranking_suite``.
        thresholds: Parsed ``thresholds.json``.

    Raises:
        AssertionError: When a metric is below its pin or the dataset changed.
    """
    violations, tightenable = threshold_check(report, thresholds)
    if tightenable:
        warnings.warn(
            "ranking metrics above their pins, tighten thresholds.json: "
            + "; ".join(tightenable),
            stacklevel=1,
        )
    assert not violations, "\n".join(violations)


def test_ranking_suite_meets_the_pinned_metrics() -> None:
    """The committed set stays at or above every pin (the CI gate)."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    assert_pins_met(run_ranking_suite(), thresholds)


def test_thresholds_file_records_each_change() -> None:
    """Every pin change has a dated entry with a reason and an MLflow run."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    assert thresholds["suite"] == "ranking"
    assert thresholds["baseline"] == "after-r5"
    assert thresholds["changes"]
    for entry in thresholds["changes"]:
        assert entry["date"] and entry["reason"] and entry["mlflow_run"], entry


def test_the_pins_cover_each_ci_method_and_profile() -> None:
    """Each CI method has both metrics for each profile, and nothing else."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    expected = {
        f"{method}_{profile}_{metric}_at_{TOP_K}"
        for method in CI_METHODS
        for profile in load_ranking_set().profiles
        for metric in ("ndcg", "recall")
    }
    assert set(thresholds["minimums"]) == expected


def _report(
    *,
    sha: str = "abc",
    metrics: Optional[Dict[str, Optional[float]]] = None,
) -> EvalReport:
    """
    Build a small synthetic ranking report.

    Args:
        sha: Dataset SHA-256 to report.
        metrics: The metrics.

    Returns:
        A report shaped like ``run_ranking_suite`` output.
    """
    return EvalReport(
        suite="ranking",
        metadata=RunMetadata(
            suite="ranking",
            git_sha="0000000",
            git_dirty=False,
            dataset_sha256=sha,
            case_count=140,
            started_at=datetime(2026, 11, 4, tzinfo=timezone.utc),
        ),
        metrics=metrics or {},
        details={},
    )


_PINS: Dict[str, Any] = {
    "dataset_sha256": "abc",
    "minimums": {"bm25_fresh_ml_ndcg_at_10": 0.8638, "heuristic_ndcg": 0.5},
}


def test_a_metric_at_its_pin_passes() -> None:
    """A metric equal to its pin is neither a violation nor tightenable."""
    report = _report(
        metrics={"bm25_fresh_ml_ndcg_at_10": 0.8638, "heuristic_ndcg": 0.5}
    )
    assert threshold_check(report, _PINS) == ([], [])


def test_a_metric_below_its_pin_is_a_violation() -> None:
    """The smallest reported drop fails, with the metric named."""
    report = _report(
        metrics={"bm25_fresh_ml_ndcg_at_10": 0.8637, "heuristic_ndcg": 0.5}
    )
    violations, tightenable = threshold_check(report, _PINS)
    assert violations == ["bm25_fresh_ml_ndcg_at_10: 0.8637 (pin 0.8638)"]
    assert tightenable == []


def test_a_metric_above_its_pin_can_be_tightened() -> None:
    """A better metric is not a violation; it is listed for tightening."""
    report = _report(metrics={"bm25_fresh_ml_ndcg_at_10": 0.9, "heuristic_ndcg": 0.5})
    violations, tightenable = threshold_check(report, _PINS)
    assert violations == []
    assert tightenable == ["bm25_fresh_ml_ndcg_at_10: 0.9 (pin 0.8638)"]


def test_a_metric_without_a_value_is_a_violation() -> None:
    """A pinned metric that is missing or None fails."""
    report = _report(metrics={"bm25_fresh_ml_ndcg_at_10": None})
    violations, _ = threshold_check(report, _PINS)
    assert violations == [
        "bm25_fresh_ml_ndcg_at_10: no value (pin 0.8638)",
        "heuristic_ndcg: no value (pin 0.5)",
    ]


def test_a_violation_fails_the_gate() -> None:
    """The gate assertion fails and names the metric."""
    report = _report(
        metrics={"bm25_fresh_ml_ndcg_at_10": 0.8637, "heuristic_ndcg": 0.5}
    )
    with pytest.raises(AssertionError, match="bm25_fresh_ml_ndcg_at_10: 0.8637"):
        assert_pins_met(report, _PINS)


def test_a_better_metric_warns_and_passes_the_gate() -> None:
    """The gate passes and names the pin that can go up."""
    report = _report(metrics={"bm25_fresh_ml_ndcg_at_10": 0.9, "heuristic_ndcg": 0.5})
    with pytest.warns(UserWarning, match="bm25_fresh_ml_ndcg_at_10: 0.9"):
        assert_pins_met(report, _PINS)


def test_a_changed_dataset_fails_before_any_metric() -> None:
    """A different dataset SHA-256 is the only violation reported."""
    report = _report(sha="def", metrics={"heuristic_ndcg": 0.1})
    violations, tightenable = threshold_check(report, _PINS)
    assert len(violations) == 1 and violations[0].startswith("dataset changed")
    assert tightenable == []
