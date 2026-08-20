"""
Tests for Ollama model discovery helpers and tier default application.
"""

from src.api.ollama_models import (
    RECOMMENDED_OLLAMA_LARGE,
    RECOMMENDED_OLLAMA_SMALL,
    apply_cloud_fallback_provider,
    apply_ollama_tier_models,
    derive_ollama_tier_models,
    is_loopback_ollama_host,
    ollama_base_url,
    parse_ollama_host_port,
    resolve_effective_ollama_host,
)
from src.api.settings import CloudProvider, ModelRouting, Provider


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

    def test_loopback_detection(self):
        """Loopback hosts are identified for Docker remapping."""
        assert is_loopback_ollama_host("localhost:11434")
        assert is_loopback_ollama_host("127.0.0.1")
        assert not is_loopback_ollama_host("ollama:11434")


class TestResolveEffectiveOllamaHost:
    """Docker-aware host selection when Settings still say localhost."""

    def test_settings_non_loopback_wins(self):
        """Explicit compose/desktop host is kept."""
        assert (
            resolve_effective_ollama_host(
                "host.docker.internal:11434",
                env_host="ollama:11434",
                in_docker=True,
            )
            == "host.docker.internal:11434"
        )

    def test_docker_loopback_falls_back_to_env(self):
        """Inside Docker, localhost Settings yield to OLLAMA_HOST."""
        assert (
            resolve_effective_ollama_host(
                "localhost:11434",
                env_host="ollama:11434",
                in_docker=True,
            )
            == "ollama:11434"
        )

    def test_non_docker_keeps_localhost(self):
        """On the host, localhost Settings remain valid."""
        assert (
            resolve_effective_ollama_host(
                "localhost:11434",
                env_host="ollama:11434",
                in_docker=False,
            )
            == "localhost:11434"
        )

    def test_docker_empty_defaults_to_host_gateway(self):
        """Inside Docker with no Settings/env, prefer host.docker.internal."""
        assert (
            resolve_effective_ollama_host(
                "",
                env_host="",
                in_docker=True,
            )
            == "host.docker.internal:11434"
        )


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

    def test_apply_cloud_fallback_switches_to_gemini(self):
        """Cloud fallback retargets Anthropic fallbacks to Gemini models."""
        routing = {
            "selection": ModelRouting(
                task_type="selection",
                primary_provider=Provider.OLLAMA,
                primary_model=RECOMMENDED_OLLAMA_SMALL,
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-haiku-4-5-20251001",
            ),
            "scoring": ModelRouting(
                task_type="scoring",
                primary_provider=Provider.OLLAMA,
                primary_model=RECOMMENDED_OLLAMA_SMALL,
                fallback_provider=Provider.OLLAMA,
                fallback_model="gemma3:4b",
            ),
        }
        updated = apply_cloud_fallback_provider(routing, CloudProvider.GEMINI)
        assert updated["selection"].fallback_provider == Provider.GEMINI
        assert updated["selection"].fallback_model == "gemini-2.5-flash"
        assert updated["scoring"].fallback_provider == Provider.OLLAMA

    def test_derive_falls_back_to_recommended(self):
        """Empty routing yields documented recommended defaults."""
        small, large = derive_ollama_tier_models({})
        assert small == RECOMMENDED_OLLAMA_SMALL
        assert large == RECOMMENDED_OLLAMA_LARGE
