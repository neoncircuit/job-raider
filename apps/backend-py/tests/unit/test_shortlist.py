"""
Unit tests for discover shortlist persistence.
"""

from pathlib import Path

from src.models.job_listing import JobListing, JobSource
from src.pipeline.shortlist import (
    load_latest_shortlist,
    save_latest_shortlist,
    serialize_scored_job,
)
from src.scoring.matcher import MatchScore


def _sample_job() -> JobListing:
    """Build a minimal listing for shortlist serialization."""
    return JobListing(
        job_id="job-42",
        title="Backend Engineer",
        company="Acme",
        location="Singapore",
        source=JobSource.LINKEDIN,
        source_url="https://www.linkedin.com/jobs/view/42",
        description="Build APIs",
    )


def _sample_score(job: JobListing) -> MatchScore:
    """Build a MatchScore for serialization tests."""
    return MatchScore(
        job=job,
        total_score=85,
        passed_threshold=True,
        breakdown={"skills": 40, "keyword": 25},
        matched_keywords=["python"],
        missing_skills=["go"],
        recommendation="apply",
        reasoning="Strong skills match",
    )


class TestDiscoverShortlist:
    """Persist and load the Jobs review shortlist artifact."""

    def test_serialize_includes_score_fields(self) -> None:
        """Serialized jobs include relevance score for the Jobs UI."""
        job = _sample_job()
        payload = serialize_scored_job((job, _sample_score(job)))
        assert payload["job_id"] == "job-42"
        assert payload["relevance_score"] == 85.0
        assert payload["recommendation"] == "apply"
        assert payload["url"].startswith("https://")

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """save_latest_shortlist writes a loadable artifact."""
        job = _sample_job()
        path = save_latest_shortlist(
            run_id="run_abc",
            mode="discover",
            keywords=["python"],
            locations=["Singapore"],
            scored_listings=[(job, _sample_score(job))],
            results_dir=tmp_path,
            jobs_scraped=70,
        )
        assert path.exists()
        data = load_latest_shortlist(tmp_path)
        assert data is not None
        assert data["run_id"] == "run_abc"
        assert data["mode"] == "discover"
        assert data["jobs_scraped"] == 70
        assert data["total"] == 1
        assert data["jobs"][0]["title"] == "Backend Engineer"

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        """Missing artifact returns None rather than raising."""
        assert load_latest_shortlist(tmp_path / "empty") is None
