"""
Unit tests for Anthropic prompt-prefix caching in ClaudeClient.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.llm.base import LLMConfig, Message, MessageType
from src.llm.claude_client import ClaudeClient


@pytest.fixture
def mock_anthropic_response():
    """Build a minimal Anthropic message response."""
    response = MagicMock()
    block = MagicMock()
    block.text = "Hello"
    response.content = [block]
    response.usage.input_tokens = 10
    response.usage.output_tokens = 5
    return response


class TestClaudePromptCache:
    """ClaudeClient sends cache_control when prompt cache is enabled."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.llm.claude_client.Anthropic")
    @patch("src.llm.claude_client.AsyncAnthropic")
    def test_cache_control_when_enabled(
        self, _async_cls, anthropic_cls, mock_anthropic_response
    ) -> None:
        """System prompt includes ephemeral cache_control when enabled."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        anthropic_cls.return_value = mock_client

        client = ClaudeClient(
            config=LLMConfig(model="claude-sonnet-4-6"),
            enable_prompt_cache=True,
        )
        messages = [
            Message(role=MessageType.SYSTEM, content="You are helpful."),
            Message(role=MessageType.USER, content="Hi"),
        ]
        client.generate(messages)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        system = call_kwargs["system"]
        assert isinstance(system, list)
        assert system[0]["cache_control"] == {"type": "ephemeral"}
        assert system[0]["text"] == "You are helpful."
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("src.llm.claude_client.Anthropic")
    @patch("src.llm.claude_client.AsyncAnthropic")
    def test_plain_system_when_disabled(
        self, _async_cls, anthropic_cls, mock_anthropic_response
    ) -> None:
        """System prompt is a plain string when caching is disabled."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_anthropic_response
        anthropic_cls.return_value = mock_client

        client = ClaudeClient(
            config=LLMConfig(model="claude-sonnet-4-6"),
            enable_prompt_cache=False,
        )
        messages = [
            Message(role=MessageType.SYSTEM, content="You are helpful."),
            Message(role=MessageType.USER, content="Hi"),
        ]
        client.generate(messages)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are helpful."
        assert "cache_control" not in str(call_kwargs)
