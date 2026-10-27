"""
Tests for Ollama token counts from the /api/chat response (Step 3.6, A2).
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

from src.llm.base import LLMConfig, Message, MessageType
from src.llm.ollama_client import OllamaClient


def _generate_with_chat_payload(payload: dict) -> tuple:
    """
    Run one generate call against a fake /api/chat response.

    Args:
        payload: JSON body returned by the fake HTTP response.

    Returns:
        The LLMResponse and the mocked ``requests.post``.
    """
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
        mock_resp.json.return_value = payload
        mock_post.return_value = mock_resp
        client = OllamaClient(config=LLMConfig(model="qwen2.5:3b"))
        response = client.generate([Message(role=MessageType.USER, content="hello")])
        return response, mock_post


def test_chat_response_counts_are_used() -> None:
    """prompt_eval_count and eval_count become the token counts."""
    response, mock_post = _generate_with_chat_payload(
        {
            "message": {"role": "assistant", "content": "ok"},
            "done_reason": "stop",
            "prompt_eval_count": 12,
            "eval_count": 7,
        }
    )
    assert response.prompt_tokens == 12
    assert response.completion_tokens == 7
    assert response.tokens_used == 19
    assert response.tokens_estimated is False
    assert mock_post.call_count == 1


def test_missing_counts_use_length_estimate() -> None:
    """A missing count uses characters / 4 and marks the response estimated."""
    response, mock_post = _generate_with_chat_payload(
        {
            "message": {"role": "assistant", "content": "abcd" * 3},
            "done_reason": "stop",
        }
    )
    assert response.prompt_tokens == len("hello") // 4
    assert response.completion_tokens == 3
    assert response.tokens_estimated is True
    assert mock_post.call_count == 1


def test_one_generation_makes_one_http_request() -> None:
    """Generation does not call /api/tokenize."""
    _, mock_post = _generate_with_chat_payload(
        {
            "message": {"role": "assistant", "content": "ok"},
            "done_reason": "stop",
            "prompt_eval_count": 4,
            "eval_count": 2,
        }
    )
    urls = [str(call.args[0]) for call in mock_post.call_args_list]
    assert urls == ["http://localhost:11434/api/chat"]
    assert mock_post.call_count == 1
