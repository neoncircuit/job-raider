"""
Unit tests for JobListingStorage catalog upsert and lookup.

Author: Job Raider
Date: 2026-08-13
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

from src.models.job_listing import JobListing, JobListingCollection, JobSource
from src.scrapers.storage import JobListingStorage


def _listing(job_id: str, **kwargs) -> JobListing:
    """Build a listing for catalog tests."""
    defaults = {
        "title": "Engineer",
        "company": "Acme",
        "job_id": job_id,
        "source": JobSource.LINKEDIN,
        "description": "Short JD",
    }
    defaults.update(kwargs)
    return JobListing(**defaults)


class TestListingCatalog:
    """Canonical catalog is the lookup source of truth."""

    def test_upsert_and_get_by_id(self, tmp_path: Path) -> None:
        """Upsert writes catalog.json and get_by_id returns the row."""
        storage = JobListingStorage(str(tmp_path))
        now = datetime(2026, 8, 13, 12, 0, 0)
        storage.upsert_listings([_listing("job-1")], now=now)

        loaded = storage.get_by_id("job-1")
        assert loaded is not None
        assert loaded.title == "Engineer"
        assert loaded.last_seen_at == now
        assert storage.catalog_path.exists()

    def test_upsert_refreshes_last_seen_and_keeps_longer_description(
        self, tmp_path: Path
    ) -> None:
        """A later scrape updates last_seen_at and keeps the richer JD."""
        storage = JobListingStorage(str(tmp_path))
        first = datetime(2026, 8, 1, 12, 0, 0)
        second = datetime(2026, 8, 13, 12, 0, 0)
        storage.upsert_listings(
            [_listing("job-1", description="A" * 200)], now=first
        )
        storage.upsert_listings(
            [_listing("job-1", description="short")], now=second
        )

        loaded = storage.get_by_id("job-1")
        assert loaded is not None
        assert loaded.last_seen_at == second
        assert loaded.description == "A" * 200

    def test_get_by_id_missing_returns_none(self, tmp_path: Path) -> None:
        """Unknown IDs return None rather than raising."""
        storage = JobListingStorage(str(tmp_path))
        assert storage.get_by_id("missing") is None

    def test_cleanup_skips_catalog(self, tmp_path: Path) -> None:
        """Age cleanup must not delete catalog.json."""
        storage = JobListingStorage(str(tmp_path), max_age_days=1)
        storage.upsert_listings([_listing("job-1")])
        storage.save_collection(JobListingCollection(listings=[_listing("job-old")]))
        old_mtime = (datetime.now() - timedelta(days=40)).timestamp()
        for path in tmp_path.glob("*.json"):
            if path.name != JobListingStorage.CATALOG_FILENAME:
                os.utime(path, (old_mtime, old_mtime))

        removed = storage.cleanup_old_listings()
        assert removed >= 1
        assert storage.catalog_path.exists()
        assert storage.get_by_id("job-1") is not None
        leftover = {path.name for path in tmp_path.glob("*.json")}
        assert leftover == {JobListingStorage.CATALOG_FILENAME}
