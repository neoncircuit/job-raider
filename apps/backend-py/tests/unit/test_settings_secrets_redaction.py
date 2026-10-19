"""
Tests that settings API responses never return API key material.

Step 2.4: GET (and other UserSettings responses) expose has_* flags only.
"""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.settings import APIConfig, SettingsStorage, UserSettings


def _settings_with_keys(tmp_path: Path) -> SettingsStorage:
    """
    Build storage with Anthropic and Gemini keys on disk.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        SettingsStorage pointing at ``tmp_path``.
    """
    storage = SettingsStorage(settings_dir=tmp_path)
    settings = storage.load_settings()
    settings.api_config = APIConfig(
        anthropic_api_key="sk-ant-test-secret-value",
        gemini_api_key="AIza-test-secret-value",
        ollama_host="localhost:11434",
    )
    storage.save_settings(settings)
    return storage


class TestSettingsSecretsRedaction:
    """Settings responses must not include key strings."""

    def test_get_settings_returns_has_key_flags_not_secrets(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """
        GET /api/settings/ reports has_* booleans and omits key material.

        Args:
            client: Shared FastAPI TestClient.
            tmp_path: Temporary settings directory.
        """
        storage = _settings_with_keys(tmp_path)
        with patch("src.api.routes.settings.get_storage", return_value=storage):
            response = client.get("/api/settings/")

        assert response.status_code == 200
        raw = response.text
        assert "sk-ant-test-secret-value" not in raw
        assert "AIza-test-secret-value" not in raw
        assert "sk-" not in raw

        data = response.json()
        api = data["api_config"]
        assert api["has_anthropic_key"] is True
        assert api["has_gemini_key"] is True
        assert api["anthropic_api_key"] is None
        assert api["gemini_api_key"] is None

    def test_put_preserves_keys_when_client_sends_null(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """
        PUT with null keys keeps stored keys and still redacts the response.

        Args:
            client: Shared FastAPI TestClient.
            tmp_path: Temporary settings directory.
        """
        storage = _settings_with_keys(tmp_path)
        with patch("src.api.routes.settings.get_storage", return_value=storage):
            current = client.get("/api/settings/")
            assert current.status_code == 200
            body = current.json()
            body["api_config"]["ollama_host"] = "127.0.0.1:11434"
            put = client.put("/api/settings/", json=body)
            assert put.status_code == 200
            assert "sk-ant-test-secret-value" not in put.text
            assert put.json()["api_config"]["has_anthropic_key"] is True

            reloaded = storage.load_settings()
            assert reloaded.api_config.anthropic_api_key == "sk-ant-test-secret-value"
            assert reloaded.api_config.gemini_api_key == "AIza-test-secret-value"
            assert reloaded.api_config.ollama_host == "127.0.0.1:11434"

    def test_for_client_helper_redacts_keys(self) -> None:
        """
        for_client clears key strings and sets has_* flags.

        Returns:
            None.
        """
        from src.api.settings import for_client

        settings = UserSettings(
            api_config=APIConfig(
                anthropic_api_key="sk-ant-x",
                gemini_api_key=None,
            )
        )
        public = for_client(settings)
        assert public.api_config.has_anthropic_key is True
        assert public.api_config.has_gemini_key is False
        assert public.api_config.anthropic_api_key is None
        assert public.api_config.gemini_api_key is None
        # Original unchanged
        assert settings.api_config.anthropic_api_key == "sk-ant-x"
