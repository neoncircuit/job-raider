"""Tests for the secondary analysis of the writer comparison (Step 3.8, MH-4)."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

import src.evaluation.writer_compare as writer_compare

SHA = "a" * 64


def report(
    model: str,
    letters: Dict[str, List[int]],
    scope: Optional[Dict[str, int]] = None,
    tech_rate: float = 0.0,
    sha: str = SHA,
) -> Dict[str, Any]:
    """
    A small writer report with rows.

    Args:
        model: The writer model.
        letters: Case ID to the flagged sentence count of each written letter.
        scope: Case ID to its letters with scope_inflation (default: none).
        tech_rate: The fabricated_technology rate.
        sha: The dataset SHA-256.

    Returns:
        The report as a dictionary, in the shape of ``main.py eval writer``.
    """
    scope = scope or {}
    rows = [
        {
            "case_id": case_id,
            "sample": sample,
            "outcome": "written",
            "ungrounded_sentences": count,
        }
        for case_id, counts in letters.items()
        for sample, count in enumerate(counts)
    ]
    written = len(rows)
    flagged = sum(scope.values())
    return {
        "suite": "writer",
        "metadata": {"dataset_sha256": sha, "model": model},
        "metrics": {
            "ungrounded_claims_rate": 1.0,
            "scope_inflation_rate": round(flagged / written, 3) if written else None,
            "fabricated_technology_rate": tech_rate,
            "words_p50": 240.0,
        },
        "details": {
            "model": model,
            "pairs": {
                case_id: {
                    "profile_id": "ml",
                    "written": len(counts),
                    "flagged": {
                        "ungrounded_claims": len(counts),
                        "fabricated_technology": 0,
                        "fabricated_experience": 0,
                        "scope_inflation": scope.get(case_id, 0),
                    },
                }
                for case_id, counts in letters.items()
            },
            "rows": rows,
        },
    }


def ten_pairs(count: int) -> Dict[str, List[int]]:
    """
    Ten pairs with three letters each, all with the same sentence count.

    Args:
        count: The flagged sentence count of each letter.

    Returns:
        Case ID to the counts.
    """
    return {f"c{i}": [count, count, count] for i in range(10)}


def test_sentence_means_use_written_letters_only() -> None:
    """Rows that are not written letters do not enter the mean."""
    data = report("qwen2.5:7b", {"a": [2, 4]})
    data["details"]["rows"].append(
        {"case_id": "a", "sample": 2, "outcome": "fallback", "ungrounded_sentences": 0}
    )
    data["details"]["rows"].append(
        {"case_id": "b", "sample": 0, "outcome": "error", "ungrounded_sentences": 0}
    )

    assert writer_compare.sentence_means(data) == {"a": 3.0}
    assert writer_compare.mean_sentences(data) == 3.0


def test_sentence_differences_are_other_minus_baseline_by_case_id() -> None:
    """Each difference is the other mean minus the baseline mean, by case ID."""
    base = report("qwen2.5:7b", {"b": [4, 4], "a": [2, 2], "c": [1]})
    other = report("gemma3:4b", {"a": [1, 1], "b": [4, 6], "d": [9]})

    assert writer_compare.sentence_differences(base, other) == [-1.0, 1.0]


def test_secondary_switch_when_sentences_drop_and_nothing_rises() -> None:
    """Fewer flagged sentences, no more scope inflation or technology: switch."""
    result = writer_compare.compare_secondary(
        report("qwen2.5:7b", ten_pairs(4)), report("gemma3:4b", ten_pairs(2))
    )

    assert result["decision"] == "switch"
    assert result["pairs"] == 10
    assert result["baseline_sentences"] == 4.0
    assert result["other_sentences"] == 2.0
    assert result["s1_mean_difference"] == -2.0
    assert result["s1_ci_low"] == result["s1_ci_high"] == -2.0
    assert result["s2_mean_difference"] == 0.0
    assert result["baseline_model"] == "qwen2.5:7b"
    assert result["other_model"] == "gemma3:4b"


def test_secondary_keep_when_scope_inflation_rises() -> None:
    """Fewer flagged sentences but more scope inflation on every pair: keep."""
    scope = {f"c{i}": 3 for i in range(10)}

    result = writer_compare.compare_secondary(
        report("qwen2.5:7b", ten_pairs(4)),
        report("gemma3:4b", ten_pairs(2), scope=scope),
    )

    assert result["s2_ci_low"] == 1.0
    assert result["other_scope_inflation_rate"] == 1.0
    assert result["decision"] == "keep"


def test_secondary_switch_when_scope_inflation_may_fall() -> None:
    """An S2 interval that reaches below 0 does not block a switch."""
    scope_base = {f"c{i}": 3 for i in range(10)}

    result = writer_compare.compare_secondary(
        report("qwen2.5:7b", ten_pairs(4), scope=scope_base),
        report("gemma3:4b", ten_pairs(2)),
    )

    assert result["s2_ci_high"] == -1.0
    assert result["decision"] == "switch"


def test_secondary_switch_when_scope_inflation_is_unclear() -> None:
    """An S2 interval that crosses 0 does not block a switch."""
    scope_base = {f"c{i}": 3 for i in range(10) if i % 2}
    scope_other = {f"c{i}": 3 for i in range(10) if not i % 2}

    result = writer_compare.compare_secondary(
        report("qwen2.5:7b", ten_pairs(4), scope=scope_base),
        report("gemma3:4b", ten_pairs(2), scope=scope_other),
    )

    assert result["s2_ci_low"] < 0 < result["s2_ci_high"]
    assert result["decision"] == "switch"


def test_secondary_keep_when_sentences_do_not_drop() -> None:
    """Some pairs better and some worse: the S1 interval crosses 0, so keep."""
    base = {f"c{i}": [2 if i % 2 else 4] * 3 for i in range(10)}
    other = {f"c{i}": [4 if i % 2 else 2] * 3 for i in range(10)}

    result = writer_compare.compare_secondary(
        report("qwen2.5:7b", base), report("gemma3:4b", other)
    )

    assert result["s1_ci_low"] < 0 < result["s1_ci_high"]
    assert result["decision"] == "keep"


def test_secondary_keep_when_fabricated_technology_is_higher() -> None:
    """Fewer flagged sentences but more fabricated technology: keep."""
    result = writer_compare.compare_secondary(
        report("qwen2.5:7b", ten_pairs(4), tech_rate=0.0),
        report("gemma3:4b", ten_pairs(2), tech_rate=0.05),
    )

    assert result["decision"] == "keep"


def test_secondary_refuses_different_datasets() -> None:
    """Reports of two datasets cannot be compared."""
    with pytest.raises(ValueError, match="different datasets"):
        writer_compare.compare_secondary(
            report("qwen2.5:7b", ten_pairs(4)),
            report("gemma3:4b", ten_pairs(2), sha="b" * 64),
        )


def write_pair(tmp_path: Path) -> List[str]:
    """
    Write a baseline and an other report for the script tests.

    Args:
        tmp_path: The test folder.

    Returns:
        The two file paths, the baseline first.
    """
    paths: List[str] = []
    for name, count in (("base", 4), ("other", 2)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(report(name, ten_pairs(count))), encoding="utf-8")
        paths.append(str(path))
    return paths


def test_script_secondary_prints_the_secondary_result(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """With --secondary, the script prints S1, S2, and their decision."""
    from scripts.compare_writer_reports import main

    assert main([*write_pair(tmp_path), "--secondary"]) == 0
    out = capsys.readouterr().out
    assert "s1_mean_difference: -2.0" in out
    assert "s2_ci_high: 0.0" in out
    assert "decision: switch" in out


def test_script_default_is_the_original_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Without --secondary, the script prints the original comparison."""
    from scripts.compare_writer_reports import main

    assert main(write_pair(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "mean_difference: 0.0" in out
    assert "s1_" not in out
    assert "decision: keep" in out
