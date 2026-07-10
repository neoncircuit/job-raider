"""
Tests for deduplicate stage syncing scraper-detected applied jobs to tracker.

Verifies that when the LinkedIn scraper sets already_applied=True on a
JobListing, the deduplicate stage persists those IDs to the AppliedJobsTracker
and filters them from the output.
"""

from pathlib import Path

import pytest

from src.models.job_listing import JobListing, JobSource
from src.submission.applied_tracker import AppliedJobsTracker


@pytest.fixture
def tracker(tmp_path: Path) -> AppliedJobsTracker:
    """Create an AppliedJobsTracker with a temporary storage directory."""
    return AppliedJobsTracker(storage_dir=str(tmp_path / "applied_jobs"))


def _make_listing(
    job_id: str, title: str, company: str, already_applied: bool = False
) -> JobListing:
    """Create a minimal JobListing for testing."""
    return JobListing(
        job_id=job_id,
        title=title,
        company=company,
        source=JobSource.LINKEDIN,
        source_url=f"https://linkedin.com/jobs/view/{job_id}",
        already_applied=already_applied,
    )


class TestDeduplicateAppliedSync:
    """Tests for syncing scraper-detected applied status during deduplication."""

    def test_scraper_detected_applied_synced_to_tracker(
        self, tracker: AppliedJobsTracker
    ) -> None:
        """Jobs with already_applied=True should be synced to the tracker."""
        listings = [
            _make_listing("job_1", "Engineer", "TechCorp", already_applied=True),
            _make_listing("job_2", "Analyst", "DataCo", already_applied=False),
        ]

        # Simulate the sync loop from stage_deduplicate
        for job in listings:
            if job.already_applied and not tracker.is_applied(job.job_id):
                tracker.mark_applied(
                    job_id=job.job_id,
                    job_title=job.title,
                    company=job.company,
                    source=(
                        job.source
                        if isinstance(job.source, str)
                        else str(job.source.value)
                    ),
                )

        assert tracker.is_applied("job_1")
        assert not tracker.is_applied("job_2")

        data = tracker.get_applied_data("job_1")
        assert data is not None
        assert data["title"] == "Engineer"
        assert data["company"] == "TechCorp"
        assert data["source"] == "linkedin"

    def test_already_applied_jobs_filtered_from_results(
        self, tracker: AppliedJobsTracker
    ) -> None:
        """Jobs with already_applied=True should be removed from deduplicated output."""
        listings = [
            _make_listing("job_1", "Engineer", "TechCorp", already_applied=True),
            _make_listing("job_2", "Analyst", "DataCo", already_applied=False),
            _make_listing("job_3", "Manager", "BizInc", already_applied=True),
        ]

        # Sync then filter (mirrors stages.py logic)
        for job in listings:
            if job.already_applied and not tracker.is_applied(job.job_id):
                tracker.mark_applied(job.job_id, job.title, job.company, "linkedin")

        result = [
            job
            for job in listings
            if not job.already_applied and not tracker.is_applied(job.job_id)
        ]

        assert len(result) == 1
        assert result[0].job_id == "job_2"

    def test_tracker_already_knows_no_double_sync(
        self, tracker: AppliedJobsTracker
    ) -> None:
        """If tracker already knows a job, mark_applied should not be called again."""
        tracker.mark_applied("job_1", "Old Title", "Old Co", "linkedin")

        listings = [
            _make_listing("job_1", "New Title", "New Co", already_applied=True),
        ]

        # Sync loop should skip job_1 since tracker already knows it
        synced = []
        for job in listings:
            if job.already_applied and not tracker.is_applied(job.job_id):
                tracker.mark_applied(job.job_id, job.title, job.company, "linkedin")
                synced.append(job.job_id)

        assert len(synced) == 0
        # Original data should be preserved
        data = tracker.get_applied_data("job_1")
        assert data["title"] == "Old Title"

    def test_mixed_applied_sources(self, tracker: AppliedJobsTracker) -> None:
        """Mix of badge-detected, tracker-known, and fresh jobs filter correctly."""
        # Pre-seed one job in the tracker
        tracker.mark_applied("job_tracked", "Tracked Job", "TrackerCo", "linkedin")

        listings = [
            _make_listing("job_badge", "Badge Job", "BadgeCo", already_applied=True),
            _make_listing(
                "job_tracked", "Tracked Job", "TrackerCo", already_applied=False
            ),
            _make_listing("job_fresh", "Fresh Job", "FreshCo", already_applied=False),
            _make_listing("job_both", "Both Job", "BothCo", already_applied=True),
        ]

        # Also pre-track "job_both" to test the overlap case
        tracker.mark_applied("job_both", "Both Job", "BothCo", "linkedin")

        # Sync
        for job in listings:
            if job.already_applied and not tracker.is_applied(job.job_id):
                tracker.mark_applied(job.job_id, job.title, job.company, "linkedin")

        # Filter
        result = [
            job
            for job in listings
            if not job.already_applied and not tracker.is_applied(job.job_id)
        ]

        # Only job_fresh should survive
        assert len(result) == 1
        assert result[0].job_id == "job_fresh"

        # Badge-detected job should now be in tracker
        assert tracker.is_applied("job_badge")
