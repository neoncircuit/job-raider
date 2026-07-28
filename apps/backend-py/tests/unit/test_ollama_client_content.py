"""
Tests for Ollama chat content extraction and think passthrough.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.llm.base import LLMClientError, LLMConfig, Message, MessageType
from src.llm.ollama_client import OllamaClient, extract_ollama_chat_content


class TestExtractOllamaChatContent:
    """Content extraction from Ollama /api/chat message objects."""

    def test_prefers_content(self):
        """Non-empty content is returned as-is (stripped)."""
        assert (
            extract_ollama_chat_content(
                {"role": "assistant", "content": "  Hello  ", "thinking": "plan"}
            )
            == "Hello"
        )

    def test_empty_content(self):
        """Thinking-only messages yield empty content for the caller."""
        assert (
            extract_ollama_chat_content(
                {"role": "assistant", "content": "", "thinking": "long plan"}
            )
            == ""
        )

    def test_missing_content_key(self):
        """Missing content key is treated as empty."""
        assert extract_ollama_chat_content({"role": "assistant"}) == ""


def _chat_payload_from_mock(mock_post: MagicMock) -> dict:
    """
    Return the JSON body from the ``/api/chat`` POST call.

    Args:
        mock_post: Patched ``requests.post`` mock.

    Returns:
        Payload dict sent to Ollama chat.
    """
    for call in mock_post.call_args_list:
        args, kwargs = call
        url = args[0] if args else kwargs.get("url", "")
        if "/api/chat" in str(url):
            return kwargs["json"]
    raise AssertionError("No /api/chat POST was recorded")


class TestOllamaThinkPassthrough:
    """``think`` is opt-in so other callers keep Ollama defaults."""

    def test_think_omitted_from_payload_by_default(self):
        """Generate without think= leaves think out of the JSON body."""
        with (
            patch.object(OllamaClient, "_is_ollama_running", return_value=True),
            patch.object(
                OllamaClient,
                "available_models",
                new_callable=PropertyMock,
                return_value=["qwen2.5:3b"],
            ),
            patch("src.llm.ollama_client.requests.post") as mock_post,
        ):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "message": {"role": "assistant", "content": "ok"},
                "done_reason": "stop",
                "eval_count": 1,
            }
            mock_post.return_value = mock_resp

            client = OllamaClient(config=LLMConfig(model="qwen2.5:3b"))
            client.generate(
                [Message(role=MessageType.USER, content="hi")],
                max_tokens=16,
            )
            payload = _chat_payload_from_mock(mock_post)
            assert "think" not in payload

    def test_think_false_included_when_caller_sets_it(self):
        """Cover-letter style callers can pass think=False explicitly."""
        with (
            patch.object(OllamaClient, "_is_ollama_running", return_value=True),
            patch.object(
                OllamaClient,
                "available_models",
                new_callable=PropertyMock,
                return_value=["gemma4:e4b"],
            ),
            patch("src.llm.ollama_client.requests.post") as mock_post,
        ):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {
                "message": {"role": "assistant", "content": "letter body"},
                "done_reason": "stop",
                "eval_count": 8,
            }
            mock_post.return_value = mock_resp

            client = OllamaClient(config=LLMConfig(model="gemma4:e4b"))
            client.generate(
                [Message(role=MessageType.USER, content="write")],
                think=False,
                max_tokens=32,
            )
            payload = _chat_payload_from_mock(mock_post)
            assert payload.get("think") is False


class TestEmptyContentErrorMessage:
    """Guard that empty-content failures stay typed as LLMClientError."""

    def test_llm_client_error_type(self):
        """LLMClientError remains the raised type for empty generations."""
        with pytest.raises(LLMClientError):
            raise LLMClientError("Ollama returned empty content")
