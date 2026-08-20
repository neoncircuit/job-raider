"""
Unit tests for the unified AppliedGuard cross-source matcher.
"""

from pathlib import Path

import pytest

from src.metrics.outcome_tracker import ApplicationStatus, OutcomeTracker
from src.models.job_listing import JobListing, JobSource
from src.submission.applied_guard import AppliedGuard
from src.submission.applied_tracker import AppliedJobsTracker


@pytest.fixture
def trackers(tmp_path: Path) -> tuple[OutcomeTracker, AppliedJobsTracker]:
    """
    Create isolated outcome and applied trackers under tmp_path.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Tuple of (OutcomeTracker, AppliedJobsTracker).
    """
    outcomes = OutcomeTracker(storage_dir=str(tmp_path / "applications"))
    applied = AppliedJobsTracker(storage_dir=str(tmp_path / "applied_jobs"))
    return outcomes, applied


def _listing(
    job_id: str,
    title: str,
    company: str,
    *,
    url: str | None = None,
    already_applied: bool = False,
) -> JobListing:
    """
    Build a minimal JobListing for guard tests.

    Args:
        job_id: Listing id.
        title: Job title.
        company: Company name.
        url: Optional source URL.
        already_applied: Scraper applied flag.

    Returns:
        JobListing instance.
    """
    return JobListing(
        job_id=job_id,
        title=title,
        company=company,
        source=JobSource.JSEARCH,
        source_url=url or f"https://example.com/jobs/{job_id}",
        already_applied=already_applied,
    )


class TestAppliedGuard:
    """AppliedGuard match and filter behaviour."""

    def test_same_company_title_different_urls_stay_separate(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """Two postings at the same company with different URLs are not one apply."""
        outcomes, applied = trackers
        outcomes.track_external_application(
            job_id="li_1",
            job_title="Software Engineer",
            company="Acme",
            metadata={"source_url": "https://linkedin.com/jobs/view/1"},
        )
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        assert not guard.is_applied(
            job_id="mcf_2",
            title="Software Engineer",
            company="Acme",
            source_url="https://mycareersfuture.gov.sg/jobs/2",
        )

    def test_same_url_different_ids_match(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """Same listing URL matches even when job ids differ."""
        outcomes, applied = trackers
        outcomes.track_external_application(
            job_id="board_a",
            job_title="Analyst",
            company="DataCo",
            metadata={"source_url": "https://jobs.example.com/posting/99"},
        )
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        assert guard.is_applied(
            job_id="board_b",
            title="Different Title",
            company="Other Co",
            source_url="https://jobs.example.com/posting/99/",
        )

    def test_applied_jobs_tracker_id_matches(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """AppliedJobsTracker ids count as already applied."""
        outcomes, applied = trackers
        applied.mark_applied("li_tracked", "Engineer", "TechCorp", "linkedin")
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        assert guard.is_applied(
            job_id="li_tracked",
            title="Engineer",
            company="TechCorp",
            source_url="https://linkedin.com/jobs/view/li_tracked",
        )

    def test_bookmark_only_does_not_count(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """saved_bookmarked outcomes are excluded from the guard."""
        outcomes, applied = trackers
        outcomes.save_job("bm_1", "Engineer", "TechCorp")
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        assert not guard.is_applied(
            job_id="bm_1",
            title="Engineer",
            company="TechCorp",
            source_url="https://linkedin.com/jobs/view/bm_1",
        )

    def test_applied_elsewhere_counts(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """applied_elsewhere is a real apply track and blocks re-apply."""
        outcomes, applied = trackers
        outcomes.track_external_application(
            job_id="ext_1",
            job_title="Designer",
            company="DesignCo",
            metadata={"source_url": "https://jobstreet.com/job/ext_1"},
        )
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        outcome = outcomes.get_application("ext_1")
        assert outcome is not None
        assert outcome.current_status == ApplicationStatus.APPLIED_ELSEWHERE
        assert guard.is_applied(
            job_id="other_id",
            title="Designer",
            company="DesignCo",
            source_url="https://jobstreet.com/job/ext_1",
        )

    def test_interview_inbound_counts(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """Inbound interview stages count as already tracked."""
        outcomes, applied = trackers
        outcomes.track_external_application(
            job_id="in_1",
            job_title="PM",
            company="ProductCo",
            inbound=True,
            metadata={"source_url": "https://example.com/jobs/in_1"},
        )
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        outcome = outcomes.get_application("in_1")
        assert outcome is not None
        assert outcome.current_status == ApplicationStatus.SCREENING_SCHEDULED
        assert guard.is_applied(
            job_id="in_1",
            title="PM",
            company="ProductCo",
            source_url="https://example.com/jobs/in_1",
        )

    def test_company_title_when_one_side_missing_url(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """Company+title matches when either side lacks a URL."""
        outcomes, applied = trackers
        outcomes.track_external_application(
            job_id="no_url_app",
            job_title="Backend Engineer",
            company="StackInc",
            metadata={},
        )
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        assert guard.is_applied(
            job_id="with_url",
            title="Backend Engineer",
            company="StackInc",
            source_url="https://jsearch.example/job/99",
        )

    def test_annotate_and_filter_unapplied(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """annotate_listings sets already_applied; filter_unapplied removes them."""
        outcomes, applied = trackers
        outcomes.track_external_application(
            job_id="keep_out",
            job_title="SRE",
            company="OpsCo",
            metadata={"source_url": "https://example.com/sre"},
        )
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        listings = [
            _listing("keep_out", "SRE", "OpsCo", url="https://example.com/sre"),
            _listing("fresh", "New Role", "FreshCo", url="https://example.com/fresh"),
        ]
        annotated = guard.annotate_listings(listings)
        assert annotated[0].already_applied is True
        assert annotated[1].already_applied is False
        kept, removed = guard.filter_unapplied(annotated)
        assert removed == 1
        assert len(kept) == 1
        assert kept[0].job_id == "fresh"

    def test_not_interested_excluded(
        self, trackers: tuple[OutcomeTracker, AppliedJobsTracker]
    ) -> None:
        """not_interested (hidden) does not count as applied."""
        outcomes, applied = trackers
        outcomes.save_job("hid_1", "Engineer", "TechCorp")
        outcomes.mark_not_interested("hid_1")
        guard = AppliedGuard(outcome_tracker=outcomes, applied_tracker=applied)
        assert not guard.is_applied(
            job_id="hid_1",
            title="Engineer",
            company="TechCorp",
        )
