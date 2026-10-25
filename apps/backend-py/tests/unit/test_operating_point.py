"""
Pipeline sweep, operating-point selection, Wilson intervals, and the
held-out guard (Step 3.3 Stage B B2b).

Tests write only under ``tmp_path``. They do not create the real
held-out marker.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.evaluation.metrics import wilson_interval
from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import build_run_metadata
from src.evaluation.suites.emscad import run_emscad_suite
from src.evaluation.suites.scam import (
    MAX_FALSE_POSITIVE_RATE,
    MIN_DROP_PRECISION,
    MIN_FLAGGED_FRAUDS,
    evaluate_scam_listings,
    select_operating_point,
)
from src.models.job_listing import JobListing, JobSource
from tests.unit.test_scam_suite import TestEmscadSuite, _FakeDetector


def _listing(job_id: str, description: str) -> JobListing:
    """
    Build a listing for the sweep tests.

    Args:
        job_id: Listing identifier.
        description: Posting text.

    Returns:
        A ``JobListing``.
    """
    return JobListing(
        title="Clerk",
        company="Example Co",
        job_id=job_id,
        source=JobSource.MANUAL,
        description=description,
    )


def _sweep_row(
    threshold: float,
    *,
    recall: Optional[float],
    false_positive_rate: Optional[float],
    precision: Optional[float],
    true_positives: int,
    false_positives: int = 0,
    false_negatives: int = 0,
    true_negatives: int = 0,
) -> Dict[str, Any]:
    """
    Build one pipeline-sweep row for selection tests.

    Args:
        threshold: Detector threshold.
        recall: Sweep recall.
        false_positive_rate: Sweep false-positive rate.
        precision: Sweep precision.
        true_positives: Flagged frauds.
        false_positives: Flagged legitimate rows.
        false_negatives: Missed frauds.
        true_negatives: Unflagged legitimate rows.

    Returns:
        A sweep row dict.
    """
    return {
        "threshold": threshold,
        "recall": recall,
        "false_positive_rate": false_positive_rate,
        "precision": precision,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
    }


def _all_thresholds(
    overrides: Dict[float, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Fill a 0.05-to-1.00 sweep and apply per-threshold overrides.

    Args:
        overrides: Fields to replace on named thresholds.

    Returns:
        Twenty sweep rows.
    """
    rows: List[Dict[str, Any]] = []
    for step in range(1, 21):
        threshold = round(step / 20, 2)
        base = _sweep_row(
            threshold,
            recall=0.0,
            false_positive_rate=0.02,
            precision=0.0,
            true_positives=0,
        )
        base.update(overrides.get(threshold, {}))
        rows.append(base)
    return rows


class TestSelectOperatingPoint:
    """Rules S1 and S2 (decision 5)."""

    def test_tie_goes_to_the_higher_threshold(self) -> None:
        """Equal recall and a qualifying FPR pick the higher threshold."""
        sweep = _all_thresholds(
            {
                0.50: {
                    "recall": 0.40,
                    "false_positive_rate": 0.001,
                    "precision": 0.60,
                    "true_positives": 12,
                },
                0.80: {
                    "recall": 0.40,
                    "false_positive_rate": 0.001,
                    "precision": 0.60,
                    "true_positives": 12,
                },
            }
        )

        result = select_operating_point(sweep)

        assert result["threshold"] == pytest.approx(0.80)
        assert "tie" in result["reason"]

    def test_no_qualifying_threshold_uses_1(self) -> None:
        """When every FPR is above the cap, ``t*`` is 1.00."""
        sweep = _all_thresholds({})

        result = select_operating_point(sweep)

        assert result["threshold"] == pytest.approx(1.00)
        assert result["action"] == "flag"
        assert "1.00" in result["reason"]

    def test_fpr_exactly_at_the_limit_qualifies(self) -> None:
        """An FPR of 0.005 is allowed."""
        sweep = _all_thresholds(
            {
                0.60: {
                    "recall": 0.30,
                    "false_positive_rate": MAX_FALSE_POSITIVE_RATE,
                    "precision": 0.60,
                    "true_positives": 12,
                },
                0.70: {
                    "recall": 0.10,
                    "false_positive_rate": 0.004,
                    "precision": 0.60,
                    "true_positives": 12,
                },
            }
        )

        result = select_operating_point(sweep)

        assert result["threshold"] == pytest.approx(0.60)

    def test_precision_and_ten_frauds_select_drop(self) -> None:
        """Precision 0.50 and 10 flagged frauds allow ``drop``."""
        sweep = _all_thresholds(
            {
                0.55: {
                    "recall": 0.20,
                    "false_positive_rate": 0.001,
                    "precision": MIN_DROP_PRECISION,
                    "true_positives": MIN_FLAGGED_FRAUDS,
                }
            }
        )

        result = select_operating_point(sweep)

        assert result["threshold"] == pytest.approx(0.55)
        assert result["action"] == "drop"

    def test_precision_below_limit_selects_flag(self) -> None:
        """Precision just below 0.50 forces ``flag``."""
        sweep = _all_thresholds(
            {
                0.55: {
                    "recall": 0.20,
                    "false_positive_rate": 0.001,
                    "precision": 0.49,
                    "true_positives": MIN_FLAGGED_FRAUDS,
                }
            }
        )

        result = select_operating_point(sweep)

        assert result["action"] == "flag"

    def test_fewer_than_ten_frauds_selects_flag(self) -> None:
        """Nine flagged frauds force ``flag`` even at precision 0.50."""
        sweep = _all_thresholds(
            {
                0.55: {
                    "recall": 0.20,
                    "false_positive_rate": 0.001,
                    "precision": MIN_DROP_PRECISION,
                    "true_positives": MIN_FLAGGED_FRAUDS - 1,
                }
            }
        )

        result = select_operating_point(sweep)

        assert result["action"] == "flag"


class TestWilsonInterval:
    """Wilson 95 percent interval helper."""

    def test_five_of_ten(self) -> None:
        """5 of 10 is about (0.2366, 0.7634)."""
        low, high = wilson_interval(5, 10)

        assert low == pytest.approx(0.2366, abs=0.0005)
        assert high == pytest.approx(0.7634, abs=0.0005)

    def test_zero_trials_is_none(self) -> None:
        """Zero trials return None."""
        assert wilson_interval(0, 0) is None


class TestPipelineSweep:
    """Pipeline decision sweep includes the quick filter."""

    def test_counts_include_the_quick_filter(self) -> None:
        """
        A filter-only fraud stays flagged at every threshold.

        Returns:
            None.
        """
        items = [
            (
                "scam_payment__filter",
                _listing("f1", "Pay the deposit in bitcoin."),
                "scam",
                ["payment"],
            ),
            (
                "scam_payment__detector",
                _listing("d1", "No interview required, start tomorrow."),
                "scam",
                ["payment"],
            ),
            (
                "legit_written__low",
                _listing("l1", "Keep the quay chart current."),
                "legit",
                [],
            ),
        ]
        detector = _FakeDetector(
            mapping={
                "f1": (False, 0.0, []),
                "d1": (False, 0.60, ["urgency"]),
                "l1": (False, 0.20, []),
            }
        )

        metrics, details = evaluate_scam_listings(
            items,
            detector=detector,
            filter_hit_fn=lambda job: job.job_id == "f1",
        )

        sweep = details["pipeline_sweep"]
        thresholds = [row["threshold"] for row in sweep]
        assert thresholds == [round(step / 20, 2) for step in range(1, 21)]
        assert "threshold_sweep" in details

        at_high = next(row for row in sweep if row["threshold"] == 1.00)
        assert at_high["true_positives"] == 1
        assert at_high["false_positives"] == 0
        assert at_high["false_negatives"] == 1
        assert at_high["true_negatives"] == 1
        assert at_high["recall"] == pytest.approx(0.5)
        assert at_high["false_positive_rate"] == pytest.approx(0.0)

        at_mid = next(row for row in sweep if row["threshold"] == 0.60)
        assert at_mid["true_positives"] == 2
        assert at_mid["false_positives"] == 0
        assert at_mid["false_negatives"] == 0
        assert at_mid["true_negatives"] == 1

        at_low = next(row for row in sweep if row["threshold"] == 0.20)
        assert at_low["true_positives"] == 2
        assert at_low["false_positives"] == 1
        assert at_low["false_negatives"] == 0
        assert at_low["true_negatives"] == 0

        assert metrics["precision.ci95_low"] is not None
        assert metrics["precision.ci95_high"] is not None
        assert metrics["recall.ci95_low"] is not None
        assert metrics["recall.ci95_high"] is not None
        assert metrics["false_positive_rate.ci95_low"] is not None
        assert metrics["false_positive_rate.ci95_high"] is not None


class TestHeldoutGuard:
    """Refuse a second held-out run; write the marker after the first."""

    def _tiny_report(self, tmp_path: Path) -> EvalReport:
        """
        Build a one-case report for the CLI guard.

        Args:
            tmp_path: Temporary folder.

        Returns:
            A tiny ``EvalReport``.
        """
        path = tmp_path / "cases.jsonl"
        path.write_text("{}\n", encoding="utf-8")
        return EvalReport(
            suite="emscad",
            metadata=build_run_metadata("emscad", [path], 1, repo_dir=tmp_path),
            metrics={"precision": 1.0},
            details={},
            tags={"part": "heldout"},
        )

    def test_refuses_when_the_marker_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Exit code 1 when the marker is already present.

        Args:
            tmp_path: Temporary folder.
            monkeypatch: Marker path and suite replacement.
        """
        import main as cli
        from src.evaluation.suites import emscad as emscad_suite
        from tests.unit.test_cli import parse

        marker = tmp_path / "heldout_used.json"
        marker.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(emscad_suite, "HELDOUT_USED_MARKER", marker)
        called: List[str] = []

        def fake_emscad(dataset: Path, **kwargs: Any) -> EvalReport:
            called.append("ran")
            return self._tiny_report(tmp_path)

        monkeypatch.setattr(
            "src.evaluation.suites.get_suite",
            lambda name: (fake_emscad, tmp_path),
        )
        args = parse(
            [
                "eval",
                "emscad",
                "--dataset",
                str(tmp_path),
                "--out",
                str(tmp_path / "out"),
                "--no-mlflow",
                "--part",
                "heldout",
            ]
        )

        assert cli.run_eval_command(args) == 1
        assert called == []

    def test_writes_the_marker_after_a_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A successful held-out run writes the marker, including ``--out``.

        Args:
            tmp_path: Temporary folder.
            monkeypatch: Marker path and suite replacement.
        """
        import main as cli
        from src.evaluation.suites import emscad as emscad_suite
        from src.scoring.scam_detector import (
            DEFAULT_SCAM_ACTION,
            DEFAULT_SCAM_THRESHOLD,
        )
        from tests.unit.test_cli import parse

        marker = tmp_path / "heldout_used.json"
        monkeypatch.setattr(emscad_suite, "HELDOUT_USED_MARKER", marker)

        def fake_emscad(dataset: Path, **kwargs: Any) -> EvalReport:
            return self._tiny_report(tmp_path)

        monkeypatch.setattr(
            "src.evaluation.suites.get_suite",
            lambda name: (fake_emscad, tmp_path),
        )
        out = tmp_path / "custom-out"
        args = parse(
            [
                "eval",
                "emscad",
                "--dataset",
                str(tmp_path),
                "--out",
                str(out),
                "--no-mlflow",
                "--part",
                "heldout",
            ]
        )

        assert cli.run_eval_command(args) == 0
        assert marker.is_file()
        payload = json.loads(marker.read_text(encoding="utf-8"))
        assert payload["git_sha"]
        assert payload["dataset_sha256"]
        assert payload["threshold"] == DEFAULT_SCAM_THRESHOLD
        assert payload["action"] == DEFAULT_SCAM_ACTION
        assert payload["used_at"]
        assert str(out) in payload["report_path"] or "emscad" in payload["report_path"]
        assert (
            Path(tmp_path / "data" / "eval" / "emscad" / "heldout_used.json") != marker
        )


class TestEmscadSelectionPlacement:
    """The tuning report selects; the held-out report does not."""

    def test_tuning_has_selection_and_heldout_does_not(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Only the tuning report stores ``details['selection']``.

        Args:
            tmp_path: Temporary CSV folder.
            monkeypatch: Detector replacement.
        """
        helper = TestEmscadSuite()
        helper._write_csv(
            tmp_path,
            [helper._row(f"L{i}", "0") for i in range(4)]
            + [helper._row(f"S{i}", "1") for i in range(4)],
        )
        monkeypatch.setattr(
            "src.evaluation.suites.emscad.JobScamDetector",
            lambda threshold=0.7: _FakeDetector(),
        )
        monkeypatch.setattr(
            "src.evaluation.suites.emscad.ScamFilter.is_potential_scam",
            lambda job: False,
        )

        tuning = run_emscad_suite(tmp_path, part="tuning")
        held = run_emscad_suite(tmp_path, part="heldout")

        assert "selection" in tuning.details
        assert "threshold" in tuning.details["selection"]
        assert "action" in tuning.details["selection"]
        assert "reason" in tuning.details["selection"]
        assert "selection" not in held.details
        assert "pipeline_sweep" in tuning.details
        assert "pipeline_sweep" in held.details
