"""
Metric functions for the offline evaluation suites (Step 3.1).

Multi-label precision, recall, and F1 (for checks such as the cover-letter
grounding validator), and graded ranking metrics (NDCG@k and recall@k).
A ratio with a zero denominator is ``None`` (undefined), not 0, so a label
that never occurs does not look like a failure or a success.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class LabelScores:
    """Counts and ratios for one label (or for all labels pooled)."""

    label: str
    true_positives: int
    false_positives: int
    false_negatives: int
    support: int
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]


def wilson_interval(
    successes: int, trials: int, z: float = 1.96
) -> Optional[Tuple[float, float]]:
    """
    Wilson score interval for a binomial proportion.

    Args:
        successes: Count of positive outcomes.
        trials: Number of trials.
        z: Normal quantile. The default 1.96 is a 95 percent interval.

    Returns:
        ``(low, high)`` clamped to ``[0, 1]``, or None when ``trials`` is 0.
    """
    if trials == 0:
        return None
    proportion = successes / trials
    z_squared = z * z
    denominator = 1.0 + z_squared / trials
    centre = (proportion + z_squared / (2.0 * trials)) / denominator
    spread = (z / denominator) * math.sqrt(
        proportion * (1.0 - proportion) / trials + z_squared / (4.0 * trials * trials)
    )
    low = max(0.0, centre - spread)
    high = min(1.0, centre + spread)
    return (low, high)


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    """
    Divide, or return None when the denominator is 0.

    Args:
        numerator: Count above the line.
        denominator: Count below the line.

    Returns:
        The ratio, or None when it is undefined.
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


def _scores(label: str, tp: int, fp: int, fn: int) -> LabelScores:
    """
    Build a ``LabelScores`` from raw counts.

    Args:
        label: Label name.
        tp: True positives.
        fp: False positives.
        fn: False negatives.

    Returns:
        Scores with precision, recall, and F1 filled in.
    """
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return LabelScores(
        label=label,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        support=tp + fn,
        precision=precision,
        recall=recall,
        f1=_f1(precision, recall),
    )


def multilabel_scores(
    expected: Sequence[Set[str]],
    predicted: Sequence[Set[str]],
    labels: Iterable[str],
) -> Dict[str, LabelScores]:
    """
    Per-label precision, recall, and F1 over multi-label cases.

    Predictions for labels outside ``labels`` are ignored.

    Args:
        expected: Expected label set per case.
        predicted: Predicted label set per case (same order).
        labels: Labels to score.

    Returns:
        Mapping of label to its scores.

    Raises:
        ValueError: When ``expected`` and ``predicted`` differ in length.
    """
    if len(expected) != len(predicted):
        raise ValueError(
            f"expected has {len(expected)} cases but predicted has {len(predicted)}"
        )
    result: Dict[str, LabelScores] = {}
    for label in labels:
        tp = fp = fn = 0
        for want, got in zip(expected, predicted):
            if label in want and label in got:
                tp += 1
            elif label in got:
                fp += 1
            elif label in want:
                fn += 1
        result[label] = _scores(label, tp, fp, fn)
    return result


def micro_scores(per_label: Mapping[str, LabelScores]) -> LabelScores:
    """
    Pool the counts of every label (micro average).

    Args:
        per_label: Output of ``multilabel_scores``.

    Returns:
        Scores with the label ``"micro"``.
    """
    tp = sum(s.true_positives for s in per_label.values())
    fp = sum(s.false_positives for s in per_label.values())
    fn = sum(s.false_negatives for s in per_label.values())
    return _scores("micro", tp, fp, fn)


def clean_case_false_positive_rate(
    expected: Sequence[Set[str]], predicted: Sequence[Set[str]]
) -> Optional[float]:
    """
    Share of clean cases (no expected label) with at least one prediction.

    Args:
        expected: Expected label set per case.
        predicted: Predicted label set per case (same order).

    Returns:
        The rate, or None when there is no clean case.
    """
    clean = [got for want, got in zip(expected, predicted) if not want]
    return _ratio(sum(1 for got in clean if got), len(clean))


def _dcg(relevances: Sequence[float]) -> float:
    """
    Discounted cumulative gain with gain ``2^rel - 1``.

    Args:
        relevances: Graded relevance in ranked order.

    Returns:
        DCG of the sequence.
    """
    return sum(
        (2**rel - 1) / math.log2(position + 2)
        for position, rel in enumerate(relevances)
    )


def ndcg_at_k(
    ranked_ids: Sequence[str], relevance: Mapping[str, float], k: int
) -> Optional[float]:
    """
    Normalized DCG of the first ``k`` ranked items.

    Items without a label have relevance 0. The ideal ranking uses every
    labeled item, so a relevant item that the ranking misses lowers the score.

    Args:
        ranked_ids: Item IDs in ranked order.
        relevance: Graded relevance per labeled item (0 = not relevant).
        k: Cut-off.

    Returns:
        NDCG@k in [0, 1], or None when no labeled item is relevant.
    """
    ideal = _dcg(sorted(relevance.values(), reverse=True)[:k])
    if ideal == 0:
        return None
    actual = _dcg([relevance.get(item, 0) for item in ranked_ids[:k]])
    return actual / ideal


def recall_at_k(
    ranked_ids: Sequence[str],
    relevance: Mapping[str, float],
    k: int,
    min_relevance: float = 1,
) -> Optional[float]:
    """
    Share of relevant items found in the first ``k`` ranked items.

    Args:
        ranked_ids: Item IDs in ranked order.
        relevance: Graded relevance per labeled item.
        k: Cut-off.
        min_relevance: Lowest grade that counts as relevant.

    Returns:
        Recall@k, or None when no labeled item is relevant.
    """
    relevant = {item for item, rel in relevance.items() if rel >= min_relevance}
    if not relevant:
        return None
    return len(relevant.intersection(ranked_ids[:k])) / len(relevant)
