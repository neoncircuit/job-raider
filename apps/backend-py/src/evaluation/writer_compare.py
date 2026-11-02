"""
Paired comparison of two writer reports (Step 3.8).

Each writer report has, for each profile-job pair of the grounding set, the
written letters and the letters that each check flags. This module compares
another model with the baseline ``qwen2.5:7b`` pair by pair: the difference in
the share of letters with ``ungrounded_claims`` (other minus baseline), a 95%
bootstrap interval of the mean difference over the pairs, with a fixed seed.

Decision rule (fixed before the runs): change the default writer only when the
high end of that interval is below 0 and the other model's
``fabricated_technology`` rate is not higher than the baseline's. Otherwise
keep the baseline.
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .suites.writer import MAIN_CHECK, percentile

DEFAULT_ROUNDS = 2000
DEFAULT_SEED = 0


def load_writer_report(path: Path) -> Dict[str, Any]:
    """
    Read a writer report from a JSON file.

    Args:
        path: The report file.

    Returns:
        The report as a dictionary.

    Raises:
        ValueError: When the file is not a writer report.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("suite") != "writer":
        raise ValueError(f"{path} is not a writer report")
    return data


def pair_differences(
    baseline: Dict[str, Any], other: Dict[str, Any], check: str = MAIN_CHECK
) -> List[float]:
    """
    The difference in the flagged share of each pair, other minus baseline.

    Args:
        baseline: The baseline writer report.
        other: The other writer report of the same dataset.
        check: The check to compare (default: ``ungrounded_claims``).

    Returns:
        One difference for each case ID in both reports, in case-ID order.
        A pair with no written letters in either report is left out.
    """
    baseline_pairs = baseline["details"]["pairs"]
    other_pairs = other["details"]["pairs"]
    diffs: List[float] = []
    for case_id in sorted(set(baseline_pairs) & set(other_pairs)):
        base = baseline_pairs[case_id]
        new = other_pairs[case_id]
        if not base["written"] or not new["written"]:
            continue
        diffs.append(
            new["flagged"][check] / new["written"]
            - base["flagged"][check] / base["written"]
        )
    return diffs


def bootstrap_interval(
    values: Sequence[float],
    rounds: int = DEFAULT_ROUNDS,
    seed: int = DEFAULT_SEED,
) -> Tuple[Optional[float], Optional[float]]:
    """
    A 95% bootstrap interval of the mean, with a fixed seed.

    Args:
        values: The numbers, one for each pair.
        rounds: The number of resamples.
        seed: The seed of the random generator.

    Returns:
        The 2.5th and the 97.5th percentile of the resampled means, or
        ``(None, None)`` when there are no values.
    """
    if not values:
        return None, None
    rng = random.Random(seed)
    means = [
        statistics.fmean(rng.choices(values, k=len(values))) for _ in range(rounds)
    ]
    return percentile(means, 0.025), percentile(means, 0.975)


def compare_reports(
    baseline: Dict[str, Any],
    other: Dict[str, Any],
    rounds: int = DEFAULT_ROUNDS,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """
    Compare another writer report with the baseline, pair by pair.

    Args:
        baseline: The baseline writer report.
        other: The other writer report of the same dataset.
        rounds: The number of bootstrap resamples.
        seed: The seed of the bootstrap.

    Returns:
        The models, the number of pairs, the two rates, the mean difference,
        the 95% interval, the two ``fabricated_technology`` rates, and the
        decision (``switch`` or ``keep``).

    Raises:
        ValueError: When the reports come from different datasets.
        KeyError: When a report lacks a field that the comparison needs.
    """
    if baseline["metadata"]["dataset_sha256"] != other["metadata"]["dataset_sha256"]:
        raise ValueError("The reports come from different datasets.")
    diffs = pair_differences(baseline, other)
    mean = statistics.fmean(diffs) if diffs else None
    low, high = bootstrap_interval(diffs, rounds=rounds, seed=seed)
    base_tech = baseline["metrics"].get("fabricated_technology_rate")
    other_tech = other["metrics"].get("fabricated_technology_rate")
    switch = (
        high is not None
        and high < 0
        and base_tech is not None
        and other_tech is not None
        and other_tech <= base_tech
    )
    return {
        "baseline_model": baseline["details"]["model"],
        "other_model": other["details"]["model"],
        "pairs": len(diffs),
        "baseline_rate": baseline["metrics"]["ungrounded_claims_rate"],
        "other_rate": other["metrics"]["ungrounded_claims_rate"],
        "mean_difference": round(mean, 3) if mean is not None else None,
        "ci_low": round(low, 3) if low is not None else None,
        "ci_high": round(high, 3) if high is not None else None,
        "baseline_fabricated_technology_rate": base_tech,
        "other_fabricated_technology_rate": other_tech,
        "decision": "switch" if switch else "keep",
    }
