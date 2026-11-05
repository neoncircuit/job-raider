"""Tests for the default cover-letter writer (decision log 2026-11-05)."""

from src.api.ollama_models import (
    OLLAMA_LARGE_TASKS,
    OLLAMA_SMALL_TASKS,
    RECOMMENDED_OLLAMA_LARGE,
    apply_ollama_tier_models,
    default_cloud_fallback_model,
)
from src.api.settings import CloudProvider
from src.llm.router import LLMRouter, TaskType


def test_default_writer_route_is_the_large_local_model() -> None:
    """The built-in cover-letter writing route uses qwen2.5:7b on Ollama."""
    route = LLMRouter.DEFAULT_ROUTES[TaskType.COVER_LETTER_WRITING]

    assert route.primary_provider == "ollama"
    assert route.primary_model == "qwen2.5:7b"
    assert route.fallback_provider is None


def test_default_writer_is_the_recommended_large_model() -> None:
    """The writer route and the recommended large tier model are the same."""
    route = LLMRouter.DEFAULT_ROUTES[TaskType.COVER_LETTER_WRITING]

    assert route.primary_model == RECOMMENDED_OLLAMA_LARGE


def test_cover_letter_writing_is_in_the_large_tier() -> None:
    """Cover-letter writing is a large-tier task, not a small-tier task."""
    assert "cover_letter_writing" in OLLAMA_LARGE_TASKS
    assert "cover_letter_writing" not in OLLAMA_SMALL_TASKS
    assert "resume_writing" in OLLAMA_LARGE_TASKS


def test_tier_apply_gives_the_writer_the_large_model() -> None:
    """Applying the tiers sets the writer to the large model."""
    routing = apply_ollama_tier_models({}, "gemma3:4b", "qwen2.5:14b")

    assert routing["cover_letter_writing"].primary_model == "qwen2.5:14b"
    assert routing["selection"].primary_model == "gemma3:4b"


def test_writer_cloud_fallback_is_the_large_cloud_model() -> None:
    """With a cloud fallback, the writer gets the large cloud model."""
    assert (
        default_cloud_fallback_model(CloudProvider.ANTHROPIC, "cover_letter_writing")
        == "claude-sonnet-4-6"
    )
    assert (
        default_cloud_fallback_model(CloudProvider.GEMINI, "cover_letter_writing")
        == "gemini-2.5-pro"
    )
