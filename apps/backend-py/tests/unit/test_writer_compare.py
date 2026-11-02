"""Tests for the paired comparison of two writer reports (Step 3.8, MH-3)."""

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest

import src.evaluation.writer_compare as writer_compare


def report(
    model: str,
    pairs: Dict[str, Tuple[int, int]],
    tech_rate: float = 0.1,
    sha: str = "a" * 64,
) -> Dict[str, Any]:
    """
    A writer report in the shape of ``eval writer``, for the comparison tests.

    Args:
        model: The writer model of the run.
        pairs: Case ID to ``(written letters, letters flagged with ungrounded_claims)``.
        tech_rate: The ``fabricated_technology_rate`` of the run.
        sha: The dataset SHA-256 of the run.

    Returns:
        The report as a dictionary.
    """
    written = sum(count for count, _ in pairs.values())
    flagged = sum(count for _, count in pairs.values())
    return {
        "suite": "writer",
        "metadata": {"dataset_sha256": sha, "model": model},
        "metrics": {
            "ungrounded_claims_rate": round(flagged / written, 3) if written else None,
            "fabricated_technology_rate": tech_rate,
        },
        "details": {
            "model": model,
            "pairs": {
                case_id: {
                    "profile_id": "ml",
                    "written": count,
                    "flagged": {
                        "ungrounded_claims": flags,
                        "fabricated_technology": 0,
                        "fabricated_experience": 0,
                        "scope_inflation": 0,
                    },
                }
                for case_id, (count, flags) in pairs.items()
            },
        },
    }


def test_pair_differences_are_other_minus_baseline_by_case_id() -> None:
    """Each difference is the other share minus the baseline share, in case-ID order."""
    baseline = report("qwen2.5:7b", {"b": (3, 3), "a": (3, 0)})
    other = report("qwen3.5:4b", {"a": (3, 1), "b": (3, 0)})

    diffs = writer_compare.pair_differences(baseline, other)

    assert diffs == pytest.approx([1 / 3, -1.0])


def test_pairs_without_written_letters_in_both_are_left_out() -> None:
    """A pair with no written letters in either report is not compared."""
    baseline = report(
        "qwen2.5:7b", {"a": (3, 1), "b": (3, 1), "c": (3, 3), "e": (0, 0)}
    )
    other = report("qwen3.5:4b", {"a": (2, 2), "b": (0, 0), "d": (3, 0), "e": (3, 1)})

    diffs = writer_compare.pair_differences(baseline, other)

    assert diffs == pytest.approx([1.0 - 1 / 3])


def test_bootstrap_interval_repeats_with_the_seed() -> None:
    """The same seed gives the same interval, inside the range of the values."""
    values = [i / 10 - 1.0 for i in range(20)]

    first = writer_compare.bootstrap_interval(values, rounds=500, seed=7)
    second = writer_compare.bootstrap_interval(values, rounds=500, seed=7)

    assert first == second
    low, high = first
    assert -1.0 <= low <= high <= 0.9


def test_bootstrap_interval_of_equal_values_is_that_value() -> None:
    """Equal values give an interval of that value."""
    assert writer_compare.bootstrap_interval([-0.5] * 10, rounds=50) == (-0.5, -0.5)


def test_bootstrap_interval_without_values_is_empty() -> None:
    """No values give no interval."""
    assert writer_compare.bootstrap_interval([]) == (None, None)


def test_switch_when_the_interval_is_below_zero_and_tech_is_not_worse() -> None:
    """The other model wins on every pair and its technology rate is not higher."""
    cases = {f"c{i}": (3, 3) for i in range(10)}
    baseline = report("qwen2.5:7b", cases, tech_rate=0.2)
    other = report("qwen3.5:4b", {case: (3, 1) for case in cases}, tech_rate=0.2)

    result = writer_compare.compare_reports(baseline, other)

    assert result["decision"] == "switch"
    assert result["pairs"] == 10
    assert result["mean_difference"] == -0.667
    assert result["ci_high"] == -0.667
    assert result["baseline_model"] == "qwen2.5:7b"
    assert result["other_model"] == "qwen3.5:4b"
    assert result["baseline_rate"] == 1.0
    assert result["other_rate"] == 0.333


def test_keep_when_fabricated_technology_is_higher() -> None:
    """A higher technology rate in the other model keeps the baseline."""
    cases = {f"c{i}": (3, 3) for i in range(10)}
    baseline = report("qwen2.5:7b", cases, tech_rate=0.1)
    other = report("qwen3.5:4b", {case: (3, 1) for case in cases}, tech_rate=0.2)

    result = writer_compare.compare_reports(baseline, other)

    assert result["decision"] == "keep"


def test_keep_when_the_interval_crosses_zero() -> None:
    """An interval that contains 0 keeps the baseline."""
    baseline_pairs = {}
    other_pairs = {}
    for i in range(10):
        baseline_pairs[f"c{i}"] = (3, 1) if i % 2 else (3, 2)
        other_pairs[f"c{i}"] = (3, 2) if i % 2 else (3, 1)
    baseline = report("qwen2.5:7b", baseline_pairs)
    other = report("qwen3.5:4b", other_pairs)

    result = writer_compare.compare_reports(baseline, other)

    assert result["ci_low"] < 0 < result["ci_high"]
    assert result["decision"] == "keep"


def test_reports_of_different_datasets_are_refused() -> None:
    """Reports from different datasets cannot be compared."""
    baseline = report("qwen2.5:7b", {"a": (3, 1)})
    other = report("qwen3.5:4b", {"a": (3, 1)}, sha="b" * 64)

    with pytest.raises(ValueError, match="different datasets"):
        writer_compare.compare_reports(baseline, other)


def test_load_writer_report_refuses_another_suite(tmp_path: Path) -> None:
    """A report of another suite is not a writer report."""
    path = tmp_path / "grounding.json"
    path.write_text(json.dumps({"suite": "grounding"}), encoding="utf-8")

    with pytest.raises(ValueError, match="not a writer report"):
        writer_compare.load_writer_report(path)


def test_script_prints_the_decision(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The script prints the decision and returns 0."""
    from scripts.compare_writer_reports import main

    cases = {f"c{i}": (3, 3) for i in range(5)}
    baseline_path = tmp_path / "baseline.json"
    other_path = tmp_path / "other.json"
    baseline_path.write_text(json.dumps(report("qwen2.5:7b", cases)), encoding="utf-8")
    other_path.write_text(
        json.dumps(report("qwen3.5:4b", {case: (3, 1) for case in cases})),
        encoding="utf-8",
    )

    assert main([str(baseline_path), str(other_path)]) == 0
    assert "decision: switch" in capsys.readouterr().out


def test_script_stops_on_a_wrong_report(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The script prints a clear message and returns 1 for a wrong report."""
    from scripts.compare_writer_reports import main

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"suite": "grounding"}), encoding="utf-8")

    assert main([str(bad), str(bad)]) == 1
    assert "Cannot compare" in capsys.readouterr().out
