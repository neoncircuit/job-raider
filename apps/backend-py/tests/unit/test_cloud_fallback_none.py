"""
Tests for CloudProvider.NONE as the default silent-cloud guard.

A forced Ollama failure must not call Anthropic or Gemini when fallback is
none. When Anthropic is selected, the fallback client is used and the
response carries ``provider=anthropic``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.api.ollama_models import apply_cloud_fallback_provider
from src.api.settings import APIConfig, CloudProvider, ModelRouting, Provider
from src.llm.base import LLMResponse, Message
from src.llm.router import LLMRouter, RouteConfig, TaskType


def _ollama_primary_route(*, fallback: str | None) -> dict[TaskType, RouteConfig]:
    """Build a single-task route map with an Ollama primary.

    Args:
        fallback: Fallback provider name, or None for local-only.

    Returns:
        Route map for ``TaskType.GENERAL``.
    """
    return {
        TaskType.GENERAL: RouteConfig(
            task_type=TaskType.GENERAL,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider=fallback,
            fallback_model="claude-haiku-4-5-20251001" if fallback else None,
        )
    }


class TestCloudProviderNoneDefault:
    """APIConfig and DEFAULT_ROUTES prefer local-only."""

    def test_api_config_default_is_none(self) -> None:
        """New settings default cloud fallback to none."""
        assert APIConfig().cloud_fallback_provider == CloudProvider.NONE

    def test_default_routes_have_no_cloud_fallback(self) -> None:
        """Built-in routes must not fall back to Anthropic or Gemini."""
        cloud = {"anthropic", "gemini"}
        for task, route in LLMRouter.DEFAULT_ROUTES.items():
            assert (
                route.fallback_provider not in cloud
            ), f"{task.value} still falls back to {route.fallback_provider}"


class TestGenerateRespectsNoneFallback:
    """``generate`` must not call a cloud client when fallback is none."""

    def test_none_fallback_raises_without_calling_cloud(self) -> None:
        """Forced Ollama failure with no fallback must not touch Anthropic."""
        router = LLMRouter(routes=_ollama_primary_route(fallback=None))
        anthropic = MagicMock()
        ollama = MagicMock()
        ollama.generate.side_effect = RuntimeError("ollama down")

        def get_client(provider: str, model: str, config: Any = None) -> Any:
            if provider == "ollama":
                return ollama
            if provider == "anthropic":
                return anthropic
            raise AssertionError(f"unexpected provider {provider}")

        with patch.object(router, "_get_client", side_effect=get_client):
            with pytest.raises(RuntimeError, match="ollama down"):
                router.generate(
                    [Message(role="user", content="hi")],
                    task_type=TaskType.GENERAL,
                )
        anthropic.generate.assert_not_called()

    def test_anthropic_fallback_is_used_and_marked(self) -> None:
        """With Anthropic fallback, a failed Ollama call uses Anthropic."""
        router = LLMRouter(routes=_ollama_primary_route(fallback="anthropic"))
        ollama = MagicMock()
        ollama.generate.side_effect = RuntimeError("ollama down")
        anthropic = MagicMock()
        anthropic.generate.return_value = LLMResponse(
            content="from cloud",
            model="claude-haiku-4-5-20251001",
            cost=0.01,
        )

        def get_client(provider: str, model: str, config: Any = None) -> Any:
            return ollama if provider == "ollama" else anthropic

        with patch.object(router, "_get_client", side_effect=get_client):
            response = router.generate(
                [Message(role="user", content="hi")],
                task_type=TaskType.GENERAL,
            )
        anthropic.generate.assert_called_once()
        assert response.content == "from cloud"
        assert response.provider == "anthropic"

    def test_successful_primary_sets_provider(self) -> None:
        """A successful Ollama call stamps provider=ollama on the response."""
        router = LLMRouter(routes=_ollama_primary_route(fallback=None))
        ollama = MagicMock()
        ollama.generate.return_value = LLMResponse(
            content="local", model="qwen2.5:3b", cost=0.0
        )
        with patch.object(router, "_get_client", return_value=ollama):
            response = router.generate(
                [Message(role="user", content="hi")],
                task_type=TaskType.GENERAL,
            )
        assert response.provider == "ollama"


class TestApplyCloudFallbackNone:
    """``apply_cloud_fallback_provider`` clears cloud fallbacks for NONE."""

    def test_none_clears_cloud_fallbacks(self) -> None:
        """Selecting none removes Anthropic/Gemini fallbacks; keeps Ollama."""
        routing = {
            "selection": ModelRouting(
                task_type="selection",
                primary_provider=Provider.OLLAMA,
                primary_model="qwen2.5:3b",
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-haiku-4-5-20251001",
            ),
            "scoring": ModelRouting(
                task_type="scoring",
                primary_provider=Provider.OLLAMA,
                primary_model="qwen2.5:3b",
                fallback_provider=Provider.OLLAMA,
                fallback_model="gemma3:4b",
            ),
        }
        updated = apply_cloud_fallback_provider(routing, CloudProvider.NONE)
        assert updated["selection"].fallback_provider is None
        assert updated["selection"].fallback_model is None
        assert updated["scoring"].fallback_provider == Provider.OLLAMA
