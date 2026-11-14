"""
Tests for one Ollama model in GPU memory at a time (one-model-at-a-time task),
and for the removal of the no-op VRAM guard. Fake HTTP, no Ollama.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock, patch

import requests

from src.llm.base import LLMConfig, Message, MessageType
from src.llm.ollama_client import OllamaClient

CHAT_REPLY = {
    "message": {"role": "assistant", "content": "ok"},
    "done_reason": "stop",
    "eval_count": 1,
}


class FakeOllama:
    """Records calls by URL and answers /api/ps, /api/generate, and /api/chat."""

    def __init__(
        self,
        loaded: Optional[List[str]] = None,
        ps_error: bool = False,
        unload_error: bool = False,
    ) -> None:
        """
        Set up the fake.

        Args:
            loaded: Model names that /api/ps reports as loaded.
            ps_error: Make /api/ps fail.
            unload_error: Make the unload request fail.
        """
        self.loaded = loaded or []
        self.ps_error = ps_error
        self.unload_error = unload_error
        self.calls: List[Dict[str, Any]] = []

    def _reply(self, payload: Dict[str, Any]) -> MagicMock:
        """
        Build a fake HTTP response.

        Args:
            payload: The JSON body.

        Returns:
            The response mock.
        """
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = payload
        return response

    def get(self, url: str, **_kwargs: Any) -> MagicMock:
        """
        Fake ``requests.get``.

        Args:
            url: The URL.

        Returns:
            The response.

        Raises:
            requests.ConnectionError: When /api/ps should fail.
        """
        self.calls.append({"method": "GET", "url": url})
        if url.endswith("/api/ps"):
            if self.ps_error:
                raise requests.ConnectionError("ps down")
            return self._reply({"models": [{"name": n} for n in self.loaded]})
        return self._reply({})

    def post(
        self, url: str, json: Optional[Dict[str, Any]] = None, **_kwargs: Any
    ) -> MagicMock:
        """
        Fake ``requests.post``.

        Args:
            url: The URL.
            json: The body.

        Returns:
            The response.

        Raises:
            requests.ConnectionError: When the unload should fail.
        """
        self.calls.append({"method": "POST", "url": url, "json": json})
        if url.endswith("/api/generate") and self.unload_error:
            raise requests.ConnectionError("unload failed")
        return self._reply(CHAT_REPLY if url.endswith("/api/chat") else {})

    def paths(self) -> List[str]:
        """
        The called paths in order, with the unloaded model for /api/generate.

        Returns:
            One entry per call.
        """
        out = []
        for call in self.calls:
            path = call["url"].split(":11434")[-1].split("//")[-1]
            path = path[path.index("/api/") :] if "/api/" in path else path
            if path == "/api/generate":
                path += f"({call['json']['model']}, keep_alive={call['json']['keep_alive']})"
            out.append(path)
        return out


def chat(fake: FakeOllama, model: str = "qwen2.5:7b", **client_kwargs: Any) -> None:
    """
    Make one chat call with a client on the fake.

    Args:
        fake: The fake Ollama.
        model: The client's model.
        **client_kwargs: Extra ``OllamaClient`` arguments.
    """
    with (
        patch.object(OllamaClient, "_is_ollama_running", return_value=True),
        patch.object(
            OllamaClient,
            "available_models",
            new_callable=PropertyMock,
            return_value=[model],
        ),
        patch("src.llm.ollama_client.requests.get", side_effect=fake.get),
        patch("src.llm.ollama_client.requests.post", side_effect=fake.post),
    ):
        client = OllamaClient(config=LLMConfig(model=model), **client_kwargs)
        client.generate([Message(role=MessageType.USER, content="hi")], max_tokens=8)


def test_another_loaded_model_is_unloaded_before_the_chat() -> None:
    """With the option on, the other model is unloaded first, then the chat runs."""
    fake = FakeOllama(loaded=["qwen2.5:3b", "qwen2.5:7b"])
    chat(fake, one_model_at_a_time=True)
    assert fake.paths() == [
        "/api/ps",
        "/api/generate(qwen2.5:3b, keep_alive=0)",
        "/api/chat",
    ]


def test_the_same_model_is_not_unloaded() -> None:
    """Only the client's own model loaded: no unload request."""
    fake = FakeOllama(loaded=["qwen2.5:7b"])
    chat(fake, one_model_at_a_time=True)
    assert fake.paths() == ["/api/ps", "/api/chat"]


def test_option_off_does_not_ask_ollama() -> None:
    """With the option off (the client default), no /api/ps call is made."""
    fake = FakeOllama(loaded=["qwen2.5:3b"])
    chat(fake)
    assert fake.paths() == ["/api/chat"]


def test_a_failing_ps_or_unload_does_not_block_the_chat() -> None:
    """Errors from /api/ps or the unload are ignored; the chat still runs."""
    ps_down = FakeOllama(ps_error=True)
    chat(ps_down, one_model_at_a_time=True)
    assert ps_down.paths()[-1] == "/api/chat"

    unload_down = FakeOllama(loaded=["qwen2.5:3b"], unload_error=True)
    chat(unload_down, one_model_at_a_time=True)
    assert unload_down.paths()[-1] == "/api/chat"


def test_the_no_op_vram_guard_is_gone() -> None:
    """The guard that ignored its own result is removed."""
    assert not hasattr(OllamaClient, "_check_vram_before_inference")


def test_router_passes_the_setting_to_ollama_clients() -> None:
    """The router gives each Ollama client the one-model setting (default on)."""
    from src.llm.router import LLMRouter

    router = LLMRouter()
    with patch("src.llm.router.OllamaClient") as client_cls:
        router._get_client("ollama", "qwen2.5:7b")
        assert client_cls.call_args.kwargs["one_model_at_a_time"] is True
        router._clients.clear()
        router._ollama_one_model_at_a_time = False
        router._get_client("ollama", "qwen2.5:3b")
        assert client_cls.call_args.kwargs["one_model_at_a_time"] is False
