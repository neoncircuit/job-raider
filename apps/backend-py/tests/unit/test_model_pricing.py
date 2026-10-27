"""
Tests for the single catalog price table (Step 3.6, A1).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.llm.base import LLMConfig, Message, MessageType
from src.llm.claude_client import ClaudeClient
from src.metrics.cost_tracker import (
    calculate_usage_cost,
    get_model_price,
    reset_price_config_cache,
)


def test_yaml_prices_for_each_catalog_model() -> None:
    """Each catalog cloud model has the dated official price."""
    sonnet = get_model_price("anthropic", "claude-sonnet-4-6")
    opus = get_model_price("anthropic", "claude-opus-4-7")
    haiku = get_model_price("anthropic", "claude-haiku-4-5-20251001")
    flash = get_model_price("gemini", "gemini-2.5-flash")
    pro = get_model_price("gemini", "gemini-2.5-pro")
    assert sonnet is not None and (
        sonnet.input_per_million,
        sonnet.output_per_million,
    ) == (
        3.0,
        15.0,
    )
    assert opus is not None and (opus.input_per_million, opus.output_per_million) == (
        5.0,
        25.0,
    )
    assert haiku is not None and (
        haiku.input_per_million,
        haiku.output_per_million,
    ) == (
        1.0,
        5.0,
    )
    assert flash is not None and (
        flash.input_per_million,
        flash.output_per_million,
    ) == (
        0.30,
        2.50,
    )
    assert pro is not None and (pro.input_per_million, pro.output_per_million) == (
        1.25,
        10.0,
    )


def test_gemini_pro_uses_the_200k_tier() -> None:
    """A prompt above 200,000 tokens uses the higher Gemini 2.5 Pro tier."""
    price = get_model_price("gemini", "gemini-2.5-pro")
    assert price is not None
    low = calculate_usage_cost(price, 200_000, 1_000_000)
    high = calculate_usage_cost(price, 200_001, 1_000_000)
    assert round(low, 6) == round(0.25 + 10.0, 6)
    assert round(high, 6) == round((200_001 / 1_000_000) * 2.50 + 15.0, 6)


def test_anthropic_cache_multipliers() -> None:
    """A cache write is 1.25 times input, and a cache read is 0.1 times input."""
    price = get_model_price("anthropic", "claude-sonnet-4-6")
    assert price is not None
    assert price.cache_write_multiplier == 1.25
    assert price.cache_read_multiplier == 0.1
    cost = calculate_usage_cost(
        price,
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cache_write_tokens=1_000_000,
        cache_read_tokens=1_000_000,
    )
    assert round(cost, 6) == round(3.0 + 3.0 * 1.25 + 3.0 * 0.1, 6)


def test_catalog_row_without_price_fields_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A catalog row without cost_per_input or cost_per_output is unknown."""
    import src.metrics.cost_tracker as cost_mod

    reset_price_config_cache()
    monkeypatch.setattr(
        cost_mod,
        "_PRICE_CONFIG",
        {
            "models": {
                "anthropic": {
                    "models": {
                        "claude-new-model": {"max_tokens": 8192},
                    }
                }
            }
        },
    )
    assert get_model_price("anthropic", "claude-new-model") is None
    reset_price_config_cache()


def test_catalog_row_without_cost_per_input_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A catalog row with only cost_per_output is unknown, and nothing raises."""
    import src.metrics.cost_tracker as cost_mod

    reset_price_config_cache()
    monkeypatch.setattr(
        cost_mod,
        "_PRICE_CONFIG",
        {
            "models": {
                "anthropic": {
                    "models": {
                        "claude-half-priced": {"cost_per_output": 15.0},
                    }
                }
            }
        },
    )
    assert get_model_price("anthropic", "claude-half-priced") is None
    reset_price_config_cache()


def test_price_value_that_is_not_a_number_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A price or multiplier that is not a number is unknown, and nothing raises."""
    import src.metrics.cost_tracker as cost_mod

    reset_price_config_cache()
    monkeypatch.setattr(
        cost_mod,
        "_PRICE_CONFIG",
        {
            "models": {
                "anthropic": {
                    "models": {
                        "claude-comma-price": {
                            "cost_per_input": "3,0",
                            "cost_per_output": 15.0,
                        },
                    }
                },
                "gemini": {
                    "cache_write_multiplier": "one and a quarter",
                    "models": {
                        "gemini-bad-multiplier": {
                            "cost_per_input": 0.30,
                            "cost_per_output": 2.50,
                        },
                    },
                },
            }
        },
    )
    assert get_model_price("anthropic", "claude-comma-price") is None
    assert get_model_price("gemini", "gemini-bad-multiplier") is None
    reset_price_config_cache()


@patch("src.llm.claude_client.Anthropic")
@patch("src.llm.claude_client.AsyncAnthropic")
def test_claude_client_calls_the_api_once_when_a_price_is_bad(
    mock_async: MagicMock,
    mock_sync: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad catalog price gives an unknown cost and does not repeat the paid call."""
    import src.metrics.cost_tracker as cost_mod

    reset_price_config_cache()
    monkeypatch.setattr(
        cost_mod,
        "_PRICE_CONFIG",
        {
            "models": {
                "anthropic": {
                    "models": {
                        "claude-sonnet-4-6": {
                            "cost_per_input": "3,0",
                            "cost_per_output": 15.0,
                        },
                    }
                }
            }
        },
    )
    mock_sync.return_value.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="ok")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    client = ClaudeClient(
        config=LLMConfig(model="claude-sonnet-4-6", max_retries=2, retry_delay=0.0),
        api_key="test-key",
    )
    response = client.generate([Message(role=MessageType.USER, content="hello")])
    assert response.content == "ok"
    assert response.cost is None
    assert mock_sync.return_value.messages.create.call_count == 1
    reset_price_config_cache()


def test_unknown_cloud_model_has_no_price() -> None:
    """A cloud model that is not in the table returns None."""
    assert get_model_price("anthropic", "claude-not-in-catalog") is None
    assert get_model_price("gemini", "gemini-2.0-flash") is None


def test_ollama_model_has_zero_cost() -> None:
    """Ollama always has cost 0, including an unknown local name."""
    listed = get_model_price("ollama", "qwen2.5:3b")
    unknown = get_model_price("ollama", "not-a-real-ollama-model")
    assert listed is not None and listed.input_per_million == 0.0
    assert unknown is not None and unknown.output_per_million == 0.0
    assert calculate_usage_cost(listed, 1_000_000, 1_000_000) == 0.0


@patch("src.llm.claude_client.Anthropic")
@patch("src.llm.claude_client.AsyncAnthropic")
def test_claude_cache_tokens_are_priced(
    mock_async: MagicMock, mock_sync: MagicMock
) -> None:
    """Cache creation and cache read tokens use the catalog multipliers."""
    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=0,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    mock_sync.return_value.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="ok")],
        usage=usage,
    )
    client = ClaudeClient(
        config=LLMConfig(model="claude-sonnet-4-6"),
        api_key="test-key",
    )
    response = client.generate([Message(role=MessageType.USER, content="hello")])
    assert response.cache_write_tokens == 1_000_000
    assert response.cache_read_tokens == 1_000_000
    assert response.cost == round(3.0 + 3.75 + 0.3, 6)
