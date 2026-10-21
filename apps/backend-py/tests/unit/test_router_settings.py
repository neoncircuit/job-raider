"""
Tests for LLMRouter settings merge and live create_router settings reload.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.ollama_models import apply_cloud_fallback_provider
from src.api.settings import CloudProvider, ModelRouting, Provider, get_storage
from src.llm.base import Message
from src.llm.router import LLMRouter, TaskType, create_router


class TestReloadRoutesFromSettings:
    """reload_routes_from_settings merges without dropping defaults."""

    def test_merges_and_preserves_unspecified_tasks(self):
        """Partial settings override selection but keep embedding default."""
        router = LLMRouter()
        router.reload_routes_from_settings(
            {
                "selection": ModelRouting(
                    task_type="selection",
                    primary_provider=Provider.OLLAMA,
                    primary_model="gemma3:4b",
                    fallback_provider=Provider.ANTHROPIC,
                    fallback_model="claude-haiku-4-5-20251001",
                )
            }
        )
        assert router.routes[TaskType.SELECTION].primary_model == "gemma3:4b"
        assert TaskType.EMBEDDING in router.routes
        assert router.routes[TaskType.EMBEDDING].primary_model == "nomic-embed-text"

    def test_accepts_dict_routing(self):
        """Dict-shaped routing (JSON round-trip) is accepted."""
        router = LLMRouter()
        router.reload_routes_from_settings(
            {
                "scoring": {
                    "primary_provider": "ollama",
                    "primary_model": "llama3.2:3b",
                    "fallback_provider": "ollama",
                    "fallback_model": "gemma3:4b",
                }
            }
        )
        assert router.routes[TaskType.SCORING].primary_model == "llama3.2:3b"


class TestCreateRouterAppliesSettings:
    """create_router loads user settings when storage is available."""

    def test_create_router_applies_routing(self):
        """Saved routing is applied on create_router()."""
        mock_settings = MagicMock()
        mock_settings.routing = {
            "selection": ModelRouting(
                task_type="selection",
                primary_provider=Provider.OLLAMA,
                primary_model="custom:3b",
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-haiku-4-5-20251001",
            )
        }
        mock_settings.api_config.ollama_host = "localhost:11434"
        mock_settings.api_config.anthropic_api_key = "sk-ant-from-settings"
        mock_settings.api_config.gemini_api_key = "gemini-from-settings"
        mock_settings.cost_limits.enable_cache = True
        mock_settings.cost_limits.cache_ttl = 3600

        mock_storage = MagicMock()
        mock_storage.load_settings.return_value = mock_settings

        with patch("src.api.settings.get_storage", return_value=mock_storage):
            router = create_router()

        assert router.routes[TaskType.SELECTION].primary_model == "custom:3b"
        assert router.api_key == "sk-ant-from-settings"
        assert router.gemini_api_key == "gemini-from-settings"
        assert router._response_cache.enabled is True
        assert router._response_cache.ttl == 3600


class TestCreateRouterReloadsChangedSettings:
    """Factory routers follow Settings revisions; direct routers do not."""

    @staticmethod
    def _save_anthropic_fallback(key: str | None) -> None:
        """
        Save an Anthropic fallback and optional stored key for GENERAL.

        Args:
            key: Stored Anthropic key, or None.

        Returns:
            None.
        """
        storage = get_storage()
        settings = storage.load_settings()
        settings.api_config.anthropic_api_key = key
        settings.api_config.cloud_fallback_provider = CloudProvider.ANTHROPIC
        settings.routing["general"] = ModelRouting(
            task_type="general",
            primary_provider=Provider.OLLAMA,
            primary_model="qwen2.5:3b",
            fallback_provider=Provider.ANTHROPIC,
            fallback_model="claude-haiku-4-5-20251001",
        )
        storage.save_settings(settings)

    def test_generate_reloads_removed_key_and_none_fallback(self) -> None:
        """
        The next generate sees key removal and disables cloud fallback.

        Returns:
            None.
        """
        self._save_anthropic_fallback("sk-ant-old")
        router = create_router(api_key="constructor-key")
        assert router.api_key == "sk-ant-old"

        storage = get_storage()
        changed = storage.load_settings()
        changed.api_config.anthropic_api_key = None
        changed.api_config.cloud_fallback_provider = CloudProvider.NONE
        changed.routing = apply_cloud_fallback_provider(
            changed.routing, CloudProvider.NONE
        )
        storage.save_settings(changed)

        ollama = MagicMock()
        ollama.generate.side_effect = RuntimeError("ollama down")
        anthropic = MagicMock()

        def get_client(provider: str, model: str, config: Any = None) -> Any:
            return ollama if provider == "ollama" else anthropic

        with patch.object(router, "_get_client", side_effect=get_client):
            with pytest.raises(RuntimeError, match="ollama down"):
                router.generate(
                    [Message(role="user", content="hi")],
                    task_type=TaskType.GENERAL,
                )

        anthropic.generate.assert_not_called()
        assert router.api_key == "constructor-key"

    def test_removed_saved_key_uses_environment_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Removing a saved key lets ClaudeClient use ANTHROPIC_API_KEY.

        Args:
            monkeypatch: Pytest environment fixture.

        Returns:
            None.
        """
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-anthropic-key")
        self._save_anthropic_fallback("sk-ant-old")
        router = create_router()

        storage = get_storage()
        changed = storage.load_settings()
        changed.api_config.anthropic_api_key = None
        storage.save_settings(changed)

        router._refresh_user_settings_if_changed()
        client = router._get_client("anthropic", "claude-haiku-4-5-20251001")
        assert client.api_key == "env-anthropic-key"
        assert router.api_key is None

    def test_direct_router_keeps_routes_after_settings_save(self) -> None:
        """
        A directly built LLMRouter does not follow saved Settings.

        Returns:
            None.
        """
        route = LLMRouter.DEFAULT_ROUTES[TaskType.GENERAL]
        router = LLMRouter(routes={TaskType.GENERAL: route})
        original_routes = router.routes

        self._save_anthropic_fallback("sk-ant-new")

        assert router.routes is original_routes
        assert router.api_key is None

    def test_save_during_reload_is_applied_on_next_refresh(self) -> None:
        """
        A save that lands while the router reloads is not missed.

        The wrapped ``load_settings`` returns the older settings and then
        saves a new key, so the save lands after the load and before the
        router records the revision it applied.

        Returns:
            None.
        """
        self._save_anthropic_fallback("sk-ant-old")
        router = create_router()
        assert router.api_key == "sk-ant-old"

        storage = get_storage()
        real_load = storage.load_settings

        def load_then_save_new_key() -> Any:
            """
            Return the current settings, then save a newer key.

            Returns:
                The settings as they were before the newer save.
            """
            loaded = real_load()
            newer = real_load()
            newer.api_config.anthropic_api_key = "sk-ant-new"
            storage.save_settings(newer)
            return loaded

        # An unchanged save bumps the revision, so the next refresh reloads.
        storage.save_settings(real_load())
        with patch.object(storage, "load_settings", side_effect=load_then_save_new_key):
            router._refresh_user_settings_if_changed()
        assert router.api_key == "sk-ant-old"

        router._refresh_user_settings_if_changed()
        assert router.api_key == "sk-ant-new"

    def test_api_key_delete_reaches_long_lived_router(self, client: TestClient) -> None:
        """
        The API DELETE is observed on the long-lived router's next call.

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        self._save_anthropic_fallback("sk-ant-old")
        router = create_router(api_key="constructor-key")

        response = client.delete("/api/settings/api-keys/anthropic")
        assert response.status_code == 200

        router._refresh_user_settings_if_changed()
        assert router.api_key == "constructor-key"
