"""
Unit tests for GET /api/jobs/{id} and POST /api/jobs/{id}/score.

Author: Job Raider
Date: 2026-08-13
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.models.job_listing import JobListing, JobSource
from src.models.user_profile import UserProfile
from src.scrapers.storage import JobListingStorage


@pytest.fixture
def listing_storage(tmp_path: Path) -> JobListingStorage:
    """Catalog rooted in a temp directory."""
    return JobListingStorage(str(tmp_path / "listings"))


@pytest.fixture
def client(listing_storage, sample_user_profile: UserProfile):
    """FastAPI client with catalog and an active profile."""
    stored = {
        "profile-1": {
            "profile": sample_user_profile,
            "created_at": datetime.now(),
        }
    }
    with patch(
        "src.api.routes.jobs._listing_storage",
        lambda: listing_storage,
    ), patch(
        "src.api.routes.jobs.profile_state.stored_profiles",
        stored,
        create=True,
    ), patch(
        "src.api.routes.jobs.profile_state.active_profile_id",
        "profile-1",
        create=True,
    ):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


def _sample_job() -> JobListing:
    """Minimal listing stored in the catalog for route tests."""
    return JobListing(
        job_id="job-42",
        title="Backend Engineer",
        company="Acme",
        location="Singapore",
        description="Build APIs in Python.",
        source=JobSource.LINKEDIN,
        source_url="https://www.linkedin.com/jobs/view/42",
    )


class TestGetJob:
    """GET /api/jobs/{job_id} reads the listing catalog."""

    def test_missing_returns_404(self, client: TestClient) -> None:
        """Unknown IDs return 404 instead of 501."""
        resp = client.get("/api/jobs/missing")
        assert resp.status_code == 404

    def test_returns_stored_listing(
        self, client: TestClient, listing_storage: JobListingStorage
    ) -> None:
        """A catalog hit returns serialized lifecycle fields."""
        listing_storage.upsert_listings([_sample_job()])
        resp = client.get("/api/jobs/job-42")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "job-42"
        assert body["title"] == "Backend Engineer"
        assert body["listing_status"] == "active"
        assert body["scraped_today"] is True


class TestScoreJob:
    """POST /api/jobs/{job_id}/score scores a catalog listing."""

    def test_missing_profile_returns_400(
        self, listing_storage: JobListingStorage
    ) -> None:
        """Scoring requires an active profile."""
        listing_storage.upsert_listings([_sample_job()])
        with patch(
            "src.api.routes.jobs._listing_storage",
            lambda: listing_storage,
        ), patch(
            "src.api.routes.jobs.profile_state.active_profile_id",
            None,
            create=True,
        ):
            from src.api.auth import verify_api_key
            from src.api.main import app

            app.dependency_overrides[verify_api_key] = lambda: None
            tc = TestClient(app, raise_server_exceptions=False)
            resp = tc.post("/api/jobs/job-42/score")
            app.dependency_overrides.clear()
        assert resp.status_code == 400

    def test_scores_catalog_listing(
        self, client: TestClient, listing_storage: JobListingStorage
    ) -> None:
        """A stored listing returns total_score plus Jobs payload fields."""
        listing_storage.upsert_listings([_sample_job()])
        resp = client.post("/api/jobs/job-42/score")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_score" in body
        assert body["job_id"] == "job-42"
        assert body["listing_status"] == "active"
