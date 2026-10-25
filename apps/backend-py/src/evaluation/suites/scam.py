"""
Scam suite: the pipeline scam decision on labeled postings.

A dataset folder has ``cases.jsonl`` (one posting per line with its expected
label and indicator groups). The runner scores the pipeline decision:
``ScamFilter.is_potential_scam`` or
``JobScamDetector(threshold=DEFAULT_SCAM_THRESHOLD)``.
"""

from __future__ import annotations

from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
)

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...models.job_listing import JobListing
from ...scoring.scam_detector import (
    DEFAULT_SCAM_THRESHOLD,
    JobScamDetector,
    ScamFilter,
)
from ..datasets import load_jsonl
from ..metrics import (
    clean_case_false_positive_rate,
    multilabel_scores,
    wilson_interval,
)
from ..report import EvalReport
from ..run_metadata import BACKEND_DIR, build_run_metadata

SUITE = "scam"
DEFAULT_DATASET_DIR = BACKEND_DIR / "tests" / "fixtures" / "eval" / "scam"

INDICATOR_GROUPS: FrozenSet[str] = frozenset(
    {
        "payment",
        "contact",
        "urgency",
        "compensation",
        "listing_quality",
    }
)

CASE_GROUPS: FrozenSet[str] = frozenset(
    {
        "legit_fixture",
        "legit_written",
        "hard_negative",
        "scam_payment",
        "scam_contact",
        "scam_urgency",
        "scam_compensation",
        "scam_listing",
    }
)

SCAM_CASE_GROUPS: FrozenSet[str] = frozenset(
    group for group in CASE_GROUPS if group.startswith("scam_")
)
LEGIT_CASE_GROUPS: FrozenSet[str] = CASE_GROUPS - SCAM_CASE_GROUPS

ExpectedLabel = Literal["scam", "legit"]

# Decision 5 (2026-10-25): S1 and S2. Do not change these numbers after a
# tuning run (rule S4).
MAX_FALSE_POSITIVE_RATE = 0.005
MIN_DROP_PRECISION = 0.50
MIN_FLAGGED_FRAUDS = 10


def _wilson_bounds(
    successes: int, trials: int
) -> Tuple[Optional[float], Optional[float]]:
    """
    Split a Wilson interval into low and high bounds.

    Args:
        successes: Count of positive outcomes.
        trials: Number of trials.

    Returns:
        ``(low, high)``, or ``(None, None)`` when the interval is undefined.
    """
    interval = wilson_interval(successes, trials)
    if interval is None:
        return None, None
    return interval[0], interval[1]


def _threshold_value(row: Dict[str, Any]) -> float:
    """
    Read a sweep-row threshold as a float.

    Args:
        row: Pipeline-sweep row.

    Returns:
        The threshold, or 0.0 when it is missing.
    """
    value = row.get("threshold")
    if value is None:
        return 0.0
    return float(value)


def select_operating_point(pipeline_sweep: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Pick ``t*`` and the action from a pipeline sweep (rules S1 and S2).

    Args:
        pipeline_sweep: Rows with threshold, recall, false-positive rate,
            precision, and true_positives.

    Returns:
        ``threshold``, ``action``, and a one-line ``reason``.
    """
    qualifying: List[Dict[str, Any]] = []
    for row in pipeline_sweep:
        rate = row.get("false_positive_rate")
        if rate is not None and rate <= MAX_FALSE_POSITIVE_RATE:
            qualifying.append(row)

    used_fallback = not qualifying
    tied = False
    if used_fallback:
        chosen = next(
            (row for row in pipeline_sweep if row.get("threshold") == 1.0),
            {
                "threshold": 1.0,
                "precision": None,
                "true_positives": 0,
                "recall": None,
            },
        )
    else:
        best_recall = max(
            (
                row["recall"] if row.get("recall") is not None else -1.0
                for row in qualifying
            ),
        )
        top = [
            row
            for row in qualifying
            if (row["recall"] if row.get("recall") is not None else -1.0) == best_recall
        ]
        tied = len(top) > 1
        chosen = max(top, key=_threshold_value)

    threshold = _threshold_value(chosen)
    precision = chosen.get("precision")
    flagged = int(chosen.get("true_positives") or 0)
    may_drop = (
        precision is not None
        and precision >= MIN_DROP_PRECISION
        and flagged >= MIN_FLAGGED_FRAUDS
    )
    action: Literal["drop", "flag"] = "drop" if may_drop else "flag"

    if used_fallback:
        thresh_part = (
            "no threshold has false-positive rate at most 0.005, so t* is 1.00"
        )
    elif tied:
        thresh_part = (
            f"t* is {threshold:.2f} (highest recall among FPR at most 0.005; "
            "tie broke to the higher threshold)"
        )
    else:
        thresh_part = f"t* is {threshold:.2f} (highest recall among FPR at most 0.005)"
    if action == "drop":
        act_part = (
            "action is drop because precision is at least 0.50 and flagged "
            "frauds are at least 10"
        )
    else:
        reasons: List[str] = []
        if precision is None or precision < MIN_DROP_PRECISION:
            reasons.append("precision is below 0.50")
        if flagged < MIN_FLAGGED_FRAUDS:
            reasons.append("flagged frauds are below 10")
        act_part = "action is flag because " + " and ".join(reasons)
    return {
        "threshold": threshold,
        "action": action,
        "reason": f"{thresh_part}; {act_part}.",
    }


class ScamCase(BaseModel):
    """One labeled job posting for the scam evaluation set."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    job: Dict[str, Any]
    expected: ExpectedLabel
    indicator_groups: List[str] = Field(default_factory=list)
    source: str
    note: str = ""

    @field_validator("case_id")
    @classmethod
    def _valid_case_id(cls, value: str) -> str:
        """
        Require ``<group>__<short_name>`` with a known group.

        Args:
            value: Case identifier.

        Returns:
            The same identifier.

        Raises:
            ValueError: When the prefix is missing or unknown.
        """
        if "__" not in value:
            raise ValueError(f"case_id must be <group>__<short_name>: {value}")
        group = value.split("__", 1)[0]
        if group not in CASE_GROUPS:
            raise ValueError(f"unknown case group: {group}")
        return value

    @field_validator("indicator_groups")
    @classmethod
    def _known_indicator_groups(cls, value: List[str]) -> List[str]:
        """
        Reject indicator names that the guide does not define.

        Args:
            value: Indicator group names.

        Returns:
            The same list.

        Raises:
            ValueError: When a name is not an indicator group.
        """
        unknown = sorted(set(value) - INDICATOR_GROUPS)
        if unknown:
            raise ValueError(f"unknown indicator groups: {unknown}")
        return value

    @field_validator("source")
    @classmethod
    def _valid_source(cls, value: str) -> str:
        """
        Accept a fixture pointer or ``written``.

        Args:
            value: Source string.

        Returns:
            The same string.

        Raises:
            ValueError: When the source form is not allowed.
        """
        if value == "written" or value.startswith("fixture:"):
            return value
        raise ValueError(f"source must be written or fixture:<path>: {value}")

    @model_validator(mode="after")
    def _label_matches_group(self) -> "ScamCase":
        """
        Check that the label, the groups, and the case prefix agree.

        Args:
            self: Validated case.

        Returns:
            The same case.

        Raises:
            ValueError: When the prefix, the expected label, or the
                indicator list disagree.
        """
        group = self.case_id.split("__", 1)[0]
        if group in SCAM_CASE_GROUPS and self.expected != "scam":
            raise ValueError(f"{self.case_id}: scam_* cases must have expected=scam")
        if group in LEGIT_CASE_GROUPS and self.expected != "legit":
            raise ValueError(
                f"{self.case_id}: legit_* and hard_negative cases must have "
                "expected=legit"
            )
        if self.expected == "scam" and not self.indicator_groups:
            raise ValueError(f"{self.case_id}: a scam must list indicator groups")
        if self.expected == "legit" and self.indicator_groups:
            raise ValueError(
                f"{self.case_id}: a legitimate posting must have empty "
                "indicator_groups"
            )
        JobListing.model_validate(self.job)
        return self


def decide_pipeline_scam(
    job: JobListing,
    detector: JobScamDetector,
    filter_hit_fn: Callable[[JobListing], bool],
) -> Tuple[bool, bool, Any]:
    """
    Apply the pipeline decision: quick filter or detector.

    Args:
        job: Listing to score.
        detector: ``JobScamDetector`` instance (shared default threshold).
        filter_hit_fn: Quick-filter predicate.

    Returns:
        ``(predicted_scam, filter_hit, detector_report)``.
    """
    filter_hit = filter_hit_fn(job)
    report = detector.detect(job)
    predicted = filter_hit or report.is_scam
    return predicted, filter_hit, report


def _ratio(hits: int, support: int) -> Optional[float]:
    """
    Divide, or return None when the support is 0.

    Args:
        hits: Count above the line.
        support: Count below the line.

    Returns:
        The ratio, or None.
    """
    return hits / support if support else None


def evaluate_scam_listings(
    items: Sequence[Tuple[str, JobListing, ExpectedLabel, Sequence[str]]],
    *,
    detector: Optional[JobScamDetector] = None,
    filter_hit_fn: Optional[Callable[[JobListing], bool]] = None,
) -> Tuple[Dict[str, Optional[float]], Dict[str, Any]]:
    """
    Score the pipeline decision, the detector sweep, and the pipeline sweep.

    Args:
        items: ``(case_id, job, expected, indicator_groups)`` rows.
        detector: Detector instance. Defaults to ``DEFAULT_SCAM_THRESHOLD``.
        filter_hit_fn: Quick-filter predicate. Defaults to ``ScamFilter``.

    Returns:
        Metrics map (including Wilson 95 percent bounds) and details
        (confusion, per-case rows, detector sweep, pipeline sweep).
    """
    detector = detector or JobScamDetector(threshold=DEFAULT_SCAM_THRESHOLD)
    if filter_hit_fn is None:
        filter_hit_fn = ScamFilter.is_potential_scam

    expected_sets: List[Set[str]] = []
    predicted_sets: List[Set[str]] = []
    confidences: List[float] = []
    filter_hits: List[bool] = []
    case_rows: List[Dict[str, Any]] = []
    group_hits: Dict[str, int] = {group: 0 for group in INDICATOR_GROUPS}
    group_support: Dict[str, int] = {group: 0 for group in INDICATOR_GROUPS}

    for case_id, job, expected, groups in items:
        predicted, filter_hit, report = decide_pipeline_scam(
            job, detector, filter_hit_fn
        )
        want: Set[str] = {"scam"} if expected == "scam" else set()
        got: Set[str] = {"scam"} if predicted else set()
        expected_sets.append(want)
        predicted_sets.append(got)
        confidences.append(report.confidence)
        filter_hits.append(filter_hit)
        case_rows.append(
            {
                "case_id": case_id,
                "expected": expected,
                "predicted": "scam" if predicted else "legit",
                "quick_filter": filter_hit,
                "detector_confidence": report.confidence,
                "detector_reasons": list(report.reasons),
            }
        )
        for group in groups:
            if group in group_support:
                group_support[group] += 1
                if predicted:
                    group_hits[group] += 1

    scores = multilabel_scores(expected_sets, predicted_sets, ["scam"])["scam"]
    true_negatives = sum(
        1 for want, got in zip(expected_sets, predicted_sets) if not want and not got
    )
    precision_low, precision_high = _wilson_bounds(
        scores.true_positives, scores.true_positives + scores.false_positives
    )
    recall_low, recall_high = _wilson_bounds(
        scores.true_positives, scores.true_positives + scores.false_negatives
    )
    fpr_low, fpr_high = _wilson_bounds(
        scores.false_positives, scores.false_positives + true_negatives
    )
    metrics: Dict[str, Optional[float]] = {
        "case_count": float(len(items)),
        "precision": scores.precision,
        "precision.ci95_low": precision_low,
        "precision.ci95_high": precision_high,
        "recall": scores.recall,
        "recall.ci95_low": recall_low,
        "recall.ci95_high": recall_high,
        "f1": scores.f1,
        "false_positive_rate": clean_case_false_positive_rate(
            expected_sets, predicted_sets
        ),
        "false_positive_rate.ci95_low": fpr_low,
        "false_positive_rate.ci95_high": fpr_high,
    }
    for group in sorted(INDICATOR_GROUPS):
        metrics[f"recall.{group}"] = _ratio(group_hits[group], group_support[group])

    sweep: List[Dict[str, Any]] = []
    for step in range(21):
        threshold = round(step / 20, 2)
        sweep_pred = [
            {"scam"} if confidence >= threshold else set() for confidence in confidences
        ]
        sweep_scores = multilabel_scores(expected_sets, sweep_pred, ["scam"])["scam"]
        sweep.append(
            {
                "threshold": threshold,
                "precision": sweep_scores.precision,
                "recall": sweep_scores.recall,
                "f1": sweep_scores.f1,
                "false_positive_rate": clean_case_false_positive_rate(
                    expected_sets, sweep_pred
                ),
            }
        )

    pipeline_sweep: List[Dict[str, Any]] = []
    for step in range(1, 21):
        threshold = round(step / 20, 2)
        pipeline_pred = [
            {"scam"} if (hit or confidence >= threshold) else set()
            for hit, confidence in zip(filter_hits, confidences)
        ]
        pipeline_scores = multilabel_scores(expected_sets, pipeline_pred, ["scam"])[
            "scam"
        ]
        pipeline_true_negatives = sum(
            1 for want, got in zip(expected_sets, pipeline_pred) if not want and not got
        )
        pipeline_sweep.append(
            {
                "threshold": threshold,
                "true_positives": pipeline_scores.true_positives,
                "false_positives": pipeline_scores.false_positives,
                "false_negatives": pipeline_scores.false_negatives,
                "true_negatives": pipeline_true_negatives,
                "precision": pipeline_scores.precision,
                "recall": pipeline_scores.recall,
                "false_positive_rate": clean_case_false_positive_rate(
                    expected_sets, pipeline_pred
                ),
            }
        )

    details: Dict[str, Any] = {
        "confusion": {
            "true_positives": scores.true_positives,
            "false_positives": scores.false_positives,
            "false_negatives": scores.false_negatives,
            "true_negatives": true_negatives,
        },
        "cases": case_rows,
        "threshold_sweep": sweep,
        "pipeline_sweep": pipeline_sweep,
    }
    return metrics, details


def run_scam_suite(dataset_dir: Path = DEFAULT_DATASET_DIR) -> EvalReport:
    """
    Score the pipeline decision on a labeled scam set.

    Args:
        dataset_dir: Folder with ``cases.jsonl``.

    Returns:
        Report with scam precision, recall, F1, the false-positive rate,
        per-group recall, confusion counts, per-case rows, and a detector
        threshold sweep.

    Raises:
        FileNotFoundError: When ``cases.jsonl`` is missing.
        ValueError: When a case is invalid.
    """
    cases_path = Path(dataset_dir) / "cases.jsonl"
    if not cases_path.exists():
        raise FileNotFoundError(
            f"{cases_path} not found. The labeled scam set is added in Step 3.3; "
            "pass --dataset to use another folder."
        )

    cases = load_jsonl(cases_path, ScamCase)
    items = [
        (
            case.case_id,
            JobListing.model_validate(case.job),
            case.expected,
            case.indicator_groups,
        )
        for case in cases
    ]
    metrics, details = evaluate_scam_listings(items)
    metadata = build_run_metadata(SUITE, [cases_path], len(cases))
    return EvalReport(
        suite=SUITE,
        metadata=metadata,
        metrics=metrics,
        details=details,
    )
