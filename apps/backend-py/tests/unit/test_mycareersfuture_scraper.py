"""
Unit tests for MyCareersFuture public JSON adapter.

Author: Job Raider
Date: 2026-08-14
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.models.job_listing import ExperienceLevel, JobSource, JobType, WorkMode
from src.scrapers.base import ScrapingException, SearchParams
from src.scrapers.mycareersfuture_scraper import (
    MAX_RESULTS,
    MyCareersFutureScraper,
    mcf_enabled,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "mycareersfuture"
    / "search_page.json"
)


def _fixture() -> Dict[str, Any]:
    """Load the capped MCF search fixture."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class TestMcfEnabled:
    """Kill switch via MCF_ENABLED."""

    def test_default_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing env defaults to enabled."""
        monkeypatch.delenv("MCF_ENABLED", raising=False)
        assert mcf_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off"])
    def test_falsey_disables(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        """Common falsey strings disable the adapter."""
        monkeypatch.setenv("MCF_ENABLED", value)
        assert mcf_enabled() is False


class TestParseJob:
    """JSON fixture maps to JobListing fields used by catalog lifecycle."""

    def test_maps_core_fields_and_deadline(self) -> None:
        """Title, company, salary, skills, dates, and stable job_id map."""
        scraper = MyCareersFutureScraper(rate_limit=0)
        raw = _fixture()["results"][0]
        job = scraper._parse_job(raw)

        assert job.job_id == "mcf-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert job.source == JobSource.MYCAREERSFUTURE.value
        assert job.title == "Software Engineer"
        assert job.company == "Example Pte Ltd"
        assert job.location == "Central"
        assert job.work_mode == WorkMode.HYBRID.value
        assert job.job_type == JobType.FULL_TIME.value
        assert job.experience_level == ExperienceLevel.MID.value
        assert job.salary_range is not None
        assert job.salary_range.min_amount == 5000
        assert job.salary_range.max_amount == 8000
        assert job.salary_range.currency == "SGD"
        assert job.salary_range.period == "monthly"
        assert [s.name for s in job.skills] == ["Python", "Docker"]
        assert job.skills[0].is_required is True
        assert job.application_deadline is not None
        assert job.application_deadline.isoformat().startswith("2026-09-01")
        assert job.posted_date is not None
        assert "mycareersfuture.gov.sg" in str(job.source_url or "")
        assert job.metadata["mcf_uuid"] == raw["uuid"]

    def test_missing_uuid_raises(self) -> None:
        """Rows without uuid are rejected."""
        scraper = MyCareersFutureScraper(rate_limit=0)
        with pytest.raises(ValueError, match="uuid"):
            scraper._parse_job({"title": "No Id"})

    def test_builds_public_url_when_metadata_missing(self) -> None:
        """Fallback URL uses public MCF job path + uuid."""
        scraper = MyCareersFutureScraper(rate_limit=0)
        job = scraper._parse_job(
            {
                "uuid": "zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
                "title": "Data Analyst!",
                "postedCompany": {"name": "Acme"},
                "metadata": {},
            }
        )
        assert str(job.source_url).endswith(
            "/job/data-analyst/zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz"
        )
        assert job.job_type == JobType.FULL_TIME.value
        assert job.experience_level == ExperienceLevel.NOT_SPECIFIED.value


class TestSearchCaps:
    """Hard page/result caps and HTTP error paths."""

    def test_search_uses_fixture_and_respects_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Search maps fixture rows and never exceeds request limit."""
        monkeypatch.setenv("MCF_ENABLED", "true")
        scraper = MyCareersFutureScraper(rate_limit=0)
        payload = _fixture()

        with patch.object(scraper, "_fetch_page", return_value=payload) as fetch:
            collection = scraper.search(SearchParams(keywords=["software"], limit=1))

        assert len(collection.listings) == 1
        assert collection.listings[0].source == JobSource.MYCAREERSFUTURE.value
        fetch.assert_called()
        assert collection.metadata["pages_fetched"] == 1

    def test_search_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Disabled adapter refuses to call the network."""
        monkeypatch.setenv("MCF_ENABLED", "0")
        scraper = MyCareersFutureScraper(rate_limit=0)
        with pytest.raises(ScrapingException, match="disabled"):
            scraper.search(SearchParams(keywords=["software"]))

    def test_max_results_constant(self) -> None:
        """Hard cap stays conservative for personal-use tooling."""
        assert MAX_RESULTS <= 60

    def test_http_error_becomes_scraping_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HTTP failures surface as ScrapingException."""
        monkeypatch.setenv("MCF_ENABLED", "true")
        scraper = MyCareersFutureScraper(rate_limit=0)
        response = MagicMock()
        response.raise_for_status.side_effect = Exception("boom")
        # Simulate requests HTTPError path via _fetch_page raising ScrapingException
        with patch.object(
            scraper,
            "_fetch_page",
            side_effect=ScrapingException("MyCareersFuture API returned HTTP 429"),
        ):
            with pytest.raises(ScrapingException, match="429"):
                scraper.search(SearchParams(keywords=["software"]))


class TestManagerRegistration:
    """ScraperManager registers MCF only when enabled."""

    def test_registered_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Enabled env includes mycareersfuture in scrapers map."""
        monkeypatch.setenv("MCF_ENABLED", "true")
        from src.scrapers.manager import ScraperManager

        manager = ScraperManager(output_dir=str(tmp_path))
        assert JobSource.MYCAREERSFUTURE in manager.scrapers

    def test_omitted_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Kill switch removes MCF from available sources."""
        monkeypatch.setenv("MCF_ENABLED", "0")
        from src.scrapers.manager import ScraperManager

        manager = ScraperManager(output_dir=str(tmp_path))
        assert JobSource.MYCAREERSFUTURE not in manager.scrapers
        assert JobSource.LINKEDIN in manager.scrapers
        assert JobSource.JSEARCH in manager.scrapers
