"""
Tests for DELETE /api/settings/api-keys/{provider}.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.settings import get_storage


class TestDeleteApiKey:
    """Clear one stored cloud key without touching the other."""

    def test_delete_anthropic_keeps_gemini(self, client: TestClient) -> None:
        """
        DELETE anthropic clears that key and leaves Gemini stored.

        Args:
            client: Shared FastAPI TestClient (R6 tmp settings dir).

        Returns:
            None.
        """
        storage = get_storage()
        settings = storage.load_settings()
        settings.api_config.anthropic_api_key = "sk-ant-test-delete"
        settings.api_config.gemini_api_key = "AIza-test-keep"
        storage.save_settings(settings)

        response = client.delete("/api/settings/api-keys/anthropic")
        assert response.status_code == 200
        api = response.json()["api_config"]
        assert api["has_anthropic_key"] is False
        assert api["has_gemini_key"] is True
        assert api["anthropic_api_key"] is None
        assert "sk-ant-test-delete" not in response.text

        reloaded = storage.load_settings()
        assert reloaded.api_config.anthropic_api_key is None
        assert reloaded.api_config.gemini_api_key == "AIza-test-keep"

    def test_delete_unknown_provider_returns_422(self, client: TestClient) -> None:
        """
        DELETE with a provider other than anthropic or gemini is 422.

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        response = client.delete("/api/settings/api-keys/openai")
        assert response.status_code == 422
