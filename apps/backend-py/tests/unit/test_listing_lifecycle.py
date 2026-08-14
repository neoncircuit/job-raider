"""
Unit tests for listing lifecycle status helpers.

Author: Job Raider
Date: 2026-08-13
"""

from datetime import datetime, timedelta

from src.models.job_listing import JobListing, JobSource
from src.scrapers.listing_lifecycle import (
    ListingStatus,
    attach_lifecycle_fields,
    is_scraped_today,
    listing_status_for_job_id,
    resolve_listing_status,
)


def _listing(**kwargs) -> JobListing:
    """Build a minimal listing for lifecycle tests."""
    defaults = {
        "title": "Engineer",
        "company": "Acme",
        "job_id": "job-1",
        "source": JobSource.LINKEDIN,
    }
    defaults.update(kwargs)
    return JobListing(**defaults)


class TestResolveListingStatus:
    """Expiry rules: deadline and last-seen age, not posted_date alone."""

    def test_deadline_passed_is_expired_even_if_seen_today(self) -> None:
        """A closed deadline expires the listing immediately."""
        now = datetime(2026, 8, 13, 12, 0, 0)
        listing = _listing(
            application_deadline=now - timedelta(hours=1),
            last_seen_at=now,
            scraped_at=now,
        )
        assert resolve_listing_status(listing, now=now) is ListingStatus.EXPIRED

    def test_stale_last_seen_is_expired(self) -> None:
        """Last seen 30+ days ago expires the listing."""
        now = datetime(2026, 8, 13, 12, 0, 0)
        listing = _listing(
            last_seen_at=now - timedelta(days=30),
            scraped_at=now - timedelta(days=30),
        )
        assert resolve_listing_status(listing, now=now) is ListingStatus.EXPIRED

    def test_old_posted_date_stays_active_if_seen_today(self) -> None:
        """An old posting that was scraped today is still active."""
        now = datetime(2026, 8, 13, 12, 0, 0)
        listing = _listing(
            posted_date=now - timedelta(days=60),
            last_seen_at=now,
            scraped_at=now,
        )
        assert resolve_listing_status(listing, now=now) is ListingStatus.ACTIVE

    def test_missing_dates_are_active(self) -> None:
        """Unknown last-seen does not expire the listing."""
        assert (
            resolve_listing_status(
                last_seen_at=None,
                scraped_at=None,
                now=datetime(2026, 8, 13),
            )
            is ListingStatus.ACTIVE
        )

    def test_does_not_unexpire_when_last_seen_missing_on_load(self) -> None:
        """Old JSON without last_seen_at uses scraped_at, not now()."""
        now = datetime(2026, 8, 13, 12, 0, 0)
        listing = _listing(scraped_at=now - timedelta(days=40), last_seen_at=None)
        assert resolve_listing_status(listing, now=now) is ListingStatus.EXPIRED


class TestScrapedToday:
    """Scraped-today uses local calendar date of last_seen_at."""

    def test_seen_today_is_true(self) -> None:
        """Same calendar day counts as scraped today."""
        now = datetime(2026, 8, 13, 18, 0, 0)
        listing = _listing(last_seen_at=datetime(2026, 8, 13, 1, 0, 0))
        assert is_scraped_today(listing, now=now) is True

    def test_seen_yesterday_is_false(self) -> None:
        """Previous calendar day is not scraped today."""
        now = datetime(2026, 8, 13, 1, 0, 0)
        listing = _listing(last_seen_at=datetime(2026, 8, 12, 23, 0, 0))
        assert is_scraped_today(listing, now=now) is False


class TestAttachLifecycleFields:
    """API dict enrichment for stored shortlist JSON."""

    def test_old_shortlist_dict_gets_status(self) -> None:
        """Legacy job dicts without listing_status are enriched in place."""
        now = datetime(2026, 8, 13, 12, 0, 0)
        job = {
            "job_id": "job-1",
            "scraped_at": now.isoformat(),
            "posted_date": (now - timedelta(days=3)).isoformat(),
        }
        attach_lifecycle_fields(job, now=now)
        assert job["listing_status"] == "active"
        assert job["scraped_today"] is True
        assert job["days_since_posted"] == 3
        assert job["last_seen_at"] == now.isoformat()


class TestListingStatusForJobId:
    """Application rows join catalog status by job_id."""

    def test_missing_catalog_row_is_unknown(self) -> None:
        """External or unsynced ids must not be treated as expired."""
        assert listing_status_for_job_id("ext-1", {}) is None
        assert listing_status_for_job_id("", {}) is None

    def test_stale_catalog_row_is_expired(self) -> None:
        """A catalog hit uses the same deadline / last-seen rules."""
        now = datetime(2026, 8, 13, 12, 0, 0)
        listing = _listing(
            job_id="job-stale",
            last_seen_at=now - timedelta(days=40),
            scraped_at=now - timedelta(days=40),
        )
        assert (
            listing_status_for_job_id("job-stale", {listing.job_id: listing}, now=now)
            == "expired"
        )
