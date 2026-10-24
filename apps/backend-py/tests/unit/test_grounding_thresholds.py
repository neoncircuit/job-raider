"""
CI gate for the grounding suite on the main set (Step 3.2, CI gate decisions).

The suite is deterministic, so the gate pins counts, not ratios: for each
label, the false positives and the false negatives must stay at or below the
pins in ``thresholds.json``. The file also pins the dataset SHA-256, so a
changed main set fails before any count is compared. The holdout set and the
real letters are not part of this gate.
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import RunMetadata
from src.evaluation.suites.grounding import DEFAULT_DATASET_DIR, run_grounding_suite

THRESHOLDS_PATH = DEFAULT_DATASET_DIR / "thresholds.json"

# Report row keys that list the cases behind each count.
_CASE_KEYS = {"false_positives": "extra", "false_negatives": "missed"}
_SENTENCE_KEYS = {
    "false_positives": "sentence_extra",
    "false_negatives": "sentence_missed",
}


def _label_cases(report: EvalReport, row_key: str, label: str) -> List[str]:
    """
    Return the case IDs whose report row lists ``label`` under ``row_key``.

    Args:
        report: Grounding report.
        row_key: ``extra`` or ``missed``.
        label: Grounding label.

    Returns:
        Case IDs in report order.
    """
    return [
        row["case_id"]
        for row in report.details.get("cases", [])
        if label in row.get(row_key, [])
    ]


def _sentence_cases(report: EvalReport, row_key: str) -> List[str]:
    """
    Return ``case_id (count)`` for each case with sentences under ``row_key``.

    Args:
        report: Grounding report.
        row_key: ``sentence_extra`` or ``sentence_missed``.

    Returns:
        Case IDs with their sentence counts, in report order.
    """
    return [
        f"{row['case_id']} ({len(row[row_key])})"
        for row in report.details.get("cases", [])
        if row.get(row_key)
    ]


def _compare(
    name: str, kind: str, count: int, pin: Optional[int], cases: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Compare one count with its pin.

    Args:
        name: Label name, or ``sentence``.
        kind: ``false_positives`` or ``false_negatives``.
        count: Count in the report.
        pin: Maximum allowed count, or ``None`` when the count is not gated.
        cases: Cases behind the count, for the failure message.

    Returns:
        ``(violation, tightenable)``; each is a message or ``None``.
    """
    if pin is None:
        return None, None
    if count > pin:
        return f"{name}: {count} {kind} (pin {pin}); cases: {', '.join(cases)}", None
    if count < pin:
        return None, f"{name}: {count} {kind} (pin {pin})"
    return None, None


def threshold_check(
    report: EvalReport, thresholds: Dict[str, Any]
) -> Tuple[List[str], List[str]]:
    """
    Compare a grounding report with the pinned counts.

    The dataset SHA-256 is checked first. When it differs, no count is
    compared. Every reported label needs a pin, and every pin needs a
    reported label.

    Args:
        report: Report from ``run_grounding_suite``.
        thresholds: Parsed ``thresholds.json``.

    Returns:
        ``(violations, tightenable)``: counts above their pins, and counts
        below their pins.
    """
    pinned_sha = thresholds["dataset_sha256"]
    if report.metadata.dataset_sha256 != pinned_sha:
        return [
            f"dataset changed: {report.metadata.dataset_sha256} is not the pinned "
            f"{pinned_sha}; run a new baseline and pin new counts"
        ], []

    violations: List[str] = []
    tightenable: List[str] = []
    per_label = report.details.get("per_label", {})
    pins = thresholds["labels"]
    for label in sorted(set(per_label) | set(pins)):
        if label not in pins:
            violations.append(f"{label}: reported but has no pin")
            continue
        if label not in per_label:
            violations.append(f"{label}: pinned but not reported")
            continue
        for kind, row_key in _CASE_KEYS.items():
            violation, tighter = _compare(
                label,
                kind,
                per_label[label][kind],
                pins[label][f"max_{kind}"],
                _label_cases(report, row_key, label),
            )
            violations.extend([violation] if violation else [])
            tightenable.extend([tighter] if tighter else [])

    for kind, row_key in _SENTENCE_KEYS.items():
        value = report.metrics.get(f"sentence.{kind}")
        if value is None:
            violations.append(f"sentence: {kind} not reported")
            continue
        violation, tighter = _compare(
            "sentence",
            kind,
            int(value),
            thresholds["sentence"][f"max_{kind}"],
            _sentence_cases(report, row_key),
        )
        violations.extend([violation] if violation else [])
        tightenable.extend([tighter] if tighter else [])
    return violations, tightenable


def test_grounding_suite_meets_the_pinned_counts() -> None:
    """The main set stays at or below every pinned count (the CI gate)."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    violations, tightenable = threshold_check(run_grounding_suite(), thresholds)
    if tightenable:
        warnings.warn(
            "grounding counts below their pins, tighten thresholds.json: "
            + "; ".join(tightenable),
            stacklevel=1,
        )
    assert not violations, "\n".join(violations)


def test_thresholds_file_records_each_change() -> None:
    """Every pin change has a dated entry with a reason and an MLflow run."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    assert thresholds["changes"]
    for entry in thresholds["changes"]:
        assert entry["date"] and entry["reason"] and entry["mlflow_run"], entry


def _report(
    false_positives: int, sentence_false_positives: int, sha: str = "abc"
) -> EvalReport:
    """
    Build a small synthetic report with one label and one case.

    Args:
        false_positives: ``scope_inflation`` false positives.
        sentence_false_positives: Sentence-level false positives.
        sha: Dataset SHA-256 to report.

    Returns:
        A report shaped like ``run_grounding_suite`` output.
    """
    return EvalReport(
        suite="grounding",
        metadata=RunMetadata(
            suite="grounding",
            git_sha="0000000",
            git_dirty=False,
            dataset_sha256=sha,
            case_count=1,
            started_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
        ),
        metrics={
            "sentence.false_positives": float(sentence_false_positives),
            "sentence.false_negatives": 0.0,
        },
        details={
            "per_label": {
                "scope_inflation": {
                    "true_positives": 1,
                    "false_positives": false_positives,
                    "false_negatives": 0,
                    "support": 1,
                }
            },
            "cases": [
                {
                    "case_id": "synthetic__quill_ledger",
                    "missed": [],
                    "extra": ["scope_inflation"] if false_positives else [],
                    "sentence_missed": [],
                    "sentence_extra": ["S"] * sentence_false_positives,
                }
            ],
        },
    )


_PINS: Dict[str, Any] = {
    "dataset_sha256": "abc",
    "labels": {"scope_inflation": {"max_false_positives": 1, "max_false_negatives": 0}},
    "sentence": {"max_false_positives": 2, "max_false_negatives": 0},
}


def test_a_count_above_its_pin_names_the_label_and_the_cases() -> None:
    """One more false positive than the pin fails, with the case in the message."""
    violations, _ = threshold_check(_report(2, 2), _PINS)
    assert violations == [
        "scope_inflation: 2 false_positives (pin 1); cases: synthetic__quill_ledger"
    ]
    sentence_violations, _ = threshold_check(_report(1, 3), _PINS)
    assert sentence_violations == [
        "sentence: 3 false_positives (pin 2); cases: synthetic__quill_ledger (3)"
    ]


def test_a_count_below_its_pin_passes_and_can_be_tightened() -> None:
    """A better count is not a violation; it is listed for tightening."""
    violations, tightenable = threshold_check(_report(0, 1), _PINS)
    assert violations == []
    assert tightenable == [
        "scope_inflation: 0 false_positives (pin 1)",
        "sentence: 1 false_positives (pin 2)",
    ]


def test_a_null_pin_is_not_gated_and_a_missing_pin_fails() -> None:
    """``null`` turns a count off; a reported label without a pin fails."""
    pins = json.loads(json.dumps(_PINS))
    pins["labels"]["scope_inflation"]["max_false_positives"] = None
    violations, tightenable = threshold_check(_report(5, 0), pins)
    assert violations == []
    assert not any(item.startswith("scope_inflation") for item in tightenable)
    pins["labels"] = {}
    violations, _ = threshold_check(_report(0, 0), pins)
    assert violations == ["scope_inflation: reported but has no pin"]


def test_a_changed_dataset_fails_before_any_count() -> None:
    """A different dataset SHA-256 is the only violation reported."""
    violations, tightenable = threshold_check(_report(9, 9, sha="def"), _PINS)
    assert len(violations) == 1 and violations[0].startswith("dataset changed")
    assert tightenable == []
