"""
Unit tests for GET /api/jobs/{id}/company-site (company-site-apply, S1).

The company site search is replaced with a fake, so no network is used.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.models.job_listing import JobListing, JobSource
from src.scrapers.storage import JobListingStorage


@pytest.fixture
def listing_storage(tmp_path: Path) -> JobListingStorage:
    """
    Catalog rooted in a temp directory.

    Args:
        tmp_path: Pytest temp directory.

    Returns:
        A storage object with one stored listing.
    """
    storage = JobListingStorage(str(tmp_path / "listings"))
    storage.upsert_listings(
        [
            JobListing(
                job_id="job-cs-1",
                title="Graduate Machine Learning Engineer",
                company="Lumen Analytics Pte. Ltd.",
                location="Singapore",
                source=JobSource.MYCAREERSFUTURE,
                source_url="https://www.mycareersfuture.gov.sg/job/it/x",
            )
        ]
    )
    return storage


@pytest.fixture
def client(listing_storage: JobListingStorage):
    """
    FastAPI client with the temp catalog.

    Args:
        listing_storage: Temp catalog fixture.

    Yields:
        A TestClient with API auth disabled.
    """
    with patch(
        "src.api.routes.jobs._listing_storage",
        lambda: listing_storage,
    ):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        yield TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides.clear()


def test_unknown_job_is_404(client: TestClient) -> None:
    """An unknown job ID gives 404.

    Args:
        client: API test client.
    """
    response = client.get("/api/jobs/no-such-job/company-site")
    assert response.status_code == 404


def test_disabled_setting_skips_search(client: TestClient) -> None:
    """With the setting off, no search runs and the level is disabled.

    Args:
        client: API test client.
    """
    search = Mock(side_effect=AssertionError("search must not run"))
    with patch("src.api.routes.jobs._company_site_enabled", return_value=False), patch(
        "src.api.routes.jobs.get_company_site", search
    ):
        response = client.get("/api/jobs/job-cs-1/company-site")
    assert response.status_code == 200
    assert response.json()["level"] == "disabled"
    search.assert_not_called()


def test_enabled_returns_result_and_passes_refresh(client: TestClient) -> None:
    """With the setting on, the route returns the result and passes refresh on.

    Args:
        client: API test client.
    """
    payload = {
        "level": "exact",
        "url": "https://boards.greenhouse.io/lumenanalytics/jobs/4012345",
        "page_title": "Job Application",
        "evidence": ["page names the company"],
        "checked_at": "2026-11-20T10:00:00+00:00",
        "query": "Lumen Analytics",
        "cached": False,
    }
    search = Mock(return_value=payload)
    with patch("src.api.routes.jobs._company_site_enabled", return_value=True), patch(
        "src.api.routes.jobs.get_company_site", search
    ):
        response = client.get("/api/jobs/job-cs-1/company-site?refresh=true")
    assert response.status_code == 200
    assert response.json() == payload
    assert search.call_args.kwargs["refresh"] is True
    assert search.call_args.args[0] == "job-cs-1"
    assert search.call_args.args[1] == "Lumen Analytics Pte. Ltd."
    assert search.call_args.args[2] == "Graduate Machine Learning Engineer"
