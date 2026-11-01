"""Tests for the context size and the JSON schema in the router and the Ollama client (Step 3.7, MH-3)."""

import asyncio
from typing import Any, Dict, Tuple
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.llm.base import LLMConfig, LLMResponse, Message, MessageType
from src.llm.ollama_client import OllamaClient
from src.llm.router import (
    DEFAULT_NUM_CTX,
    LLMRouter,
    TaskType,
    context_size,
    schema_key,
)

SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {"critique": {"type": "string"}},
    "required": ["critique"],
}
OTHER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {"score": {"type": "integer"}},
    "required": ["score"],
}


def _messages() -> list:
    """
    A short chat for the calls.

    Returns:
        Two messages.
    """
    return [
        Message(role=MessageType.SYSTEM, content="Answer in JSON."),
        Message(role=MessageType.USER, content="Review this."),
    ]


def _ollama_payload(**kwargs: Any) -> Dict[str, Any]:
    """
    Run one Ollama generate call against a fake /api/chat and return its body.

    Args:
        **kwargs: Generation arguments for ``OllamaClient.generate``.

    Returns:
        The JSON body that the client sent.
    """
    with (
        patch.object(OllamaClient, "_is_ollama_running", return_value=True),
        patch.object(
            OllamaClient,
            "available_models",
            new_callable=PropertyMock,
            return_value=["qwen2.5:3b"],
        ),
        patch("src.llm.ollama_client.requests.post") as post,
    ):
        answer = MagicMock()
        answer.json.return_value = {
            "message": {"role": "assistant", "content": "{}"},
            "prompt_eval_count": 5,
            "eval_count": 2,
        }
        post.return_value = answer
        client = OllamaClient(config=LLMConfig(model="qwen2.5:3b"))
        client.generate(_messages(), **kwargs)
        return post.call_args.kwargs["json"]


def _router() -> Tuple[LLMRouter, MagicMock]:
    """
    A router with a fake client and the response cache on.

    Returns:
        The router and the fake client.
    """
    router = LLMRouter()
    router._response_cache.enabled = True
    client = MagicMock()
    client.generate = MagicMock(
        return_value=LLMResponse(content="{}", model="qwen2.5:3b", cost=0.0)
    )
    client.generate_async = AsyncMock(
        return_value=LLMResponse(content="{}", model="qwen2.5:3b", cost=0.0)
    )
    router._get_client = MagicMock(return_value=client)  # type: ignore[method-assign]
    return router, client


def test_ollama_sends_the_context_size() -> None:
    """``num_ctx`` goes to ``options.num_ctx``."""
    payload = _ollama_payload(num_ctx=8192)

    assert payload["options"]["num_ctx"] == 8192


def test_ollama_sends_no_context_size_without_one() -> None:
    """Without ``num_ctx``, Ollama keeps its own default."""
    payload = _ollama_payload()

    assert "num_ctx" not in payload["options"]


def test_ollama_sends_the_schema_as_format() -> None:
    """``response_schema`` goes to ``format`` unchanged."""
    payload = _ollama_payload(response_schema=SCHEMA)

    assert payload["format"] == SCHEMA


def test_ollama_sends_no_format_without_a_schema() -> None:
    """Without a schema, the request has no ``format``."""
    payload = _ollama_payload()

    assert "format" not in payload


def test_context_sizes_of_the_tasks() -> None:
    """JD extraction and resume parsing get 8192 tokens; other tasks 4096."""
    assert DEFAULT_NUM_CTX == 4096
    assert context_size(TaskType.JD_EXTRACTION) == 8192
    assert context_size(TaskType.RESUME_PARSING) == 8192
    assert context_size(TaskType.SELECTION) == 4096
    assert context_size(TaskType.RESUME_WRITING) == 4096


@pytest.mark.parametrize(
    "task_type, expected",
    [(TaskType.JD_EXTRACTION, 8192), (TaskType.SELECTION, 4096)],
)
def test_router_sends_the_task_context_size(task_type: TaskType, expected: int) -> None:
    """The router gives the client the context size of the task."""
    router, client = _router()

    router.generate(_messages(), task_type=task_type, temperature=0.5)

    assert client.generate.call_args.kwargs["num_ctx"] == expected


def test_a_caller_context_size_wins() -> None:
    """A ``num_ctx`` from the caller is not replaced."""
    router, client = _router()

    router.generate(_messages(), task_type=TaskType.JD_EXTRACTION, num_ctx=2048)

    assert client.generate.call_args.kwargs["num_ctx"] == 2048


def test_router_passes_the_schema_to_the_client() -> None:
    """The router gives ``response_schema`` to the client unchanged."""
    router, client = _router()

    router.generate(
        _messages(), task_type=TaskType.COVER_LETTER_REVIEW, response_schema=SCHEMA
    )

    assert client.generate.call_args.kwargs["response_schema"] == SCHEMA


def test_async_router_sends_the_task_context_size() -> None:
    """``generate_async`` also gives the client the task's context size."""
    router, client = _router()

    asyncio.run(
        router.generate_async(
            _messages(), task_type=TaskType.RESUME_PARSING, temperature=0.5
        )
    )

    assert client.generate_async.call_args.kwargs["num_ctx"] == 8192


def test_cache_key_has_the_context_size_and_the_schema() -> None:
    """The cache key changes with the context size and with the schema."""
    router, _ = _router()

    def extra(**kwargs: Any) -> Dict[str, Any]:
        """
        The extra cache-key fields for a validation call.

        Args:
            **kwargs: Generation arguments.

        Returns:
            The extra fields.
        """
        return router._cache_extra(TaskType.VALIDATION, "ollama", kwargs)

    assert extra(num_ctx=4096) != extra(num_ctx=8192)
    assert extra(response_schema=SCHEMA) != extra(response_schema=OTHER_SCHEMA)
    assert extra(response_schema=SCHEMA) != extra()
    assert extra(response_schema=SCHEMA)["response_schema"] == schema_key(SCHEMA)


def test_schema_key_ignores_key_order() -> None:
    """The same schema with another key order gives the same cache key."""
    reordered = {"required": ["critique"], **SCHEMA}

    assert schema_key(reordered) == schema_key(SCHEMA)
    assert len(schema_key(SCHEMA)) == 16


def test_a_new_schema_is_not_a_cache_hit() -> None:
    """Two cacheable calls with different schemas both reach the client."""
    router, client = _router()

    for schema in (SCHEMA, OTHER_SCHEMA):
        router.generate(
            _messages(),
            task_type=TaskType.VALIDATION,
            temperature=0.0,
            response_schema=schema,
        )

    assert client.generate.call_count == 2
