"""
Unit tests for tracking an application made on the company site (S3).

Rule R3: a job applied on the company site shows as applied on its portal
copy, and the next pipeline run skips it through AppliedGuard. The tests use
temp storage only; nothing is written to data/.
"""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.metrics.outcome_tracker import OutcomeTracker
from src.models.job_listing import JobListing, JobSource
from src.submission.applied_guard import AppliedGuard
from src.submission.applied_tracker import AppliedJobsTracker

PORTAL_URL = "https://www.mycareersfuture.gov.sg/job/it/graduate-ml-lumen-1"
COMPANY_URL = "https://boards.greenhouse.io/lumenanalytics/jobs/4012345"


@pytest.fixture
def tracker(tmp_path: Path) -> OutcomeTracker:
    """
    Outcome tracker rooted in a temp directory.

    Args:
        tmp_path: Pytest temp directory.

    Returns:
        An OutcomeTracker with no records.
    """
    return OutcomeTracker(str(tmp_path / "applications"))


@pytest.fixture
def applied(tmp_path: Path) -> AppliedJobsTracker:
    """
    Applied-jobs tracker rooted in a temp directory.

    Args:
        tmp_path: Pytest temp directory.

    Returns:
        An AppliedJobsTracker with no records.
    """
    return AppliedJobsTracker(str(tmp_path / "applied_jobs"))


@pytest.fixture
def client(tracker: OutcomeTracker, applied: AppliedJobsTracker):
    """
    FastAPI client that writes to the temp trackers only.

    Args:
        tracker: Temp outcome tracker.
        applied: Temp applied-jobs tracker.

    Yields:
        A TestClient with API auth disabled.
    """
    with patch("src.api.routes.applications.outcome_tracker", tracker), patch(
        "src.api.routes.applications.AppliedJobsTracker",
        lambda: applied,
    ), patch("src.api.routes.applications._listing_catalog", lambda: {}):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        yield TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides.clear()


def _track_company_site(client: TestClient) -> Dict[str, Any]:
    """
    Send the tracking request the job detail action sends.

    Args:
        client: API test client.

    Returns:
        The JSON response of POST /api/applications/external.
    """
    response = client.post(
        "/api/applications/external",
        json={
            "job_id": "mcf-lumen-1",
            "job_title": "Graduate Machine Learning Engineer",
            "company": "Lumen Analytics Pte. Ltd.",
            "application_method": "Company site",
            "metadata": {
                "company_site_url": COMPANY_URL,
                "company_site_level": "exact",
            },
        },
    )
    assert response.status_code == 200
    return response.json()


def _portal_listing() -> JobListing:
    """
    The portal copy of the same job, as the scraper stores it.

    Returns:
        A MyCareersFuture listing with the same job ID.
    """
    return JobListing(
        job_id="mcf-lumen-1",
        title="Graduate Machine Learning Engineer",
        company="Lumen Analytics Pte. Ltd.",
        source=JobSource.MYCAREERSFUTURE,
        source_url=PORTAL_URL,
    )


def test_company_site_application_keeps_method_and_url(
    client: TestClient,
    tracker: OutcomeTracker,
) -> None:
    """The record keeps the method "Company site" and the company URL.

    Args:
        client: API test client.
        tracker: Temp outcome tracker.
    """
    _track_company_site(client)
    detail = client.get("/api/applications/mcf-lumen-1")
    assert detail.status_code == 200
    assert detail.json()["external_application_details"]["application_method"] == (
        "Company site"
    )
    (row,) = [
        o for o in tracker.get_all_applications() if o.application_id == "mcf-lumen-1"
    ]
    assert row.metadata["company_site_url"] == COMPANY_URL


def test_portal_copy_shows_applied_after_company_site_action(
    client: TestClient,
    tracker: OutcomeTracker,
    applied: AppliedJobsTracker,
) -> None:
    """Rule R3: the portal copy of the same job is marked as already applied.

    Args:
        client: API test client.
        tracker: Temp outcome tracker.
        applied: Temp applied-jobs tracker.
    """
    _track_company_site(client)
    guard = AppliedGuard(outcome_tracker=tracker, applied_tracker=applied)
    annotated = guard.annotate_listings([_portal_listing()])
    assert annotated[0].already_applied is True


def test_next_pipeline_run_skips_the_job(
    client: TestClient,
    tracker: OutcomeTracker,
    applied: AppliedJobsTracker,
) -> None:
    """Rule R3: the pipeline filter removes the portal copy of the job.

    The pipeline (stages_collect) annotates the listings and then filters them
    with AppliedGuard. This test follows the same two calls.

    Args:
        client: API test client.
        tracker: Temp outcome tracker.
        applied: Temp applied-jobs tracker.
    """
    _track_company_site(client)
    guard = AppliedGuard(outcome_tracker=tracker, applied_tracker=applied)
    kept, removed = guard.filter_unapplied(guard.annotate_listings([_portal_listing()]))
    assert kept == []
    assert removed == 1
