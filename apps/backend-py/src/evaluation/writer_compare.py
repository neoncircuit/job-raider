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

The baseline run showed that the validator flags every letter, so the share
above is at its ceiling. The secondary analysis (``compare_secondary``) was
fixed after the baseline, before the other results: S1 compares the mean
count of flagged ungrounded sentences in a letter, S2 the share of letters
with ``scope_inflation``, both pair by pair with the same bootstrap.
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


def sentence_means(report: Dict[str, Any]) -> Dict[str, float]:
    """
    For each pair: the mean count of flagged ungrounded sentences in a letter.

    Args:
        report: A writer report.

    Returns:
        Case ID to the mean count over the pair's written letters. Pairs
        with no written letter are left out.
    """
    counts: Dict[str, List[int]] = {}
    for row in report["details"]["rows"]:
        if row["outcome"] == "written":
            counts.setdefault(row["case_id"], []).append(row["ungrounded_sentences"])
    return {case_id: statistics.fmean(values) for case_id, values in counts.items()}


def sentence_differences(
    baseline: Dict[str, Any], other: Dict[str, Any]
) -> List[float]:
    """
    For each pair: the other model's mean sentence count minus the baseline's.

    Args:
        baseline: The baseline writer report.
        other: The other writer report of the same dataset.

    Returns:
        One difference for each pair with written letters in both reports,
        in case-ID order.
    """
    base = sentence_means(baseline)
    mine = sentence_means(other)
    return [mine[case_id] - base[case_id] for case_id in sorted(set(base) & set(mine))]


def mean_sentences(report: Dict[str, Any]) -> Optional[float]:
    """
    The mean count of flagged ungrounded sentences in a written letter.

    Args:
        report: A writer report.

    Returns:
        The mean over all written letters, rounded to 3 places, or None.
    """
    counts = [
        row["ungrounded_sentences"]
        for row in report["details"]["rows"]
        if row["outcome"] == "written"
    ]
    return round(statistics.fmean(counts), 3) if counts else None


def _round3(value: Optional[float]) -> Optional[float]:
    """
    A number rounded to 3 places.

    Args:
        value: The number, or None.

    Returns:
        The rounded number, or None.
    """
    return round(value, 3) if value is not None else None


def _summary(
    values: Sequence[float], rounds: int, seed: int
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    The mean of the values and its 95% bootstrap interval, rounded.

    Args:
        values: The pair differences.
        rounds: Bootstrap resamples.
        seed: Bootstrap seed.

    Returns:
        ``(mean, low, high)``, each rounded to 3 places, or None when there
        are no values.
    """
    low, high = bootstrap_interval(values, rounds=rounds, seed=seed)
    mean = statistics.fmean(values) if values else None
    return _round3(mean), _round3(low), _round3(high)


def compare_secondary(
    baseline: Dict[str, Any],
    other: Dict[str, Any],
    rounds: int = DEFAULT_ROUNDS,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """
    The secondary analysis of Step 3.8: S1, S2, and their rule.

    S1 compares the mean count of flagged ungrounded sentences in a letter,
    pair by pair. S2 compares the share of letters with ``scope_inflation``,
    pair by pair. Both use the bootstrap of ``bootstrap_interval``. The rule:
    change the default writer only when the S1 interval is below 0, the S2
    interval is not above 0, and the ``fabricated_technology`` rate is not
    higher. The analysis was fixed after the baseline, before the other
    results, because the main metric of the plan was at its ceiling.

    Args:
        baseline: The baseline writer report.
        other: The other writer report of the same dataset.
        rounds: Bootstrap resamples.
        seed: Bootstrap seed.

    Returns:
        The models, the pairs, the mean sentence counts, the S1 difference
        and interval, the two ``scope_inflation`` rates, the S2 difference
        and interval, the two median word counts, the two
        ``fabricated_technology`` rates, and the decision (``switch`` or
        ``keep``).

    Raises:
        ValueError: When the reports come from different datasets.
        KeyError: When a report lacks a field that the analysis needs.
    """
    if baseline["metadata"]["dataset_sha256"] != other["metadata"]["dataset_sha256"]:
        raise ValueError("The reports come from different datasets.")
    s1 = sentence_differences(baseline, other)
    s2 = pair_differences(baseline, other, check="scope_inflation")
    s1_mean, s1_low, s1_high = _summary(s1, rounds, seed)
    s2_mean, s2_low, s2_high = _summary(s2, rounds, seed)
    base_tech = baseline["metrics"].get("fabricated_technology_rate")
    other_tech = other["metrics"].get("fabricated_technology_rate")
    switch = (
        s1_high is not None
        and s1_high < 0
        and (s2_low is None or s2_low <= 0)
        and base_tech is not None
        and other_tech is not None
        and other_tech <= base_tech
    )
    return {
        "baseline_model": baseline["details"]["model"],
        "other_model": other["details"]["model"],
        "pairs": len(s1),
        "baseline_sentences": mean_sentences(baseline),
        "other_sentences": mean_sentences(other),
        "s1_mean_difference": s1_mean,
        "s1_ci_low": s1_low,
        "s1_ci_high": s1_high,
        "baseline_scope_inflation_rate": baseline["metrics"].get(
            "scope_inflation_rate"
        ),
        "other_scope_inflation_rate": other["metrics"].get("scope_inflation_rate"),
        "s2_mean_difference": s2_mean,
        "s2_ci_low": s2_low,
        "s2_ci_high": s2_high,
        "baseline_words_p50": baseline["metrics"].get("words_p50"),
        "other_words_p50": other["metrics"].get("words_p50"),
        "baseline_fabricated_technology_rate": base_tech,
        "other_fabricated_technology_rate": other_tech,
        "decision": "switch" if switch else "keep",
    }
