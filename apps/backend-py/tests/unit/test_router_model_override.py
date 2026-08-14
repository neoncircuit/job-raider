"""
Tests for one-shot LLM model overrides on the router.
"""

from src.llm.router import LLMRouter, RouteConfig, TaskType


def test_resolve_primary_model_uses_allowed_anthropic_override(monkeypatch):
    """Catalog Anthropic models override the route primary for that call."""
    monkeypatch.setattr(
        "src.config.loader.get_config_loader",
        lambda: type(
            "L",
            (),
            {
                "get_available_models": staticmethod(
                    lambda: {
                        "anthropic": [
                            "claude-sonnet-4-6",
                            "claude-haiku-4-5-20251001",
                        ],
                        "gemini": [],
                        "ollama": [],
                    }
                )
            },
        )(),
    )
    router = LLMRouter(
        routes={
            TaskType.COVER_LETTER_WRITING: RouteConfig(
                task_type=TaskType.COVER_LETTER_WRITING,
                primary_provider="anthropic",
                primary_model="claude-sonnet-4-6",
            )
        }
    )
    provider, model = router.resolve_primary_model(
        TaskType.COVER_LETTER_WRITING,
        "claude-haiku-4-5-20251001",
    )
    assert provider == "anthropic"
    assert model == "claude-haiku-4-5-20251001"


def test_resolve_primary_model_ignores_cross_provider_override(monkeypatch):
    """Ollama tags are ignored when the route provider is Anthropic."""
    monkeypatch.setattr(
        "src.config.loader.get_config_loader",
        lambda: type(
            "L",
            (),
            {
                "get_available_models": staticmethod(
                    lambda: {
                        "anthropic": ["claude-sonnet-4-6"],
                        "gemini": [],
                        "ollama": ["qwen2.5:7b"],
                    }
                )
            },
        )(),
    )
    router = LLMRouter(
        routes={
            TaskType.COVER_LETTER_WRITING: RouteConfig(
                task_type=TaskType.COVER_LETTER_WRITING,
                primary_provider="anthropic",
                primary_model="claude-sonnet-4-6",
            )
        }
    )
    provider, model = router.resolve_primary_model(
        TaskType.COVER_LETTER_WRITING,
        "qwen2.5:7b",
    )
    assert provider == "anthropic"
    assert model == "claude-sonnet-4-6"


def test_is_model_allowed_gemini_catalog(monkeypatch):
    """Gemini overrides must be in the YAML catalog."""
    monkeypatch.setattr(
        "src.config.loader.get_config_loader",
        lambda: type(
            "L",
            (),
            {
                "get_available_models": staticmethod(
                    lambda: {
                        "anthropic": [],
                        "gemini": ["gemini-2.5-pro", "gemini-2.5-flash"],
                        "ollama": [],
                    }
                )
            },
        )(),
    )
    router = LLMRouter()
    assert router.is_model_allowed_for_provider("gemini", "gemini-2.5-pro") is True
    assert router.is_model_allowed_for_provider("gemini", "not-a-real-model") is False


def test_is_model_allowed_ollama_requires_installed(monkeypatch):
    """Ollama overrides require an installed tag, not merely a catalog name."""
    router = LLMRouter()

    monkeypatch.setattr(
        "src.api.ollama_models.list_installed_ollama_models",
        lambda _host, timeout=3.0: ["qwen2.5:7b"],
    )
    monkeypatch.setattr(
        "src.api.ollama_models.resolve_effective_ollama_host",
        lambda host: host or "localhost:11434",
    )

    assert router.is_model_allowed_for_provider("ollama", "qwen2.5:7b") is True
    assert router.is_model_allowed_for_provider("ollama", "missing-model:99b") is False
