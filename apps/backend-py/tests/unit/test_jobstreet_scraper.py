"""
Unit tests for JobStreet Singapore public JSON adapter.

Author: Job Raider
Date: 2026-08-15
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from src.models.job_listing import JobSource, JobType, WorkMode
from src.scrapers.base import ScrapingException, SearchParams
from src.scrapers.jobstreet_scraper import (
    MAX_RESULTS,
    JobStreetScraper,
    jobstreet_enabled,
)
from src.utils.source_geography import listing_matches_requested_locations

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "jobstreet" / "search_page.json"
)


def _fixture() -> Dict[str, Any]:
    """Load the capped JobStreet search fixture."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class TestJobstreetEnabled:
    """Kill switch via JOBSTREET_ENABLED."""

    def test_default_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing env defaults to enabled."""
        monkeypatch.delenv("JOBSTREET_ENABLED", raising=False)
        assert jobstreet_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off"])
    def test_falsey_disables(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        """Common falsey strings disable the adapter."""
        monkeypatch.setenv("JOBSTREET_ENABLED", value)
        assert jobstreet_enabled() is False


class TestParseJob:
    """JSON fixture maps to JobListing fields used by catalog lifecycle."""

    def test_maps_core_fields_and_salary(self) -> None:
        """Title, company, salary, location, and stable job_id map."""
        scraper = JobStreetScraper(rate_limit=0)
        raw = _fixture()["data"][0]
        job = scraper._parse_job(raw)

        assert job is not None
        assert job.job_id == "js-93962024"
        assert job.source == JobSource.JOBSTREET.value
        assert job.title == "Software Engineer"
        assert job.company == "AlwaysHired"
        assert job.location == "Kallang, Central Region, Singapore"
        assert job.work_mode == WorkMode.ON_SITE.value
        assert job.job_type == JobType.FULL_TIME.value
        assert job.salary_range is not None
        assert job.salary_range.min_amount == 3500
        assert job.salary_range.max_amount == 4000
        assert job.salary_range.currency == "SGD"
        assert job.salary_range.period == "monthly"
        assert job.posted_date is not None
        assert "jobstreet.com.sg" in str(job.source_url or "")
        assert job.metadata["jobstreet_id"] == "93962024"
        assert job.description is not None
        assert "Up to $4K" in job.description
        assert "Develop scalable cloud applications" in job.description

    def test_intern_title_maps_job_type(self) -> None:
        """Internship in the title maps to internship even when type is full time."""
        scraper = JobStreetScraper(rate_limit=0)
        job = scraper._parse_job(_fixture()["data"][1])
        assert job is not None
        assert job.job_type == JobType.INTERNSHIP.value
        assert job.work_mode == WorkMode.HYBRID.value
        assert listing_matches_requested_locations(job, ["Singapore"])
        assert listing_matches_requested_locations(job, ["SG"])

    def test_drops_non_singapore_country(self) -> None:
        """Australian cards from the wrong host must not be stored as JobStreet SG."""
        scraper = JobStreetScraper(rate_limit=0)
        assert scraper._parse_job(_fixture()["data"][2]) is None

    def test_missing_id_raises(self) -> None:
        """Rows without id are rejected."""
        scraper = JobStreetScraper(rate_limit=0)
        with pytest.raises(ValueError, match="id"):
            scraper._parse_job({"title": "No Id"})

    def test_district_matches_singapore_filter(self) -> None:
        """JobStreet district names survive the default Singapore post-filter."""
        scraper = JobStreetScraper(rate_limit=0)
        job = scraper._parse_job(_fixture()["data"][0])
        assert job is not None
        assert listing_matches_requested_locations(job, ["Singapore"])
        assert listing_matches_requested_locations(job, ["Remote"]) is False
        assert not listing_matches_requested_locations(job, ["New York"])


class TestSearchCaps:
    """Hard page/result caps and HTTP error paths."""

    def test_search_uses_fixture_and_drops_overseas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Search maps SG rows, drops AU, and never exceeds request limit."""
        monkeypatch.setenv("JOBSTREET_ENABLED", "true")
        scraper = JobStreetScraper(rate_limit=0)
        payload = _fixture()

        with patch.object(scraper, "_fetch_page", return_value=payload) as fetch:
            collection = scraper.search(SearchParams(keywords=["software"], limit=10))

        assert [job.job_id for job in collection.listings] == [
            "js-93962024",
            "js-11111111",
        ]
        assert collection.listings[0].source == JobSource.JOBSTREET.value
        fetch.assert_called()
        assert collection.metadata["pages_fetched"] == 1

    def test_search_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Disabled adapter refuses to call the network."""
        monkeypatch.setenv("JOBSTREET_ENABLED", "0")
        scraper = JobStreetScraper(rate_limit=0)
        with pytest.raises(ScrapingException, match="disabled"):
            scraper.search(SearchParams(keywords=["software"]))

    def test_search_skips_non_singapore_location(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US/UK searches do not call the JobStreet API."""
        monkeypatch.setenv("JOBSTREET_ENABLED", "true")
        scraper = JobStreetScraper(rate_limit=0)
        with patch.object(scraper, "_fetch_page") as fetch:
            collection = scraper.search(
                SearchParams(keywords=["AI", "Engineer"], location="New York")
            )
        fetch.assert_not_called()
        assert collection.listings == []
        assert collection.metadata.get("skipped") is True

    def test_max_results_constant(self) -> None:
        """Hard cap stays conservative for personal-use tooling."""
        assert MAX_RESULTS <= 60

    def test_http_error_becomes_scraping_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HTTP failures surface as ScrapingException."""
        monkeypatch.setenv("JOBSTREET_ENABLED", "true")
        scraper = JobStreetScraper(rate_limit=0)
        with patch.object(
            scraper,
            "_fetch_page",
            side_effect=ScrapingException("JobStreet API returned HTTP 429"),
        ):
            with pytest.raises(ScrapingException, match="429"):
                scraper.search(SearchParams(keywords=["software"]))


class TestManagerRegistration:
    """ScraperManager registers JobStreet only when enabled."""

    def test_registered_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Enabled env includes jobstreet in scrapers map."""
        monkeypatch.setenv("JOBSTREET_ENABLED", "true")
        from src.scrapers.manager import ScraperManager

        manager = ScraperManager(output_dir=str(tmp_path))
        assert JobSource.JOBSTREET in manager.scrapers

    def test_omitted_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Kill switch removes JobStreet from available sources."""
        monkeypatch.setenv("JOBSTREET_ENABLED", "0")
        from src.scrapers.manager import ScraperManager

        manager = ScraperManager(output_dir=str(tmp_path))
        assert JobSource.JOBSTREET not in manager.scrapers
        assert JobSource.LINKEDIN in manager.scrapers
        assert JobSource.JSEARCH in manager.scrapers
