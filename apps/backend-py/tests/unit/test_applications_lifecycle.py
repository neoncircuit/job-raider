"""
Unit tests for application dashboard listing_status joins.

Author: Job Raider
Date: 2026-08-14
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.metrics.outcome_tracker import OutcomeTracker
from src.models.job_listing import JobListing, JobSource


@pytest.fixture
def tracker(tmp_path: Path) -> OutcomeTracker:
    """Outcome tracker rooted in a temp directory."""
    return OutcomeTracker(str(tmp_path / "applications"))


@pytest.fixture
def client(tracker: OutcomeTracker):
    """FastAPI client with an isolated tracker and a stale catalog row."""
    now = datetime.now()
    stale = JobListing(
        job_id="stale-job",
        title="Engineer",
        company="Acme",
        source=JobSource.LINKEDIN,
        last_seen_at=now - timedelta(days=40),
        scraped_at=now - timedelta(days=40),
    )
    catalog = {stale.job_id: stale}
    with patch(
        "src.api.routes.applications.outcome_tracker",
        tracker,
    ), patch(
        "src.api.routes.applications._listing_catalog",
        lambda: catalog,
    ):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


class TestApplicationsExpiredJoin:
    """Dashboard and detail expose catalog listing_status."""

    def test_dashboard_marks_stale_catalog_job_expired(
        self, client: TestClient
    ) -> None:
        """A saved job whose catalog last-seen is 40 days old is expired."""
        client.post(
            "/api/applications/actions",
            json={
                "job_id": "stale-job",
                "action": "save",
                "metadata": {
                    "title": "Engineer",
                    "company": "Acme",
                    "source_url": "https://example.com/stale",
                },
            },
        )
        client.post(
            "/api/applications/external",
            json={
                "job_id": "ext-1",
                "job_title": "Developer",
                "company": "Startup",
            },
        )

        resp = client.get("/api/applications/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        by_id = {row["application_id"]: row for row in data["applications"]}
        assert by_id["stale-job"]["listing_status"] == "expired"
        assert by_id["stale-job"]["source_url"] == "https://example.com/stale"
        assert by_id["ext-1"]["listing_status"] is None
        assert data["summary"]["expired"] == 1

    def test_detail_includes_listing_status(self, client: TestClient) -> None:
        """GET application detail joins the same catalog status."""
        client.post(
            "/api/applications/actions",
            json={
                "job_id": "stale-job",
                "action": "save",
                "metadata": {"title": "Engineer", "company": "Acme"},
            },
        )
        resp = client.get("/api/applications/stale-job")
        assert resp.status_code == 200
        assert resp.json()["listing_status"] == "expired"
