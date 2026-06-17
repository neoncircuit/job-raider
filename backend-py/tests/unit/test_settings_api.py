"""
Job Raider - Settings API Tests

Tests for the settings API endpoints. These exercise the real routes
(GET /api/settings/, /models, /config/merged; POST /reset) via the shared
TestClient. Read-only GET endpoints are asserted directly; the mutation test
round-trips the settings returned by GET back through PUT to avoid constructing
a full UserSettings body by hand.
"""

from fastapi.testclient import TestClient


class TestSettingsAPI:
    """Test settings API endpoints."""

    def test_get_settings(self, client: TestClient):
        """GET /api/settings/ returns the current user settings."""
        response = client.get("/api/settings/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_available_models(self, client: TestClient):
        """GET /api/settings/models returns models grouped by provider."""
        response = client.get("/api/settings/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_merged_config(self, client: TestClient):
        """GET /api/settings/config/merged returns merged configuration."""
        response = client.get("/api/settings/config/merged")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_update_settings_roundtrip(self, client: TestClient):
        """PUT /api/settings/ accepts the body returned by GET (round-trip)."""
        current = client.get("/api/settings/")
        assert current.status_code == 200
        response = client.put("/api/settings/", json=current.json())
        assert response.status_code == 200

    def test_reset_settings(self, client: TestClient):
        """POST /api/settings/reset restores defaults."""
        response = client.post("/api/settings/reset")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
