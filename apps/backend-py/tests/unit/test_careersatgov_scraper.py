"""
Unit tests for the Careers@Gov delayed-catalog adapter.

Author: Job Raider
Date: 2026-08-15
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from src.models.job_listing import JobSource, JobType, WorkMode
from src.scrapers.base import ScrapingException, SearchParams
from src.scrapers.careersatgov_scraper import (
    MAX_RESULTS,
    CareersAtGovScraper,
    careersatgov_enabled,
    clear_dump_cache,
)
from src.utils.source_geography import listing_matches_requested_locations

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "careersatgov"
    / "job-listings.json"
)

SNAPSHOT = datetime(2026, 8, 14, 8, 10, 5)


def _fixture() -> List[Dict[str, Any]]:
    """Load the capped Careers@Gov dump fixture."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _reset_dump_cache() -> None:
    """Clear module dump cache around every test."""
    clear_dump_cache()
    yield
    clear_dump_cache()


class TestCareersAtGovEnabled:
    """Kill switch via CAREERSATGOV_ENABLED. Default is off."""

    def test_default_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing env defaults to disabled because the dump is delayed."""
        monkeypatch.delenv("CAREERSATGOV_ENABLED", raising=False)
        assert careersatgov_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_enables(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        """Common truthy strings enable the adapter."""
        monkeypatch.setenv("CAREERSATGOV_ENABLED", value)
        assert careersatgov_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
    def test_falsey_disables(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        """Falsey strings keep the delayed dump unregistered."""
        monkeypatch.setenv("CAREERSATGOV_ENABLED", value)
        assert careersatgov_enabled() is False


class TestParseJob:
    """Dump fixture maps to JobListing fields used by catalog lifecycle."""

    def test_maps_hrp_core_fields(self) -> None:
        """Title, agency, hybrid work, deadline, and delayed snapshot map."""
        scraper = CareersAtGovScraper(rate_limit=0)
        job = scraper._parse_job(_fixture()[0], snapshot_at=SNAPSHOT)

        assert job is not None
        assert job.job_id == ("cag-hrp-17060737-005056a3-d347-1fe1-83ab-e89b314c0286")
        assert job.source == JobSource.CAREERSATGOV.value
        assert job.title == "Software Engineer, Data Platform"
        assert job.company == "Government Technology Agency"
        assert job.location == "Singapore"
        assert job.work_mode == WorkMode.HYBRID.value
        assert job.job_type == JobType.FULL_TIME.value
        assert job.posted_date is not None
        assert job.application_deadline is not None
        assert job.last_seen_at == SNAPSHOT
        assert "jobs.careers.gov.sg/jobs/hrp/17060737/" in str(job.source_url or "")
        assert job.metadata["catalog_kind"] == "delayed_dump"
        assert job.metadata["dump_snapshot_at"] == SNAPSHOT.isoformat()
        assert job.description is not None
        assert "Build data platforms" in job.description
        assert "Python" in job.description

    def test_greenhouse_url_and_intern_type(self) -> None:
        """Greenhouse rows use gh_jid URLs and empty location becomes Singapore."""
        scraper = CareersAtGovScraper(rate_limit=0)
        job = scraper._parse_job(_fixture()[1], snapshot_at=SNAPSHOT)
        assert job is not None
        assert job.job_id == "cag-greenhouse-4001978201"
        assert job.job_type == JobType.INTERNSHIP.value
        assert job.location == "Singapore"
        assert "gh_jid=4001978201" in str(job.source_url or "")
        assert listing_matches_requested_locations(job, ["Singapore"])
        assert listing_matches_requested_locations(job, ["SG"])

    def test_missing_ids_raise(self) -> None:
        """Rows without platform or jobId are rejected."""
        scraper = CareersAtGovScraper(rate_limit=0)
        with pytest.raises(ValueError, match="platform or jobId"):
            scraper._parse_job({"jobTitle": "No Id"}, snapshot_at=SNAPSHOT)

    def test_district_matches_singapore_filter(self) -> None:
        """Islandwide dump locations survive the Singapore post-filter."""
        scraper = CareersAtGovScraper(rate_limit=0)
        job = scraper._parse_job(_fixture()[2], snapshot_at=SNAPSHOT)
        assert job is not None
        assert listing_matches_requested_locations(job, ["Singapore"])
        assert listing_matches_requested_locations(job, ["Remote"]) is False
        assert not listing_matches_requested_locations(job, ["New York"])


class TestSearchCaps:
    """Local dump filter, skip path, and disabled adapter."""

    def test_search_filters_fixture_and_caps(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Software search keeps engineer rows and drops facilities."""
        monkeypatch.setenv("CAREERSATGOV_ENABLED", "true")
        scraper = CareersAtGovScraper(rate_limit=0)
        rows = _fixture()

        with patch.object(scraper, "_fetch_dump", return_value=(rows, SNAPSHOT)):
            collection = scraper.search(SearchParams(keywords=["software"], limit=10))

        assert [job.job_id for job in collection.listings] == [
            "cag-hrp-17060737-005056a3-d347-1fe1-83ab-e89b314c0286"
        ]
        assert collection.listings[0].source == JobSource.CAREERSATGOV.value
        assert collection.listings[0].last_seen_at == SNAPSHOT
        assert collection.metadata["catalog_kind"] == "delayed_dump"
        assert collection.metadata["dump_snapshot_at"] == SNAPSHOT.isoformat()

    def test_search_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Disabled adapter refuses to call the network."""
        monkeypatch.setenv("CAREERSATGOV_ENABLED", "0")
        scraper = CareersAtGovScraper(rate_limit=0)
        with pytest.raises(ScrapingException, match="disabled"):
            scraper.search(SearchParams(keywords=["software"]))

    def test_search_skips_non_singapore_location(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US/UK searches do not download the dump."""
        monkeypatch.setenv("CAREERSATGOV_ENABLED", "true")
        scraper = CareersAtGovScraper(rate_limit=0)
        with patch.object(scraper, "_fetch_dump") as fetch:
            collection = scraper.search(
                SearchParams(keywords=["AI", "Engineer"], location="New York")
            )
        fetch.assert_not_called()
        assert collection.listings == []
        assert collection.metadata.get("skipped") is True

    def test_max_results_constant(self) -> None:
        """Ingest cap stays conservative for a bulk dump."""
        assert MAX_RESULTS <= 60

    def test_http_error_becomes_scraping_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HTTP failures surface as ScrapingException."""
        monkeypatch.setenv("CAREERSATGOV_ENABLED", "true")
        scraper = CareersAtGovScraper(rate_limit=0)
        with patch.object(
            scraper,
            "_fetch_dump",
            side_effect=ScrapingException("Careers@Gov dump returned HTTP 429"),
        ):
            with pytest.raises(ScrapingException, match="429"):
                scraper.search(SearchParams(keywords=["software"]))


class TestManagerRegistration:
    """ScraperManager registers Careers@Gov only when enabled."""

    def test_registered_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Enabled env includes careersatgov in scrapers map."""
        monkeypatch.setenv("CAREERSATGOV_ENABLED", "true")
        from src.scrapers.manager import ScraperManager

        manager = ScraperManager(output_dir=str(tmp_path))
        assert JobSource.CAREERSATGOV in manager.scrapers

    def test_omitted_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Default-off kill switch removes Careers@Gov from available sources."""
        monkeypatch.delenv("CAREERSATGOV_ENABLED", raising=False)
        from src.scrapers.manager import ScraperManager

        manager = ScraperManager(output_dir=str(tmp_path))
        assert JobSource.CAREERSATGOV not in manager.scrapers
        assert JobSource.LINKEDIN in manager.scrapers
        assert JobSource.JSEARCH in manager.scrapers
