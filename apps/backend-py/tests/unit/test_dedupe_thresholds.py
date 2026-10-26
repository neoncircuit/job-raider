"""
CI gate for the dedupe suite on the committed set (Step 3.5, B2b).

The suite is deterministic, so the gate pins counts, not ratios. It also
pins the dataset SHA-256. A merged ``different`` pair is a safety failure.
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import RunMetadata
from src.evaluation.suites.dedupe import DEFAULT_DATASET_DIR, run_dedupe_suite

THRESHOLDS_PATH = DEFAULT_DATASET_DIR / "thresholds.json"


def _is_identified(row: Dict[str, Any]) -> bool:
    """
    Return whether a per-pair row is identified.

    Args:
        row: One case row from the report.

    Returns:
        True when the pair was merged or flagged.
    """
    return bool(row.get("merged") or row.get("flagged"))


def _compare_count(
    kind: str, count: int, pin: int, cases: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Compare one count with its pin.

    Args:
        kind: Count name.
        count: Count in the report.
        pin: Maximum allowed count.
        cases: Cases behind the count.

    Returns:
        ``(violation, tightenable)``; each is a message or ``None``.
    """
    if count > pin:
        return f"{kind}: {count} (pin {pin}); cases: {', '.join(cases)}", None
    if count < pin:
        return None, f"{kind}: {count} (pin {pin})"
    return None, None


def threshold_check(
    report: EvalReport, thresholds: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """
    Compare a dedupe report with the pinned counts.

    The dataset SHA-256 is checked first. When it differs, no count is
    compared.

    Args:
        report: Report from ``run_dedupe_suite``.
        thresholds: Parsed ``thresholds.json``.

    Returns:
        ``(violations, tightenable)``: values above their pins, and values
        below their pins.
    """
    pinned_sha = thresholds["dataset_sha256"]
    if report.metadata.dataset_sha256 != pinned_sha:
        return [
            f"dataset changed: {report.metadata.dataset_sha256} is not the pinned "
            f"{pinned_sha}; run a new baseline and pin new counts"
        ], []

    rows = list(report.details.get("cases", []))
    false_identified = [
        str(row["case_id"])
        for row in rows
        if row.get("expected") == "different" and _is_identified(row)
    ]
    missed_same = [
        str(row["case_id"])
        for row in rows
        if row.get("expected") == "same" and not _is_identified(row)
    ]
    merged_different = [
        str(row["case_id"])
        for row in rows
        if row.get("expected") == "different"
        and (row.get("merged") or row.get("merged_reversed"))
    ]
    pins = thresholds["counts"]
    violations: List[str] = []
    tightenable: List[str] = []
    for kind, count, pin, cases in (
        (
            "false_identified",
            len(false_identified),
            pins["max_false_identified"],
            false_identified,
        ),
        ("missed_same", len(missed_same), pins["max_missed_same"], missed_same),
        (
            "merged_different",
            len(merged_different),
            pins["max_merged_different"],
            merged_different,
        ),
    ):
        violation, tighter = _compare_count(kind, count, pin, cases)
        violations.extend([violation] if violation else [])
        tightenable.extend([tighter] if tighter else [])
    return violations, tightenable


def test_dedupe_suite_meets_the_pinned_counts() -> None:
    """The committed set stays at or below every pin (the CI gate)."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    violations, tightenable = threshold_check(run_dedupe_suite(), thresholds)
    if tightenable:
        warnings.warn(
            "dedupe counts below their pins, tighten thresholds.json: "
            + "; ".join(tightenable),
            stacklevel=1,
        )
    assert not violations, "\n".join(violations)


def test_thresholds_file_records_each_change() -> None:
    """Every pin change has a dated entry with a reason and an MLflow run."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    assert thresholds["suite"] == "dedupe"
    assert thresholds["baseline"] == "B2a"
    assert thresholds["changes"]
    for entry in thresholds["changes"]:
        assert entry["date"] and entry["reason"] and entry["mlflow_run"], entry


def test_merged_different_pin_is_a_safety_rule_and_stays_at_zero() -> None:
    """The merged-different pin is 0. Raising it is not a measured change."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    assert thresholds["counts"]["max_merged_different"] == 0, (
        "max_merged_different is a safety rule and not a measured pin; "
        "it must not be raised"
    )


def _report(
    *,
    sha: str = "abc",
    cases: Optional[List[Dict[str, Any]]] = None,
) -> EvalReport:
    """
    Build a small synthetic dedupe report.

    Args:
        sha: Dataset SHA-256 to report.
        cases: Per-pair rows.

    Returns:
        A report shaped like ``run_dedupe_suite`` output.
    """
    rows = cases or []
    return EvalReport(
        suite="dedupe",
        metadata=RunMetadata(
            suite="dedupe",
            git_sha="0000000",
            git_dirty=False,
            dataset_sha256=sha,
            case_count=len(rows) or 1,
            started_at=datetime(2026, 10, 26, tzinfo=timezone.utc),
        ),
        metrics={},
        details={"cases": rows},
    )


_PINS: Dict[str, Any] = {
    "dataset_sha256": "abc",
    "counts": {
        "max_false_identified": 1,
        "max_missed_same": 1,
        "max_merged_different": 0,
    },
}


def test_a_count_above_its_pin_names_the_cases() -> None:
    """One more false identify than the pin fails, with the cases named."""
    report = _report(
        cases=[
            {
                "case_id": "h2__alpha",
                "expected": "different",
                "merged": False,
                "flagged": True,
            },
            {
                "case_id": "h2__beta",
                "expected": "different",
                "merged": False,
                "flagged": True,
            },
        ]
    )
    violations, _ = threshold_check(report, _PINS)
    assert violations == ["false_identified: 2 (pin 1); cases: h2__alpha, h2__beta"]


def test_a_count_below_its_pin_passes_and_can_be_tightened() -> None:
    """A better count is not a violation; it is listed for tightening."""
    report = _report(
        cases=[
            {
                "case_id": "c1__miss",
                "expected": "same",
                "merged": False,
                "flagged": False,
            }
        ]
    )
    violations, tightenable = threshold_check(report, _PINS)
    assert violations == []
    assert "false_identified: 0 (pin 1)" in tightenable
    assert "merged_different: 0 (pin 0)" not in tightenable


def test_merged_different_above_zero_is_a_safety_failure() -> None:
    """A merged different pair fails the zero pin and names the case."""
    report = _report(
        cases=[
            {
                "case_id": "h3__shared",
                "expected": "different",
                "merged": True,
                "flagged": False,
            }
        ]
    )
    violations, _ = threshold_check(report, _PINS)
    assert violations == ["merged_different: 1 (pin 0); cases: h3__shared"]


def test_merged_reversed_on_a_different_pair_is_a_merged_different_violation() -> None:
    """A different pair that merges only in reverse order fails the zero pin."""
    report = _report(
        cases=[
            {
                "case_id": "h3__reversed",
                "expected": "different",
                "merged": False,
                "merged_reversed": True,
                "flagged": False,
            }
        ]
    )
    violations, _ = threshold_check(report, _PINS)
    assert violations == ["merged_different: 1 (pin 0); cases: h3__reversed"]


def test_a_changed_dataset_fails_before_any_count() -> None:
    """A different dataset SHA-256 is the only violation reported."""
    report = _report(
        sha="def",
        cases=[
            {
                "case_id": "h3__shared",
                "expected": "different",
                "merged": True,
                "flagged": False,
            }
        ],
    )
    violations, tightenable = threshold_check(report, _PINS)
    assert len(violations) == 1 and violations[0].startswith("dataset changed")
    assert tightenable == []
