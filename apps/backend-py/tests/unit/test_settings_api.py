"""
Job Raider - Settings API Tests

Tests for the settings API endpoints. These exercise the real routes
(GET /api/settings/, /models, /config/merged; POST /reset) via the shared
TestClient. Read-only GET endpoints are asserted directly; the mutation test
round-trips the settings returned by GET back through PUT to avoid constructing
a full UserSettings body by hand.
"""

from unittest.mock import patch

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
        with patch(
            "src.api.routes.settings.list_installed_ollama_models",
            return_value=["qwen2.5:3b", "custom-local:1b"],
        ):
            response = client.get("/api/settings/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "recommended" in data
        assert data["recommended"]["small"] == "qwen2.5:3b"
        assert data["recommended"]["large"] == "qwen2.5:7b"
        assert "custom-local:1b" in data.get("ollama", [])
        assert "custom-local:1b" in data.get("ollama_installed", [])

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

    def test_apply_ollama_defaults(self, client: TestClient):
        """POST /api/settings/ollama-defaults updates tier routing and saves."""
        response = client.post(
            "/api/settings/ollama-defaults",
            json={"small_model": "gemma3:4b", "large_model": "qwen2.5:14b"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["routing"]["selection"]["primary_model"] == "gemma3:4b"
        assert data["routing"]["resume_writing"]["primary_model"] == "qwen2.5:14b"
