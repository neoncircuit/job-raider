"""
Integration tests for application tracking API.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.mark.integration
class TestApplicationAPI:
    """Tests for application tracking API endpoints."""

    def test_perform_save_action(self, client):
        """Test saving a job via API."""
        response = client.post(
            "/api/applications/actions",
            json={
                "job_id": "test_job_1",
                "action": "save",
                "metadata": {
                    "title": "Software Engineer",
                    "company": "Tech Corp",
                    "source_url": "https://example.com/job",
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "save"
        assert data["new_status"] == "saved_bookmarked"
        assert data["message"] == "Job saved successfully"

    def test_perform_hide_action(self, client):
        """Test hiding a job via API."""
        # First create an application
        client.post("/api/applications/external", json={
            "job_id": "test_hide_1",
            "job_title": "Developer",
            "company": "Test Company",
        })

        # Then hide it
        response = client.post(
            "/api/applications/actions",
            json={
                "job_id": "test_hide_1",
                "action": "hide",
                "note": "Not interested in this role",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "hide"
        assert data["new_status"] == "not_interested"

    def test_track_external_application(self, client):
        """Test tracking external application via API."""
        response = client.post(
            "/api/applications/external",
            json={
                "job_id": "ext_app_1",
                "job_title": "Developer",
                "company": "Startup",
                "application_method": "referral",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "applied_elsewhere"
        assert data["message"] == "External application tracked successfully"

    def test_create_custom_status(self, client):
        """Test creating custom status via API."""
        response = client.post(
            "/api/applications/statuses/custom",
            json={
                "name": "Waiting for Response",
                "description": "Applied and waiting",
                "color": "#FFA500",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Waiting for Response"
        assert data["color"] == "#FFA500"
        assert "status_id" in data
        assert data["is_active"] is True

    def test_get_custom_statuses(self, client):
        """Test getting all custom statuses via API."""
        # Use unique names to avoid conflicts with other tests
        import time
        suffix = str(int(time.time()))

        # Create a few custom statuses
        client.post("/api/applications/statuses/custom", json={
            "name": f"Status 1 {suffix}",
            "description": "First status",
        })
        client.post("/api/applications/statuses/custom", json={
            "name": f"Status 2 {suffix}",
            "description": "Second status",
        })

        response = client.get("/api/applications/statuses/custom")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # At least our 2 statuses
        assert any(s["name"] == f"Status 1 {suffix}" for s in data)
        assert any(s["name"] == f"Status 2 {suffix}" for s in data)

    def test_set_custom_status_on_application(self, client):
        """Test setting custom status on application via API."""
        # Create an external application
        client.post("/api/applications/external", json={
            "job_id": "custom_status_test",
            "job_title": "Engineer",
            "company": "Company",
        })

        # Create a custom status
        status_response = client.post("/api/applications/statuses/custom", json={
            "name": "Interviewing",
            "description": "In interview process",
        })
        status_id = status_response.json()["status_id"]

        # Set the custom status
        response = client.post(
            "/api/applications/statuses/set",
            json={
                "job_id": "custom_status_test",
                "custom_status_id": status_id,
                "note": "Phone screen scheduled",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["custom_status_id"] == status_id

    def test_update_application_status(self, client):
        """Test updating application status via API."""
        # Create an application
        client.post("/api/applications/external", json={
            "job_id": "status_update_test",
            "job_title": "Developer",
            "company": "Tech Corp",
        })

        # Update status
        response = client.put(
            "/api/applications/status",
            json={
                "job_id": "status_update_test",
                "status": "under_review",
                "note": "Resume received by HR",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "under_review"

    def test_get_dashboard(self, client):
        """Test retrieving dashboard data via API."""
        # Create some test data
        client.post("/api/applications/actions", json={
            "job_id": "dash_job_1",
            "action": "save",
            "metadata": {"title": "Engineer", "company": "Company"},
        })
        client.post("/api/applications/external", json={
            "job_id": "dash_ext_1",
            "job_title": "Developer",
            "company": "Startup",
        })

        response = client.get("/api/applications/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert "applications" in data
        assert "summary" in data
        assert "custom_statuses" in data
        assert "filters_applied" in data

        # Check summary
        assert data["summary"]["total_applications"] >= 2
        assert data["summary"]["bookmarked"] >= 1
        assert data["summary"]["external"] >= 1

    def test_get_dashboard_with_filters(self, client):
        """Test dashboard with filtering parameters."""
        # Create test data
        client.post("/api/applications/actions", json={
            "job_id": "filter_test_1",
            "action": "save",
            "metadata": {"title": "Engineer", "company": "Company A"},
        })
        client.post("/api/applications/external", json={
            "job_id": "filter_test_2",
            "job_title": "Developer",
            "company": "Company B",
        })

        # Get dashboard without hidden
        response = client.get(
            "/api/applications/dashboard",
            params={"include_hidden": False, "include_bookmarked": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filters_applied"]["include_hidden"] is False
        assert data["filters_applied"]["include_bookmarked"] is True

    def test_get_application_details(self, client):
        """Test getting detailed application information."""
        # Create an application
        client.post("/api/applications/external", json={
            "job_id": "detail_test_1",
            "job_title": "Senior Engineer",
            "company": "Big Tech",
            "application_method": "referral",
        })

        response = client.get("/api/applications/detail_test_1")

        assert response.status_code == 200
        data = response.json()
        assert data["application_id"] == "detail_test_1"
        assert data["job_title"] == "Senior Engineer"
        assert data["company"] == "Big Tech"
        assert data["current_status"] == "applied_elsewhere"
        assert data["external_application_details"] is not None
        assert data["external_application_details"]["application_method"] == "referral"

    def test_unsave_job_via_api(self, client):
        """Test unsaving a job via API."""
        # Save a job
        client.post("/api/applications/actions", json={
            "job_id": "unsave_test_1",
            "action": "save",
            "metadata": {"title": "Engineer", "company": "Company"},
        })

        # Unsave it
        response = client.post(
            "/api/applications/actions",
            json={
                "job_id": "unsave_test_1",
                "action": "unsave",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "unsave"

    def test_unhide_job_via_api(self, client):
        """Test unhiding a job via API."""
        # Create and hide a job
        client.post("/api/applications/external", json={
            "job_id": "unhide_test_1",
            "job_title": "Developer",
            "company": "Company",
        })
        client.post("/api/applications/actions", json={
            "job_id": "unhide_test_1",
            "action": "hide",
        })

        # Unhide it
        response = client.post(
            "/api/applications/actions",
            json={
                "job_id": "unhide_test_1",
                "action": "unhide",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "unhide"

    def test_invalid_action_returns_400(self, client):
        """Test that invalid action returns 400 error."""
        response = client.post(
            "/api/applications/actions",
            json={
                "job_id": "test_job",
                "action": "invalid_action",
            },
        )

        # Should get validation error
        assert response.status_code == 422  # Validation error

    def test_nonexistent_job_returns_404(self, client):
        """Test that acting on non-existent job returns 404."""
        response = client.post(
            "/api/applications/actions",
            json={
                "job_id": "nonexistent_job",
                "action": "save",
            },
        )

        # This should succeed as it creates the job
        assert response.status_code == 200

        # Now try to unhide a job that doesn't exist
        response = client.post(
            "/api/applications/actions",
            json={
                "job_id": "totally_fake_job",
                "action": "unhide",
            },
        )

        assert response.status_code == 404
