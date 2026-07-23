"""
Tests for LLMRouter settings merge and create_router settings load.
"""

from unittest.mock import MagicMock, patch

from src.api.settings import ModelRouting, Provider
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

        mock_storage = MagicMock()
        mock_storage.load_settings.return_value = mock_settings

        with patch("src.api.settings.get_storage", return_value=mock_storage):
            router = create_router()

        assert router.routes[TaskType.SELECTION].primary_model == "custom:3b"
