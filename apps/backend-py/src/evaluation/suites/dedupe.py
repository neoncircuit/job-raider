"""
Dedupe suite: the listing-pair merge decision on labeled pairs.

A dataset folder has ``cases.jsonl`` (one pair per line with its expected
label and class). The runner scores ``JobListingCollection.deduplicate``
on ``[a, b]``, and also runs ``[b, a]`` to count order-dependent pairs.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    FrozenSet,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
)

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...models.job_listing import JobListing, JobListingCollection
from ..datasets import load_jsonl
from ..metrics import wilson_interval
from ..report import EvalReport
from ..run_metadata import BACKEND_DIR, build_run_metadata

SUITE = "dedupe"
DEFAULT_DATASET_DIR = BACKEND_DIR / "tests" / "fixtures" / "eval" / "dedupe"

SAME_CLASSES: FrozenSet[str] = frozenset({"C0", "C1", "C2", "C3", "C4"})
DIFFERENT_CLASSES: FrozenSet[str] = frozenset({"H1", "H2", "H3", "H4", "H5"})
CASE_CLASSES: FrozenSet[str] = SAME_CLASSES | DIFFERENT_CLASSES | frozenset({"catalog"})

ExpectedLabel = Literal["same", "different", "TODO"]
DedupeFn = Callable[[JobListing, JobListing], int]


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    """
    Divide, or return None when the denominator is 0.

    Args:
        numerator: Count above the line.
        denominator: Count below the line.

    Returns:
        The ratio, or None.
    """
    return numerator / denominator if denominator else None


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    """
    Harmonic mean of precision and recall.

    Args:
        precision: Precision, or None.
        recall: Recall, or None.

    Returns:
        F1, 0.0 when both are 0, or None when either is undefined.
    """
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


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


def _flag_between(
    listings: Sequence[JobListing], left_id: str, right_id: str
) -> Tuple[bool, Optional[str]]:
    """
    Return whether two kept listings flag each other, and the reason.

    Args:
        listings: Result of ``deduplicate``.
        left_id: First job id.
        right_id: Second job id.

    Returns:
        ``(flagged, reason)``. Reason is None when the pair is not flagged.
    """
    by_id = {item.job_id: item for item in listings}
    if left_id not in by_id or right_id not in by_id:
        return False, None
    rows = by_id[left_id].metadata.get("possible_duplicates") or []
    for row in rows:
        if row.get("job_id") == right_id:
            return True, str(row.get("reason") or "") or None
    return False, None


def _pair_outcome(
    first: JobListing,
    second: JobListing,
    dedupe_fn: Optional[DedupeFn],
) -> Tuple[bool, bool, Optional[str]]:
    """
    Decide merge and flag for one order of a pair.

    Args:
        first: First listing.
        second: Second listing.
        dedupe_fn: Optional fake that returns the remaining count.

    Returns:
        ``(merged, flagged, reason)``.
    """
    if dedupe_fn is not None:
        return dedupe_fn(first, second) == 1, False, None
    collection = JobListingCollection(listings=[first, second]).deduplicate()
    merged = len(collection.listings) == 1
    flagged, reason = _flag_between(collection.listings, first.job_id, second.job_id)
    return merged, flagged, reason


def default_dedupe(first: JobListing, second: JobListing) -> int:
    """
    Return the listing count after ``deduplicate`` on ``[first, second]``.

    Args:
        first: First listing in the collection.
        second: Second listing in the collection.

    Returns:
        Length of the deduplicated collection.
    """
    merged = JobListingCollection(listings=[first, second]).deduplicate()
    return len(merged.listings)


class DedupeCase(BaseModel):
    """One labeled listing pair for the dedupe evaluation set."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    case_id: str
    pair_class: str = Field(alias="class")
    expected: ExpectedLabel
    a: Dict[str, Any]
    b: Dict[str, Any]
    source: str
    note: str = ""

    @field_validator("case_id")
    @classmethod
    def _valid_case_id(cls, value: str) -> str:
        """
        Require ``<class in lower case>__<short_name>``.

        Args:
            value: Case identifier.

        Returns:
            The same identifier.

        Raises:
            ValueError: When the prefix is missing.
        """
        if "__" not in value:
            raise ValueError(f"case_id must be <class>__<short_name>: {value}")
        return value

    @field_validator("pair_class")
    @classmethod
    def _known_class(cls, value: str) -> str:
        """
        Reject a class that the guide does not define.

        Args:
            value: Class name.

        Returns:
            The same class name.

        Raises:
            ValueError: When the class is unknown.
        """
        if value not in CASE_CLASSES:
            raise ValueError(f"unknown class: {value}")
        return value

    @field_validator("source")
    @classmethod
    def _valid_source(cls, value: str) -> str:
        """
        Accept a constructed pair, a catalog pair, or a fixture pointer.

        Args:
            value: Source string.

        Returns:
            The same string.

        Raises:
            ValueError: When the source form is not allowed.
        """
        if value in {"constructed", "catalog"} or value.startswith("fixture:"):
            return value
        raise ValueError(
            f"source must be constructed, catalog, or fixture:<path>: {value}"
        )

    @model_validator(mode="after")
    def _label_matches_class(self) -> "DedupeCase":
        """
        Check that the prefix, the class, and the expected label agree.

        Args:
            self: Validated case.

        Returns:
            The same case.

        Raises:
            ValueError: When the prefix, the class, or the listings disagree.
        """
        prefix = self.case_id.split("__", 1)[0]
        if prefix != self.pair_class.lower():
            raise ValueError(f"{self.case_id}: prefix must match class")
        if self.expected == "TODO" and self.pair_class != "catalog":
            raise ValueError(f"{self.case_id}: TODO is only valid for catalog pairs")
        if self.pair_class in SAME_CLASSES and self.expected != "same":
            raise ValueError(f"{self.case_id}: C classes must have expected=same")
        if self.pair_class in DIFFERENT_CLASSES and self.expected != "different":
            raise ValueError(f"{self.case_id}: H classes must have expected=different")
        JobListing.model_validate(self.a)
        JobListing.model_validate(self.b)
        return self


def evaluate_dedupe_pairs(
    cases: Sequence[DedupeCase],
    *,
    dedupe_fn: Optional[DedupeFn] = None,
) -> Tuple[Dict[str, Optional[float]], Dict[str, Any]]:
    """
    Score the identify decision (merged or flagged) on labeled pairs.

    Args:
        cases: Validated pairs. A ``TODO`` label is refused.
        dedupe_fn: Optional fake that returns the listing count after a
            merge attempt. Tests pass a fake. The default reads merge and
            flag from ``deduplicate``.

    Returns:
        Metrics map (Wilson 95 percent bounds on identify rates) and
        details (confusion, merged counts, per-class counts, per-pair
        rows).

    Raises:
        ValueError: When a case still has ``expected=TODO``.
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    true_negatives = 0
    merged_same = 0
    merged_different = 0
    order_dependent = 0
    class_counts: DefaultDict[str, Dict[str, int]] = defaultdict(
        lambda: {"merged": 0, "flagged": 0, "total": 0}
    )
    case_rows: List[Dict[str, Any]] = []

    for case in cases:
        if case.expected == "TODO":
            raise ValueError("label the pairs first")
        listing_a = JobListing.model_validate(case.a)
        listing_b = JobListing.model_validate(case.b)
        merged, flagged, reason = _pair_outcome(listing_a, listing_b, dedupe_fn)
        merged_reversed, flagged_reversed, _ = _pair_outcome(
            listing_b, listing_a, dedupe_fn
        )
        identified = merged or flagged
        identified_reversed = merged_reversed or flagged_reversed
        if identified != identified_reversed:
            order_dependent += 1
        if case.expected == "same" and identified:
            true_positives += 1
        elif case.expected == "same":
            false_negatives += 1
        elif identified:
            false_positives += 1
        else:
            true_negatives += 1
        either_merged = merged or merged_reversed
        if either_merged and case.expected == "same":
            merged_same += 1
        if either_merged and case.expected == "different":
            merged_different += 1
        class_counts[case.pair_class]["total"] += 1
        if either_merged:
            class_counts[case.pair_class]["merged"] += 1
        if flagged:
            class_counts[case.pair_class]["flagged"] += 1
        case_rows.append(
            {
                "case_id": case.case_id,
                "class": case.pair_class,
                "expected": case.expected,
                "merged": merged,
                "merged_reversed": merged_reversed,
                "flagged": flagged,
                "reason": reason,
            }
        )

    precision_trials = true_positives + false_positives
    recall_trials = true_positives + false_negatives
    false_identify_trials = false_positives + true_negatives
    precision = _ratio(true_positives, precision_trials)
    recall = _ratio(true_positives, recall_trials)
    false_identify_rate = _ratio(false_positives, false_identify_trials)
    precision_low, precision_high = _wilson_bounds(true_positives, precision_trials)
    recall_low, recall_high = _wilson_bounds(true_positives, recall_trials)
    f1 = _f1(precision, recall)
    false_identify_low, false_identify_high = _wilson_bounds(
        false_positives, false_identify_trials
    )
    metrics: Dict[str, Optional[float]] = {
        "case_count": float(len(cases)),
        "precision": precision,
        "precision.ci95_low": precision_low,
        "precision.ci95_high": precision_high,
        "recall": recall,
        "recall.ci95_low": recall_low,
        "recall.ci95_high": recall_high,
        "f1": f1,
        "false_identify_rate": false_identify_rate,
        "false_identify_rate.ci95_low": false_identify_low,
        "false_identify_rate.ci95_high": false_identify_high,
        "merged_same": float(merged_same),
        "merged_different": float(merged_different),
        "order_dependent": float(order_dependent),
    }
    details: Dict[str, Any] = {
        "confusion": {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "true_negatives": true_negatives,
        },
        "merged_same": merged_same,
        "merged_different": merged_different,
        "per_class": {
            name: dict(counts) for name, counts in sorted(class_counts.items())
        },
        "order_dependent": order_dependent,
        "cases": case_rows,
    }
    return metrics, details


def run_dedupe_suite(
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    *,
    dedupe_fn: Optional[DedupeFn] = None,
) -> EvalReport:
    """
    Score the merge decision on a labeled pair set.

    Args:
        dataset_dir: Folder with ``cases.jsonl``.
        dedupe_fn: Optional replacement for ``default_dedupe``. Tests pass a
            fake. The dataset SHA-256 covers ``cases.jsonl`` only.

    Returns:
        Report with identify precision, recall, F1, the false-identify
        rate, merged counts, per-class counts, and per-pair rows.

    Raises:
        FileNotFoundError: When ``cases.jsonl`` is missing.
        ValueError: When a case is invalid or still unlabeled.
    """
    cases_path = Path(dataset_dir) / "cases.jsonl"
    if not cases_path.exists():
        raise FileNotFoundError(
            f"{cases_path} not found. The labeled dedupe set is added in "
            "Step 3.5; pass --dataset to use another folder."
        )

    cases = load_jsonl(cases_path, DedupeCase)
    metrics, details = evaluate_dedupe_pairs(cases, dedupe_fn=dedupe_fn)
    metadata = build_run_metadata(SUITE, [cases_path], len(cases))
    return EvalReport(
        suite=SUITE,
        metadata=metadata,
        metrics=metrics,
        details=details,
    )
