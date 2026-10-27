"""
Tests for process-wide router cost recording (Step 3.6, A3).
"""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.llm.base import LLMResponse, Message, MessageType
from src.llm.router import LLMRouter, RouteConfig, TaskType
from src.metrics.cost_tracker import (
    get_cost_tracker,
    reset_cost_tracker,
    reset_price_config_cache,
)


def _messages() -> list[Message]:
    """Return a small chat that must not appear in a call record."""
    return [
        Message(role=MessageType.SYSTEM, content="SECRET_PROMPT_TEXT"),
        Message(role=MessageType.USER, content="SECRET_USER_TEXT"),
    ]


def _response(
    *,
    content: str = "SECRET_RESPONSE_TEXT",
    model: str = "qwen2.5:3b",
    provider: str = "ollama",
    prompt_tokens: int = 10,
    completion_tokens: int = 4,
    cost: float = 0.0,
) -> LLMResponse:
    """
    Build a fake client response.

    Args:
        content: Generated text (must not appear in a record).
        model: Served model.
        provider: Served provider.
        prompt_tokens: Prompt token count.
        completion_tokens: Completion token count.
        cost: Client-reported cost.

    Returns:
        An ``LLMResponse`` for a mocked client.
    """
    return LLMResponse(
        content=content,
        model=model,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        tokens_used=prompt_tokens + completion_tokens,
        cost=cost,
        cached=False,
        tokens_estimated=False,
    )


def _router(
    *,
    fallback: bool = False,
    client: MagicMock | None = None,
) -> LLMRouter:
    """
    Build a router with one selection route and a mocked client.

    Args:
        fallback: When True, configure an Anthropic fallback.
        client: Optional shared mock client.

    Returns:
        A router that does not follow user settings.
    """
    routes = {
        TaskType.SELECTION: RouteConfig(
            task_type=TaskType.SELECTION,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="anthropic" if fallback else None,
            fallback_model="claude-sonnet-4-6" if fallback else None,
        ),
        TaskType.VALIDATION: RouteConfig(
            task_type=TaskType.VALIDATION,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider=None,
            fallback_model=None,
        ),
    }
    router = LLMRouter(routes=routes)
    mock = client or MagicMock()
    if client is None:
        mock.generate.return_value = _response()
        mock.generate_async = AsyncMock(return_value=_response())
    router._get_client = MagicMock(return_value=mock)  # type: ignore[method-assign]
    return router


@pytest.fixture(autouse=True)
def _empty_tracker() -> None:
    """Each test starts from an empty process-wide tracker and price cache."""
    reset_cost_tracker()
    reset_price_config_cache()
    yield
    reset_cost_tracker()
    reset_price_config_cache()


def _anthropic_primary_router(
    *,
    fallback: bool = True,
) -> tuple[LLMRouter, MagicMock, MagicMock]:
    """
    Build a router with an Anthropic primary and an optional Ollama fallback.

    Args:
        fallback: When True, configure an Ollama fallback.

    Returns:
        The router, the primary mock, and the fallback mock.
    """
    routes = {
        TaskType.SELECTION: RouteConfig(
            task_type=TaskType.SELECTION,
            primary_provider="anthropic",
            primary_model="claude-sonnet-4-6",
            fallback_provider="ollama" if fallback else None,
            fallback_model="qwen2.5:3b" if fallback else None,
        ),
    }
    router = LLMRouter(routes=routes)
    primary = MagicMock()
    primary.generate.return_value = _response(
        content="PRIMARY_ANSWER",
        model="claude-sonnet-4-6",
        provider="anthropic",
        prompt_tokens=10,
        completion_tokens=4,
        cost=0.0,
    )
    primary.generate_async = AsyncMock(
        return_value=_response(
            content="PRIMARY_ANSWER",
            model="claude-sonnet-4-6",
            provider="anthropic",
            prompt_tokens=10,
            completion_tokens=4,
            cost=0.0,
        )
    )
    fallback_client = MagicMock()
    fallback_client.generate.return_value = _response(content="FALLBACK_ANSWER")
    fallback_client.generate_async = AsyncMock(
        return_value=_response(content="FALLBACK_ANSWER")
    )

    def _client(provider: str, _model: str) -> MagicMock:
        return primary if provider == "anthropic" else fallback_client

    router._get_client = MagicMock(side_effect=_client)  # type: ignore[method-assign]
    return router, primary, fallback_client


def test_primary_call_is_recorded_once() -> None:
    """One primary success writes one record with tokens, provider, model, and cost."""
    router = _router()
    router.generate(_messages(), task_type=TaskType.SELECTION)
    records = get_cost_tracker().recent_calls()
    assert len(records) == 1
    record = records[0]
    assert record.task_type == TaskType.SELECTION.value
    assert record.provider == "ollama"
    assert record.model == "qwen2.5:3b"
    assert record.prompt_tokens == 10
    assert record.completion_tokens == 4
    assert record.total_tokens == 14
    assert record.cost_usd == 0.0
    assert record.cache_hit is False
    assert record.fallback is False
    assert record.error is False


def test_cache_hit_is_recorded_with_zero_tokens() -> None:
    """A response-cache hit is one record with cache_hit true and 0 tokens."""
    router = _router()
    router._response_cache.enabled = True
    router._response_cache.ttl = 3600
    msgs = _messages()
    router.generate(
        msgs, task_type=TaskType.VALIDATION, temperature=0.0, max_tokens=512
    )
    router.generate(
        msgs, task_type=TaskType.VALIDATION, temperature=0.0, max_tokens=512
    )
    records = get_cost_tracker().recent_calls()
    assert len(records) == 2
    hit = records[1]
    assert hit.cache_hit is True
    assert hit.prompt_tokens == 0
    assert hit.completion_tokens == 0
    assert hit.total_tokens == 0
    assert hit.cost_usd == 0.0
    assert hit.error is False


def test_primary_failure_and_fallback_success_are_two_records() -> None:
    """A failed primary and a successful fallback write two records."""
    client = MagicMock()
    client.generate.side_effect = [
        RuntimeError("primary down"),
        _response(
            model="claude-sonnet-4-6",
            provider="anthropic",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            cost=3.0,
        ),
    ]
    router = _router(fallback=True, client=client)
    router.generate(_messages(), task_type=TaskType.SELECTION)
    records = get_cost_tracker().recent_calls()
    assert len(records) == 2
    failed, served = records
    assert failed.error is True
    assert failed.fallback is False
    assert failed.provider == "ollama"
    assert failed.model == "qwen2.5:3b"
    assert failed.total_tokens == 0
    assert served.fallback is True
    assert served.error is False
    assert served.provider == "anthropic"
    assert served.model == "claude-sonnet-4-6"
    assert served.cost_usd == 3.0


def test_two_router_instances_share_one_tracker() -> None:
    """Every router writes to the same process-wide tracker."""
    _router().generate(_messages(), task_type=TaskType.SELECTION)
    _router().generate(_messages(), task_type=TaskType.SELECTION)
    assert len(get_cost_tracker().recent_calls()) == 2
    assert get_cost_tracker().process_totals()["calls"] == 2


@pytest.mark.asyncio
async def test_generate_async_records_the_same() -> None:
    """generate_async writes the same kind of record as generate."""
    router = _router()
    await router.generate_async(_messages(), task_type=TaskType.SELECTION)
    records = get_cost_tracker().recent_calls()
    assert len(records) == 1
    assert records[0].provider == "ollama"
    assert records[0].model == "qwen2.5:3b"
    assert records[0].total_tokens == 14
    assert records[0].error is False


def test_recording_error_does_not_change_router_result() -> None:
    """A tracker that raises still returns the client response."""
    router = _router()
    tracker = get_cost_tracker()
    original = tracker.record_call
    tracker.record_call = MagicMock(side_effect=RuntimeError("tracker down"))  # type: ignore[method-assign]
    try:
        result = router.generate(_messages(), task_type=TaskType.SELECTION)
        assert result.content == "SECRET_RESPONSE_TEXT"
    finally:
        tracker.record_call = original  # type: ignore[method-assign]


def test_record_has_no_prompt_or_response_text() -> None:
    """A call record holds counts and names only."""
    router = _router()
    router.generate(_messages(), task_type=TaskType.SELECTION)
    record = get_cost_tracker().recent_calls()[0]
    blob = str(asdict(record))
    assert "SECRET_PROMPT_TEXT" not in blob
    assert "SECRET_USER_TEXT" not in blob
    assert "SECRET_RESPONSE_TEXT" not in blob
    assert "content" not in asdict(record)
    assert "messages" not in asdict(record)


def test_recent_call_limit_is_1000_and_totals_count_every_call() -> None:
    """The recent list keeps 1000 records; process totals keep every call."""
    tracker = get_cost_tracker()
    for _ in range(1001):
        tracker.record_call(
            task_type="selection",
            provider="ollama",
            model="qwen2.5:3b",
            prompt_tokens=1,
            completion_tokens=1,
            tokens_estimated=False,
            latency_ms=1,
            cache_hit=False,
            fallback=False,
            error=False,
        )
    assert len(tracker.recent_calls()) == 1000
    totals = tracker.process_totals()
    assert totals["calls"] == 1001
    assert totals["prompt_tokens"] == 1001
    assert totals["completion_tokens"] == 1001
    assert totals["total_tokens"] == 2002


def test_price_lookup_error_does_not_change_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A price lookup that raises still returns the primary answer."""
    monkeypatch.setattr(
        "src.llm.router.get_model_price",
        MagicMock(side_effect=RuntimeError("price down")),
    )
    router, _primary, fallback_client = _anthropic_primary_router()
    result = router.generate(_messages(), task_type=TaskType.SELECTION)
    assert result.content == "PRIMARY_ANSWER"
    fallback_client.generate.assert_not_called()
    assert not any(record.error for record in get_cost_tracker().recent_calls())


@pytest.mark.asyncio
async def test_price_lookup_error_does_not_change_generate_async(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A price lookup that raises still returns the primary async answer."""
    monkeypatch.setattr(
        "src.llm.router.get_model_price",
        MagicMock(side_effect=RuntimeError("price down")),
    )
    router, _primary, fallback_client = _anthropic_primary_router()
    result = await router.generate_async(_messages(), task_type=TaskType.SELECTION)
    assert result.content == "PRIMARY_ANSWER"
    fallback_client.generate_async.assert_not_called()
    assert not any(record.error for record in get_cost_tracker().recent_calls())


def test_price_lookup_error_does_not_raise_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no fallback, a price lookup that raises does not raise from generate."""
    monkeypatch.setattr(
        "src.llm.router.get_model_price",
        MagicMock(side_effect=RuntimeError("price down")),
    )
    router, _primary, _fallback = _anthropic_primary_router(fallback=False)
    result = router.generate(_messages(), task_type=TaskType.SELECTION)
    assert result.content == "PRIMARY_ANSWER"


def test_catalog_row_without_price_keeps_primary_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A catalog row with no price fields records cost None and keeps the primary."""
    import src.metrics.cost_tracker as cost_mod

    monkeypatch.setattr(
        cost_mod,
        "_PRICE_CONFIG",
        {
            "models": {
                "anthropic": {
                    "models": {
                        "claude-sonnet-4-6": {"max_tokens": 8192},
                    }
                }
            }
        },
    )
    router, _primary, fallback_client = _anthropic_primary_router()
    result = router.generate(_messages(), task_type=TaskType.SELECTION)
    assert result.content == "PRIMARY_ANSWER"
    fallback_client.generate.assert_not_called()
    records = get_cost_tracker().recent_calls()
    assert len(records) == 1
    assert records[0].error is False
    assert records[0].cost_usd is None
    assert records[0].provider == "anthropic"


def test_process_cost_is_unknown_when_one_call_has_no_price() -> None:
    """Process cost is unknown when one recorded call has no price."""
    tracker = get_cost_tracker()
    tracker.record_call(
        task_type="selection",
        provider="anthropic",
        model="claude-not-in-catalog",
        prompt_tokens=10,
        completion_tokens=4,
        latency_ms=1,
    )
    tracker.record_call(
        task_type="selection",
        provider="ollama",
        model="qwen2.5:3b",
        prompt_tokens=1,
        completion_tokens=1,
        latency_ms=1,
    )
    totals = tracker.process_totals()
    assert totals["cost_unknown"] == 1
    assert totals["cost_usd"] is None
