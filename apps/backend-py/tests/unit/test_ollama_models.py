"""
Tests for Ollama model discovery helpers and tier default application.
"""

from src.api.ollama_models import (
    RECOMMENDED_OLLAMA_LARGE,
    RECOMMENDED_OLLAMA_SMALL,
    apply_ollama_tier_models,
    derive_ollama_tier_models,
    ollama_base_url,
    parse_ollama_host_port,
)
from src.api.settings import ModelRouting, Provider


class TestParseOllamaHost:
    """Host string parsing for Ollama base URL."""

    def test_host_port(self):
        """Bare host:port splits correctly."""
        assert parse_ollama_host_port("localhost:11434") == ("localhost", 11434)

    def test_http_url(self):
        """http:// prefix is stripped before parsing."""
        assert parse_ollama_host_port("http://127.0.0.1:11434") == (
            "127.0.0.1",
            11434,
        )
        assert ollama_base_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434"

    def test_bare_host(self):
        """Bare hostname uses default port 11434."""
        assert parse_ollama_host_port("ollama") == ("ollama", 11434)


class TestOllamaTierModels:
    """Small/large tier application onto routing maps."""

    def test_apply_updates_ollama_primaries(self):
        """Applying tiers updates selection and resume_writing models."""
        routing = {
            "selection": ModelRouting(
                task_type="selection",
                primary_provider=Provider.OLLAMA,
                primary_model=RECOMMENDED_OLLAMA_SMALL,
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-haiku-4-5-20251001",
            ),
            "resume_writing": ModelRouting(
                task_type="resume_writing",
                primary_provider=Provider.OLLAMA,
                primary_model=RECOMMENDED_OLLAMA_LARGE,
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-sonnet-4-6",
            ),
        }
        updated = apply_ollama_tier_models(routing, "gemma3:4b", "qwen2.5:14b")
        assert updated["selection"].primary_model == "gemma3:4b"
        assert updated["resume_writing"].primary_model == "qwen2.5:14b"

    def test_derive_falls_back_to_recommended(self):
        """Empty routing yields documented recommended defaults."""
        small, large = derive_ollama_tier_models({})
        assert small == RECOMMENDED_OLLAMA_SMALL
        assert large == RECOMMENDED_OLLAMA_LARGE
