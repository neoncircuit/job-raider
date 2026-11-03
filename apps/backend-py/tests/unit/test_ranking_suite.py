"""Tests for the ranking eval suite (Step 3.4, MH-2)."""

import shutil
from pathlib import Path
from typing import Any, Dict, List

import pytest

import src.evaluation.suites.ranking as ranking
from src.evaluation.suites import SUITE_NAMES, get_suite
from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile

LABELS: Dict[str, int] = {"c": 0, "a": 2, "b": 1}


def profile_with(skills: List[str]) -> UserProfile:
    """
    A small profile with the given skills.

    Args:
        skills: Skill names.

    Returns:
        The profile.
    """
    return UserProfile.model_validate(
        {
            "name": "Test Person",
            "contact": {"email": "test@example.com", "location": "Singapore"},
            "skills": [{"name": name} for name in skills],
        }
    )


def job_with(job_id: str, title: str, description: str) -> JobListing:
    """
    A small job.

    Args:
        job_id: The job ID.
        title: The title.
        description: The description.

    Returns:
        The job.
    """
    return JobListing.model_validate(
        {
            "job_id": job_id,
            "title": title,
            "company": "Test Co",
            "source": "other",
            "description": description,
        }
    )


def test_ndcg_of_the_best_order_is_one() -> None:
    """The best order has NDCG 1, even when the labels are not in order."""
    assert ranking.ndcg_at_k(["a", "b", "c"], LABELS) == 1.0


def test_ndcg_of_the_reverse_order() -> None:
    """The reverse order gives DCG 1/log2(3) + 2/log2(4) over 2 + 1/log2(3)."""
    assert ranking.ndcg_at_k(["c", "b", "a"], LABELS) == pytest.approx(0.6199, abs=1e-4)


def test_ndcg_counts_only_the_top_k() -> None:
    """Jobs below the cut-off do not count."""
    assert ranking.ndcg_at_k(["c", "a", "b"], LABELS, k=1) == 0.0


def test_ndcg_without_a_relevant_job_is_none() -> None:
    """With no label above 0 there is no NDCG."""
    assert ranking.ndcg_at_k(["a", "b"], {"a": 0, "b": 0}) is None


def test_recall_counts_apply_labels_in_the_top_k() -> None:
    """Recall is the share of jobs labeled 2 in the top k; label 1 does not count."""
    labels = {"a": 2, "b": 1, "c": 2, "d": 0}

    assert ranking.recall_at_k(["a", "b", "d", "c"], labels, k=2) == 0.5
    assert ranking.recall_at_k(["b", "d"], {"b": 1, "d": 0}) is None


def test_ties_are_broken_by_job_id() -> None:
    """Equal scores are ordered by job ID."""
    assert ranking.sort_scores({"rk-002": 1.0, "rk-001": 1.0, "rk-003": 2.0}) == [
        ("rk-003", 2.0),
        ("rk-001", 1.0),
        ("rk-002", 1.0),
    ]


def test_heuristic_uses_the_profile_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each profile is scored with its own matcher mode."""
    seen: List[bool] = []
    real = ranking.JobMatcher

    def make(fresh_grad_mode: bool = False, **kwargs: Any) -> Any:
        """Record the mode and make a real matcher."""
        seen.append(fresh_grad_mode)
        return real(fresh_grad_mode=fresh_grad_mode, **kwargs)

    monkeypatch.setattr(ranking, "JobMatcher", make)

    ranking.run_ranking_suite(methods=["heuristic"])

    assert sorted(seen) == [False, True]


def test_bm25_uses_the_ranker_profile_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """BM25 searches with the RAG ranker's profile query."""
    monkeypatch.setattr(
        ranking.RAGRanker, "_build_profile_query_text", lambda self, profile: "zebra"
    )
    jobs = [
        job_with("j1", "Analyst", "Reports and dashboards for the sales team."),
        job_with("j2", "Keeper", "Care for the zebra herd and its enclosure."),
        job_with("j3", "Clerk", "File records and answer the phone."),
    ]

    result = ranking.bm25_ranking(profile_with(["Python"]), {}, jobs)

    assert result[0][0] == "j2"


def test_bm25_scores_a_job_by_its_best_chunk() -> None:
    """A job's short title chunk decides, not its weaker long-text chunk."""
    filler = " ".join(["Build reliable services for our customers."] * 40)
    jobs = [
        job_with("j1", "Kafka Engineer", filler),
        job_with("j2", "Backend Engineer", filler + " Kafka work with Kafka Streams."),
    ] + [
        job_with(f"f{n}", "Clerk", "File records and answer the phone.")
        for n in range(8)
    ]

    result = ranking.bm25_ranking(profile_with(["Kafka"]), {}, jobs)

    assert [job_id for job_id, _ in result[:2]] == ["j1", "j2"]


def test_suite_reports_each_method_and_profile() -> None:
    """The report has NDCG and recall for each method, each profile, and the mean."""
    report = ranking.run_ranking_suite()

    for method in ("heuristic", "bm25"):
        for pid in ("fresh_ml", "mid_backend"):
            for metric in ("ndcg_at_10", "recall_at_10"):
                value = report.metrics[f"{method}_{pid}_{metric}"]
                assert value is not None and 0.0 <= value <= 1.0
        mean = report.metrics[f"{method}_ndcg_at_10"]
        per_profile = [
            report.metrics[f"{method}_{pid}_ndcg_at_10"]
            for pid in ("fresh_ml", "mid_backend")
        ]
        assert mean == pytest.approx(sum(per_profile) / 2, abs=1e-4)
        assert len(report.details["top"][method]["fresh_ml"]) == 10
    assert report.suite == "ranking"
    assert report.metadata.case_count == 140


def test_suite_is_deterministic() -> None:
    """Two runs give the same metrics."""
    assert ranking.run_ranking_suite().metrics == ranking.run_ranking_suite().metrics


def test_unknown_method_is_refused() -> None:
    """Only known methods can run."""
    with pytest.raises(ValueError, match="unknown ranking methods"):
        ranking.run_ranking_suite(methods=["magic"])


def test_a_missing_label_is_refused(tmp_path: Path) -> None:
    """Every profile and job pair needs a label."""
    for path in ranking.DEFAULT_DATASET_DIR.iterdir():
        shutil.copy(path, tmp_path / path.name)
    labels = (tmp_path / "labels.jsonl").read_text(encoding="utf-8").splitlines()
    (tmp_path / "labels.jsonl").write_text(
        "\n".join(labels[:-1]) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="labels do not cover every job"):
        ranking.load_ranking_set(tmp_path)


def test_ranking_is_a_registered_suite() -> None:
    """The registry gives the ranking suite and its set."""
    runner, dataset_dir = get_suite("ranking")

    assert "ranking" in SUITE_NAMES
    assert runner is ranking.run_ranking_suite
    assert dataset_dir == ranking.DEFAULT_DATASET_DIR
