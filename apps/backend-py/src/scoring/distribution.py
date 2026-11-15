"""
Job Raider - Score distribution of a scoring run

Summarizes the scores of all jobs that the score-and-rank stage scored,
including the jobs below the cut-off, so that the scoring can be calibrated
from a pipeline run. The summary holds numbers only: counts per 10-point band,
the counts at 50 and at 60 or more, the mean of each score component, and the
same counts for jobs without a structured skill list. It holds no job text and
no profile data.

Author: Job Raider
Date: 2026-11-15
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

BAND_LABELS: Tuple[str, ...] = (
    "0-9",
    "10-19",
    "20-29",
    "30-39",
    "40-49",
    "50-59",
    "60-69",
    "70-79",
    "80-89",
    "90-100",
)
CUT_OFFS: Tuple[int, ...] = (50, 60)


def _band(total: float) -> str:
    """
    Return the 10-point band of a total score.

    Args:
        total: The total score (0 to 100; values outside are clamped).

    Returns:
        The band label, for example ``"50-59"``. 100 is in ``"90-100"``.
    """
    index = min(max(int(total) // 10, 0), len(BAND_LABELS) - 1)
    return BAND_LABELS[index]


def _cut_counts(totals: Sequence[float]) -> Dict[str, int]:
    """
    Count the totals at or above each cut-off.

    Args:
        totals: The total scores.

    Returns:
        ``{"at_or_above_50": n, "at_or_above_60": m}``.
    """
    return {f"at_or_above_{cut}": sum(t >= cut for t in totals) for cut in CUT_OFFS}


def _breakdown(score: Any) -> Dict[str, float]:
    """
    Return the numeric components of a score's breakdown.

    Args:
        score: A match score with an optional ``breakdown`` dict.

    Returns:
        Component name to points; empty when the score has no breakdown dict.
    """
    raw = getattr(score, "breakdown", None)
    if not isinstance(raw, dict):
        return {}
    return {
        str(name): float(value)
        for name, value in raw.items()
        if isinstance(value, (int, float))
    }


def score_distribution(pairs: Sequence[Tuple[Any, Any]]) -> Dict[str, Any]:
    """
    Summarize the scores of all scored jobs of one run.

    Args:
        pairs: ``(job, score)`` pairs for every scored job. A job needs a
            ``skills`` list; a score needs ``total_score`` and may have a
            ``breakdown`` dict.

    Returns:
        A dict with ``count``, ``bands`` (label to count), ``at_or_above_50``,
        ``at_or_above_60``, ``component_means`` (component to mean points over
        all jobs, rounded to 0.1), ``levels`` (experience level to the number
        of scored jobs), and ``without_skill_list`` (``count``, ``median`` or
        ``None``, and the two cut counts).
    """
    totals: List[float] = [float(score.total_score) for _, score in pairs]
    bands = {label: 0 for label in BAND_LABELS}
    for total in totals:
        bands[_band(total)] += 1

    components: Dict[str, List[float]] = {}
    for _, score in pairs:
        for name, value in _breakdown(score).items():
            components.setdefault(name, []).append(value)
    component_means = {
        name: round(statistics.mean(values), 1) for name, values in components.items()
    }

    levels: Dict[str, int] = {}
    for job, _ in pairs:
        level = getattr(job, "experience_level", None)
        name = str(getattr(level, "value", level) or "Not Specified")
        levels[name] = levels.get(name, 0) + 1

    no_skill_totals = [
        float(score.total_score)
        for job, score in pairs
        if not getattr(job, "skills", None)
    ]
    median: Optional[float] = (
        float(statistics.median(no_skill_totals)) if no_skill_totals else None
    )

    return {
        "count": len(totals),
        "bands": bands,
        **_cut_counts(totals),
        "component_means": component_means,
        "levels": levels,
        "without_skill_list": {
            "count": len(no_skill_totals),
            "median": median,
            **_cut_counts(no_skill_totals),
        },
    }
