"""
Tests for the dedupe evaluation suite (Step 3.5 Stage A).

Each test writes a small dataset under ``tmp_path``. The tests do not read
the committed dedupe set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.evaluation.metrics import wilson_interval
from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import build_run_metadata
from src.evaluation.suites import SUITE_NAMES, get_suite
from src.evaluation.suites.dedupe import (
    DEFAULT_DATASET_DIR,
    DedupeCase,
    evaluate_dedupe_pairs,
    run_dedupe_suite,
)
from src.models.job_listing import JobListing


def _listing(job_id: str, title: str = "Clerk") -> Dict[str, Any]:
    """
    Build one listing payload for a synthetic pair.

    Args:
        job_id: Listing identifier.
        title: Job title.

    Returns:
        Fields that ``JobListing.model_validate`` accepts.
    """
    return {
        "title": title,
        "company": "Test Bench",
        "job_id": job_id,
        "source": "jobstreet",
        "source_url": f"https://www.jobstreet.com.sg/job/{job_id}",
        "location": "Singapore",
        "description": "Keep the book current. File the sheet at noon.",
    }


def _case(
    case_id: str,
    pair_class: str,
    expected: str,
    left_id: str,
    right_id: str,
) -> Dict[str, Any]:
    """
    Build one JSONL case object.

    Args:
        case_id: Case identifier.
        pair_class: Class name.
        expected: ``same``, ``different``, or ``TODO``.
        left_id: ``job_id`` of listing A.
        right_id: ``job_id`` of listing B.

    Returns:
        A case dictionary.
    """
    return {
        "case_id": case_id,
        "class": pair_class,
        "expected": expected,
        "a": _listing(left_id),
        "b": _listing(right_id),
        "source": "constructed",
        "note": "synthetic suite case",
    }


def _write_cases(folder: Path, rows: List[Dict[str, Any]]) -> Path:
    """
    Write a temporary cases.jsonl file.

    Args:
        folder: Dataset folder.
        rows: Case objects.

    Returns:
        Path of the written file.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "cases.jsonl"
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _merge_ids(*job_ids: str):
    """
    Return a ``dedupe_fn`` that merges only a named pair, in that order.

    Args:
        job_ids: Two ``job_id`` values. A call matches when the arguments
            are exactly this order.

    Returns:
        A function that returns 1 for that order and 2 otherwise.
    """
    wanted = tuple(job_ids)

    def _dedupe(first: JobListing, second: JobListing) -> int:
        """
        Merge only the named order.

        Args:
            first: First listing.
            second: Second listing.

        Returns:
            1 when the pair matches, otherwise 2.
        """
        if (first.job_id, second.job_id) == wanted:
            return 1
        return 2

    return _dedupe


def _merge_either(*job_ids: str):
    """
    Return a ``dedupe_fn`` that merges a named pair in either order.

    Args:
        job_ids: Two ``job_id`` values.

    Returns:
        A function that returns 1 when both IDs are present.
    """
    wanted = frozenset(job_ids)

    def _dedupe(first: JobListing, second: JobListing) -> int:
        """
        Merge when both IDs are the named pair.

        Args:
            first: First listing.
            second: Second listing.

        Returns:
            1 when the IDs match, otherwise 2.
        """
        if {first.job_id, second.job_id} == wanted:
            return 1
        return 2

    return _dedupe


def test_metrics_and_per_class_on_a_known_small_set(tmp_path: Path) -> None:
    """
    Check precision, recall, F1, false-merge rate, and per-class counts.

    Returns:
        None.

    Args:
        tmp_path: Temporary dataset folder.
    """
    rows = [
        _case("c0__copy", "C0", "same", "keep-a", "keep-a"),
        _case("c1__miss", "C1", "same", "miss-a", "miss-b"),
        _case("h1__false", "H1", "different", "false-a", "false-b"),
        _case("h2__clean", "H2", "different", "clean-a", "clean-b"),
    ]
    _write_cases(tmp_path, rows)

    def _dedupe(first: JobListing, second: JobListing) -> int:
        """
        Merge the C0 copy and the H1 false pair.

        Args:
            first: First listing.
            second: Second listing.

        Returns:
            1 for the two merge pairs, otherwise 2.
        """
        pair = {first.job_id, second.job_id}
        if pair == {"keep-a"} or pair == {"false-a", "false-b"}:
            return 1
        return 2

    report = run_dedupe_suite(tmp_path, dedupe_fn=_dedupe)
    precision_ci = wilson_interval(1, 2)
    recall_ci = wilson_interval(1, 2)
    false_merge_ci = wilson_interval(1, 2)
    assert report.suite == "dedupe"
    assert report.metrics["case_count"] == 4
    assert report.metrics["precision"] == 0.5
    assert report.metrics["recall"] == 0.5
    assert report.metrics["f1"] == 0.5
    assert report.metrics["false_merge_rate"] == 0.5
    assert report.metrics["precision.ci95_low"] == precision_ci[0]
    assert report.metrics["precision.ci95_high"] == precision_ci[1]
    assert report.metrics["recall.ci95_low"] == recall_ci[0]
    assert report.metrics["recall.ci95_high"] == recall_ci[1]
    assert report.metrics["false_merge_rate.ci95_low"] == false_merge_ci[0]
    assert report.metrics["false_merge_rate.ci95_high"] == false_merge_ci[1]
    assert report.details["confusion"] == {
        "true_positives": 1,
        "false_positives": 1,
        "false_negatives": 1,
        "true_negatives": 1,
    }
    assert report.details["per_class"] == {
        "C0": {"merged": 1, "total": 1},
        "C1": {"merged": 0, "total": 1},
        "H1": {"merged": 1, "total": 1},
        "H2": {"merged": 0, "total": 1},
    }
    assert report.details["order_dependent"] == 0
    assert report.metrics["order_dependent"] == 0


def test_order_dependent_count_uses_both_orders(tmp_path: Path) -> None:
    """
    Count a pair that merges in one order only.

    The decision uses ``[a, b]``. The reversed call still runs.

    Args:
        tmp_path: Temporary dataset folder.

    Returns:
        None.
    """
    rows = [_case("c1__order", "C1", "same", "left", "right")]
    _write_cases(tmp_path, rows)
    report = run_dedupe_suite(tmp_path, dedupe_fn=_merge_ids("left", "right"))
    assert report.details["order_dependent"] == 1
    assert report.metrics["order_dependent"] == 1
    assert report.details["cases"][0]["merged"] is True
    assert report.details["cases"][0]["merged_reversed"] is False
    assert report.details["confusion"]["true_positives"] == 1


def test_todo_label_refuses_the_run(tmp_path: Path) -> None:
    """
    Stop when a catalog pair is still unlabeled.

    Args:
        tmp_path: Temporary dataset folder.

    Returns:
        None.
    """
    rows = [
        {
            "case_id": "catalog__pending",
            "class": "catalog",
            "expected": "TODO",
            "a": _listing("cat-a"),
            "b": _listing("cat-b"),
            "source": "catalog",
            "note": "unlabeled",
        }
    ]
    _write_cases(tmp_path, rows)
    with pytest.raises(ValueError, match="label the pairs first"):
        run_dedupe_suite(tmp_path)


def test_cli_routes_eval_dedupe_to_the_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    ``eval dedupe`` parses and calls the dedupe runner.

    Args:
        tmp_path: Temporary report folder.
        monkeypatch: Suite registry replacement.

    Returns:
        None.
    """
    import main as cli
    from tests.unit.test_cli import parse

    args = parse(["eval", "dedupe"])
    assert args.suite == "dedupe"
    runner, dataset_dir = get_suite("dedupe")
    assert runner is run_dedupe_suite
    assert dataset_dir == DEFAULT_DATASET_DIR
    assert "dedupe" in SUITE_NAMES

    seen: Dict[str, Any] = {}

    def fake_dedupe(dataset: Path, **kwargs: Any) -> EvalReport:
        seen["dataset"] = dataset
        seen["kwargs"] = kwargs
        path = tmp_path / "cases.jsonl"
        path.write_text("{}\n", encoding="utf-8")
        return EvalReport(
            suite="dedupe",
            metadata=build_run_metadata("dedupe", [path], 1, repo_dir=tmp_path),
            metrics={"precision": 1.0},
            details={},
        )

    def fake_get_suite(name: str) -> tuple:
        assert name == "dedupe"
        return fake_dedupe, tmp_path

    monkeypatch.setattr("src.evaluation.suites.get_suite", fake_get_suite)
    out = tmp_path / "out"
    routed = parse(
        [
            "eval",
            "dedupe",
            "--dataset",
            str(tmp_path),
            "--out",
            str(out),
            "--no-mlflow",
        ]
    )
    assert cli.run_eval_command(routed) == 0
    assert seen["dataset"] == tmp_path
    assert seen["kwargs"] == {}


def test_evaluate_accepts_a_validated_case() -> None:
    """
    ``DedupeCase`` loads a catalog pair after the user labels it.

    Returns:
        None.
    """
    case = DedupeCase.model_validate(
        {
            "case_id": "catalog__labeled",
            "class": "catalog",
            "expected": "same",
            "a": _listing("lab-a"),
            "b": _listing("lab-b"),
            "source": "catalog",
            "note": "labeled later",
        }
    )
    metrics, details = evaluate_dedupe_pairs(
        [case], dedupe_fn=_merge_either("lab-a", "lab-b")
    )
    assert metrics["precision"] == 1.0
    assert details["per_class"]["catalog"] == {"merged": 1, "total": 1}
