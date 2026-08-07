"""
Unit tests for kind-A allowlisted response caching on LLMRouter.
"""

from unittest.mock import MagicMock

import pytest

from src.llm.base import LLMResponse, Message, MessageType
from src.llm.router import LLMRouter, TaskType


def _messages() -> list[Message]:
    """Return a tiny stable chat for cache keys."""
    return [
        Message(role=MessageType.SYSTEM, content="Extract fields."),
        Message(role=MessageType.USER, content="Raw JD text"),
    ]


def _response(content: str = "ok") -> LLMResponse:
    """Build a minimal LLMResponse."""
    return LLMResponse(content=content, model="qwen2.5:7b", cost=0.0, cached=False)


@pytest.fixture
def router() -> LLMRouter:
    """Router with caching enabled and a mocked primary client."""
    r = LLMRouter()
    r._response_cache.enabled = True
    r._response_cache.ttl = 3600
    client = MagicMock()
    client.generate = MagicMock(return_value=_response("fresh"))
    r._get_client = MagicMock(return_value=client)  # type: ignore[method-assign]
    return r


class TestRouterResponseCache:
    """Allowlisted TaskTypes reuse identical low-temp responses."""

    def test_validation_second_call_is_cache_hit(self, router: LLMRouter) -> None:
        """Identical validation calls hit the response cache."""
        msgs = _messages()
        first = router.generate(
            msgs, task_type=TaskType.VALIDATION, temperature=0.0, max_tokens=512
        )
        second = router.generate(
            msgs, task_type=TaskType.VALIDATION, temperature=0.0, max_tokens=512
        )

        assert first.content == "fresh"
        assert second.cached is True
        assert second.content == "fresh"
        assert router._get_client.return_value.generate.call_count == 1
        assert router.stats["cache_hits"] == 1
        assert router.stats["cache_misses"] == 1

    def test_cover_letter_writing_never_cached(self, router: LLMRouter) -> None:
        """Creative cover-letter writing stays uncached even at low temperature."""
        msgs = _messages()
        router.generate(
            msgs,
            task_type=TaskType.COVER_LETTER_WRITING,
            temperature=0.0,
            max_tokens=512,
        )
        router.generate(
            msgs,
            task_type=TaskType.COVER_LETTER_WRITING,
            temperature=0.0,
            max_tokens=512,
        )

        assert router._get_client.return_value.generate.call_count == 2
        assert router.stats["cache_hits"] == 0

    def test_high_temperature_skips_cache(self, router: LLMRouter) -> None:
        """Allowlisted tasks above the temperature guard are not cached."""
        msgs = _messages()
        router.generate(
            msgs, task_type=TaskType.JD_EXTRACTION, temperature=0.8, max_tokens=512
        )
        router.generate(
            msgs, task_type=TaskType.JD_EXTRACTION, temperature=0.8, max_tokens=512
        )

        assert router._get_client.return_value.generate.call_count == 2
        assert router.stats["cache_hits"] == 0

    def test_disabled_settings_skip_cache(self, router: LLMRouter) -> None:
        """Master enable_cache=False disables kind-A caching."""
        router._response_cache.enabled = False
        msgs = _messages()
        router.generate(
            msgs, task_type=TaskType.RESUME_PARSING, temperature=0.3, max_tokens=512
        )
        router.generate(
            msgs, task_type=TaskType.RESUME_PARSING, temperature=0.3, max_tokens=512
        )

        assert router._get_client.return_value.generate.call_count == 2
        assert router.stats["cache_hits"] == 0

    def test_jd_extraction_at_point_three_is_cached(self, router: LLMRouter) -> None:
        """Current JD extraction temperature (0.3) is within the cache guard."""
        msgs = _messages()
        router.generate(
            msgs, task_type=TaskType.JD_EXTRACTION, temperature=0.3, max_tokens=512
        )
        second = router.generate(
            msgs, task_type=TaskType.JD_EXTRACTION, temperature=0.3, max_tokens=512
        )

        assert second.cached is True
        assert router._get_client.return_value.generate.call_count == 1
