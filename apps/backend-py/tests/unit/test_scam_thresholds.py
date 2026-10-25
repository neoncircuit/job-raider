"""
CI gate for the scam suite on the committed set (Step 3.3, B3).

The suite is deterministic, so the gate pins counts at the default
threshold, not ratios. It also pins the detector score of each hard
negative with no margin, and the dataset SHA-256, so a changed set or a
changed default fails before the pins are compared.
"""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import RunMetadata
from src.evaluation.suites.scam import DEFAULT_DATASET_DIR, run_scam_suite
from src.scoring import scam_detector as scam_mod

THRESHOLDS_PATH = DEFAULT_DATASET_DIR / "thresholds.json"


def _case_ids(report: EvalReport, expected: str, predicted: str) -> List[str]:
    """
    Return case IDs whose expected and predicted labels match.

    Args:
        report: Scam report.
        expected: Expected label.
        predicted: Predicted label.

    Returns:
        Case IDs in report order.
    """
    return [
        row["case_id"]
        for row in report.details.get("cases", [])
        if row.get("expected") == expected and row.get("predicted") == predicted
    ]


def _compare_count(
    kind: str, count: int, pin: int, cases: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Compare one confusion count with its pin.

    Args:
        kind: ``false_positives`` or ``false_negatives``.
        count: Count in the report.
        pin: Maximum allowed count.
        cases: Cases behind the count, for the failure message.

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
    Compare a scam report with the pinned counts and hard-negative scores.

    The dataset SHA-256 is checked first. When it differs, no other check
    runs. The process defaults are checked next. When a default differs,
    no count or score is compared.

    Args:
        report: Report from ``run_scam_suite``.
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

    if (
        scam_mod.DEFAULT_SCAM_THRESHOLD != thresholds["threshold"]
        or scam_mod.DEFAULT_SCAM_ACTION != thresholds["action"]
    ):
        return ["defaults changed; run a new baseline and pin new counts"], []

    violations: List[str] = []
    tightenable: List[str] = []
    confusion = report.details.get("confusion", {})
    pins = thresholds["counts"]
    for kind, expected, predicted in (
        ("false_positives", "legit", "scam"),
        ("false_negatives", "scam", "legit"),
    ):
        violation, tighter = _compare_count(
            kind,
            int(confusion.get(kind, 0)),
            pins[f"max_{kind}"],
            _case_ids(report, expected, predicted),
        )
        violations.extend([violation] if violation else [])
        tightenable.extend([tighter] if tighter else [])

    score_pins: Dict[str, float] = thresholds["hard_negative_scores"]
    rows = {
        row["case_id"]: row
        for row in report.details.get("cases", [])
        if str(row.get("case_id", "")).startswith("hard_negative__")
    }
    for case_id in sorted(set(rows) | set(score_pins)):
        if case_id not in score_pins:
            violations.append(f"{case_id}: reported but has no pin")
            continue
        if case_id not in rows:
            violations.append(f"{case_id}: pinned but not reported")
            continue
        row = rows[case_id]
        if row.get("predicted") != "legit":
            violations.append(f"{case_id}: predicted scam (must be legit)")
        if row.get("quick_filter"):
            violations.append(f"{case_id}: quick filter hit")
        score = round(float(row.get("detector_confidence", 0.0)), 4)
        pin = round(float(score_pins[case_id]), 4)
        if score > pin:
            reasons = ", ".join(row.get("detector_reasons") or [])
            violations.append(
                f"{case_id}: score {score:.4f} (pin {pin:.4f}); reasons: {reasons}"
            )
        elif score < pin:
            tightenable.append(f"{case_id}: score {score:.4f} (pin {pin:.4f})")
    return violations, tightenable


def test_scam_suite_meets_the_pinned_counts() -> None:
    """The committed set stays at or below every pin (the CI gate)."""
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    violations, tightenable = threshold_check(run_scam_suite(), thresholds)
    if tightenable:
        warnings.warn(
            "scam counts or scores below their pins, tighten thresholds.json: "
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
    *,
    sha: str = "abc",
    false_positives: Optional[List[str]] = None,
    false_negatives: Optional[List[str]] = None,
    hard_negatives: Optional[List[Dict[str, Any]]] = None,
) -> EvalReport:
    """
    Build a small synthetic scam report.

    Args:
        sha: Dataset SHA-256 to report.
        false_positives: Case IDs predicted scam that are legitimate.
        false_negatives: Case IDs predicted legit that are scams.
        hard_negatives: Hard-negative rows (case_id, score, reasons, flags).

    Returns:
        A report shaped like ``run_scam_suite`` output.
    """
    fp_ids = false_positives or []
    fn_ids = false_negatives or []
    hn_rows = hard_negatives or []
    cases: List[Dict[str, Any]] = []
    for case_id in fp_ids:
        cases.append(
            {
                "case_id": case_id,
                "expected": "legit",
                "predicted": "scam",
                "quick_filter": False,
                "detector_confidence": 1.0,
                "detector_reasons": ["synthetic"],
            }
        )
    for case_id in fn_ids:
        cases.append(
            {
                "case_id": case_id,
                "expected": "scam",
                "predicted": "legit",
                "quick_filter": False,
                "detector_confidence": 0.0,
                "detector_reasons": [],
            }
        )
    for row in hn_rows:
        cases.append(
            {
                "case_id": row["case_id"],
                "expected": "legit",
                "predicted": row.get("predicted", "legit"),
                "quick_filter": row.get("quick_filter", False),
                "detector_confidence": row.get("score", 0.1),
                "detector_reasons": row.get("reasons", []),
            }
        )
    return EvalReport(
        suite="scam",
        metadata=RunMetadata(
            suite="scam",
            git_sha="0000000",
            git_dirty=False,
            dataset_sha256=sha,
            case_count=len(cases) or 1,
            started_at=datetime(2026, 10, 25, tzinfo=timezone.utc),
        ),
        metrics={},
        details={
            "confusion": {
                "true_positives": 0,
                "false_positives": len(fp_ids),
                "false_negatives": len(fn_ids),
                "true_negatives": 0,
            },
            "cases": cases,
        },
    )


_PINS: Dict[str, Any] = {
    "dataset_sha256": "abc",
    "threshold": 1.0,
    "action": "flag",
    "counts": {"max_false_positives": 1, "max_false_negatives": 22},
    "hard_negative_scores": {"hard_negative__signal_processing": 0.1},
}


def test_a_count_above_its_pin_names_the_cases() -> None:
    """One more false positive than the pin fails, with the case in the message."""
    report = _report(
        false_positives=["legit_written__alpha", "legit_written__beta"],
        hard_negatives=[
            {
                "case_id": "hard_negative__signal_processing",
                "score": 0.1,
                "reasons": [],
            }
        ],
    )
    violations, _ = threshold_check(report, _PINS)
    assert violations == [
        "false_positives: 2 (pin 1); cases: legit_written__alpha, "
        "legit_written__beta"
    ]


def test_a_count_below_its_pin_passes_and_can_be_tightened() -> None:
    """A better count is not a violation; it is listed for tightening."""
    report = _report(
        false_positives=[],
        false_negatives=["scam_payment__one"],
        hard_negatives=[
            {
                "case_id": "hard_negative__signal_processing",
                "score": 0.1,
                "reasons": [],
            }
        ],
    )
    violations, tightenable = threshold_check(report, _PINS)
    assert violations == []
    assert "false_positives: 0 (pin 1)" in tightenable
    assert "false_negatives: 1 (pin 22)" in tightenable


def test_a_hard_negative_score_above_its_pin_names_the_case_and_reasons() -> None:
    """A score above the pin fails, with the case and the detector reasons."""
    report = _report(
        hard_negatives=[
            {
                "case_id": "hard_negative__signal_processing",
                "score": 0.5,
                "reasons": [
                    "Requires messaging app: signal",
                    "No company email provided",
                ],
            }
        ]
    )
    violations, _ = threshold_check(report, _PINS)
    assert violations == [
        "hard_negative__signal_processing: score 0.5000 (pin 0.1000); "
        "reasons: Requires messaging app: signal, No company email provided"
    ]


def test_a_missing_hard_negative_pin_fails() -> None:
    """A reported hard negative without a pin is a violation."""
    report = _report(
        hard_negatives=[
            {
                "case_id": "hard_negative__signal_processing",
                "score": 0.1,
                "reasons": [],
            },
            {
                "case_id": "hard_negative__bitcoin_exchange",
                "score": 0.1,
                "reasons": [],
            },
        ]
    )
    violations, _ = threshold_check(report, _PINS)
    assert violations == ["hard_negative__bitcoin_exchange: reported but has no pin"]


def test_a_changed_dataset_fails_before_any_count() -> None:
    """A different dataset SHA-256 is the only violation reported."""
    report = _report(
        sha="def",
        false_positives=["hard_negative__bitcoin_exchange"],
        hard_negatives=[
            {
                "case_id": "hard_negative__signal_processing",
                "score": 0.9,
                "reasons": ["synthetic"],
            }
        ],
    )
    violations, tightenable = threshold_check(report, _PINS)
    assert len(violations) == 1 and violations[0].startswith("dataset changed")
    assert tightenable == []


def test_a_changed_default_fails() -> None:
    """A changed process default is a violation; counts are not compared."""
    original = scam_mod.DEFAULT_SCAM_THRESHOLD
    scam_mod.DEFAULT_SCAM_THRESHOLD = 0.95
    try:
        report = _report(
            hard_negatives=[
                {
                    "case_id": "hard_negative__signal_processing",
                    "score": 0.1,
                    "reasons": [],
                }
            ]
        )
        violations, tightenable = threshold_check(report, _PINS)
    finally:
        scam_mod.DEFAULT_SCAM_THRESHOLD = original
    assert violations == ["defaults changed; run a new baseline and pin new counts"]
    assert tightenable == []
