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
    with_jd = JobListing(
        job_id="catalog-jd-job",
        title="AI Engineer",
        company="Acme",
        source=JobSource.LINKEDIN,
        description=(
            "We need a junior AI engineer to evaluate models, write Python "
            "services, and document findings for consulting teams each week."
        ),
        source_url="https://example.com/catalog-jd",
        last_seen_at=now,
        scraped_at=now,
    )
    catalog = {stale.job_id: stale, with_jd.job_id: with_jd}
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
        assert by_id["ext-1"]["current_status"] == "applied_elsewhere"
        assert data["summary"]["expired"] == 1
        assert data["summary"]["external"] >= 1

    def test_dashboard_includes_hashed_applied_elsewhere(
        self, client: TestClient
    ) -> None:
        """Long unsafe ids persist as id_*.json and still appear on All / External."""
        long_id = "b29x" + "A" * 400 + ":colon"
        resp = client.post(
            "/api/applications/external",
            json={
                "job_id": long_id,
                "job_title": "AI Engineer",
                "company": "Acme",
                "application_method": "External site",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "applied_elsewhere"

        included = client.get(
            "/api/applications/dashboard",
            params={"include_hidden": False, "include_external": True},
        )
        assert included.status_code == 200
        included_data = included.json()
        by_id = {row["application_id"]: row for row in included_data["applications"]}
        assert long_id in by_id
        assert by_id[long_id]["current_status"] == "applied_elsewhere"
        assert included_data["summary"]["external"] >= 1

        excluded = client.get(
            "/api/applications/dashboard",
            params={"include_external": False},
        )
        assert excluded.status_code == 200
        excluded_ids = {
            row["application_id"] for row in excluded.json()["applications"]
        }
        assert long_id not in excluded_ids

    def test_untrack_deletes_hashed_file_and_dashboard_row(
        self, client: TestClient, tracker: OutcomeTracker
    ) -> None:
        """Untrack removes hashed files and drops the row from the dashboard."""
        from src.metrics.outcome_tracker import application_filename_stem

        long_id = "b29x" + "C" * 400 + ":colon"
        created = client.post(
            "/api/applications/external",
            json={
                "job_id": long_id,
                "job_title": "AI Engineer",
                "company": "Acme",
                "application_method": "External site",
            },
        )
        assert created.status_code == 200
        path = tracker.storage_dir / f"{application_filename_stem(long_id)}.json"
        assert path.exists()

        deleted = client.post(
            "/api/applications/actions",
            json={"job_id": long_id, "action": "untrack"},
        )
        assert deleted.status_code == 200
        assert deleted.json()["action"] == "untrack"
        assert not path.exists()

        dash = client.get(
            "/api/applications/dashboard",
            params={"include_hidden": False, "include_external": True},
        )
        assert dash.status_code == 200
        ids = {row["application_id"] for row in dash.json()["applications"]}
        assert long_id not in ids

        missing = client.post(
            "/api/applications/actions",
            json={"job_id": long_id, "action": "untrack"},
        )
        assert missing.status_code == 404

    def test_track_external_stores_listing_description(
        self, client: TestClient
    ) -> None:
        """Jobs-originated apply-elsewhere must persist a supplied job description."""
        description = (
            "We are hiring a junior AI engineer to build evaluation pipelines, "
            "write Python services, and support consulting delivery."
        )
        created = client.post(
            "/api/applications/external",
            json={
                "job_id": "jd-from-jobs",
                "job_title": "Junior AI Engineer",
                "company": "Acme",
                "application_method": "External site",
                "metadata": {
                    "description": description,
                    "source_url": "https://ex.com/j",
                },
            },
        )
        assert created.status_code == 200
        assert created.json()["status"] == "applied_elsewhere"

        detail = client.get("/api/applications/jd-from-jobs")
        assert detail.status_code == 200
        data = detail.json()
        stored = str(data["metadata"].get("description", ""))
        assert len(stored) >= 50
        assert "evaluation pipelines" in stored
        assert data["source_url"] == "https://ex.com/j"

        dash = client.get("/api/applications/dashboard")
        assert dash.status_code == 200
        by_id = {row["application_id"]: row for row in dash.json()["applications"]}
        assert by_id["jd-from-jobs"]["has_job_description"] is True
        assert by_id["jd-from-jobs"]["source_url"] == "https://ex.com/j"

    def test_track_external_optional_listing_url_is_cleaned(
        self, client: TestClient
    ) -> None:
        """Optional listing URL is stored cleaned; empty and unsafe values are dropped."""
        created = client.post(
            "/api/applications/external",
            json={
                "job_id": "ext-url-1",
                "job_title": "Engineer",
                "company": "Acme",
                "application_method": "External site",
                "metadata": {"source_url": "example.com/jobs/1"},
            },
        )
        assert created.status_code == 200
        detail = client.get("/api/applications/ext-url-1")
        assert detail.status_code == 200
        assert detail.json()["source_url"] == "https://example.com/jobs/1"

        no_url = client.post(
            "/api/applications/external",
            json={
                "job_id": "ext-url-2",
                "job_title": "Engineer",
                "company": "Acme",
                "application_method": "External site",
                "metadata": {"source_url": "  "},
            },
        )
        assert no_url.status_code == 200
        empty_detail = client.get("/api/applications/ext-url-2")
        assert empty_detail.status_code == 200
        assert empty_detail.json()["source_url"] is None

        unsafe = client.post(
            "/api/applications/external",
            json={
                "job_id": "ext-url-3",
                "job_title": "Engineer",
                "company": "Acme",
                "application_method": "External site",
                "metadata": {"source_url": "javascript:alert(1)"},
            },
        )
        assert unsafe.status_code == 200
        unsafe_detail = client.get("/api/applications/ext-url-3")
        assert unsafe_detail.status_code == 200
        assert unsafe_detail.json()["source_url"] is None

    def test_dashboard_falls_back_to_catalog_listing_url(
        self, client: TestClient, tracker: OutcomeTracker
    ) -> None:
        """Cards can show a catalog URL when metadata has none."""
        tracker.track_external_application(
            "catalog-jd-job",
            "AI Engineer",
            "Acme",
            application_method="External site",
        )
        dash = client.get("/api/applications/dashboard")
        assert dash.status_code == 200
        by_id = {row["application_id"]: row for row in dash.json()["applications"]}
        assert by_id["catalog-jd-job"]["source_url"] == "https://example.com/catalog-jd"

    def test_applied_elsewhere_advances_to_interview_and_keeps_jd(
        self, client: TestClient
    ) -> None:
        """Applied-elsewhere can use the same screening_scheduled interview path."""
        description = (
            "Own model evaluation, prompt tests, and reporting for client AI "
            "engagements. Python and SQL are required every week."
        )
        client.post(
            "/api/applications/external",
            json={
                "job_id": "ext-interview-1",
                "job_title": "AI Engineer",
                "company": "Acme",
                "application_method": "External site",
                "metadata": {"description": description},
            },
        )
        updated = client.put(
            "/api/applications/status",
            json={
                "job_id": "ext-interview-1",
                "status": "screening_scheduled",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["new_status"] == "screening_scheduled"

        detail = client.get("/api/applications/ext-interview-1")
        assert detail.status_code == 200
        data = detail.json()
        assert data["current_status"] == "screening_scheduled"
        assert len(str(data["metadata"].get("description", ""))) >= 50

    def test_track_external_backfills_catalog_description(
        self, client: TestClient
    ) -> None:
        """When Jobs sends no JD, persist the catalog listing description."""
        created = client.post(
            "/api/applications/external",
            json={
                "job_id": "catalog-jd-job",
                "job_title": "AI Engineer",
                "company": "Acme",
                "application_method": "External site",
            },
        )
        assert created.status_code == 200
        detail = client.get("/api/applications/catalog-jd-job")
        assert detail.status_code == 200
        stored = str(detail.json()["metadata"].get("description", ""))
        assert len(stored) >= 50
        assert "evaluate models" in stored
        assert detail.json()["source_url"] == "https://example.com/catalog-jd"

    def test_detail_backfills_catalog_description(
        self, client: TestClient, tracker: OutcomeTracker
    ) -> None:
        """GET detail copies a catalog JD onto a row that was stored without one."""
        tracker.track_external_application(
            "catalog-jd-job",
            "AI Engineer",
            "Acme",
            application_method="External site",
        )
        stored = tracker.get_application("catalog-jd-job")
        assert stored is not None
        assert not (stored.metadata or {}).get("description")

        dash = client.get("/api/applications/dashboard")
        assert dash.status_code == 200
        by_id = {row["application_id"]: row for row in dash.json()["applications"]}
        assert by_id["catalog-jd-job"]["has_job_description"] is True

        detail = client.get("/api/applications/catalog-jd-job")
        assert detail.status_code == 200
        assert len(str(detail.json()["metadata"].get("description", ""))) >= 50
        reloaded = tracker.get_application("catalog-jd-job")
        assert reloaded is not None
        assert len(str((reloaded.metadata or {}).get("description", ""))) >= 50

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
