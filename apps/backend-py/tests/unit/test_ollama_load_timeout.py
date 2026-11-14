"""
Tests for the Ollama model load step (ollama-load-timeout task).

When the client's model is not loaded, the client loads it first with a long
timeout, so the chat timeout applies to the answer only and a slow load is not
cancelled and started again. Fake HTTP, no Ollama.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock, patch

import requests

from src.llm.base import LLMConfig, Message, MessageType
from src.llm.ollama_client import OllamaClient

MODEL = "qwen2.5:7b"
OTHER = "qwen2.5:3b"
CHAT_REPLY = {
    "message": {"role": "assistant", "content": "ok"},
    "done_reason": "stop",
    "eval_count": 1,
}


class FakeOllama:
    """Records each call (method, path, body, timeout) and answers like Ollama."""

    def __init__(
        self,
        loaded: Optional[List[str]] = None,
        ps_error: bool = False,
        load_error: Optional[Exception] = None,
    ) -> None:
        """
        Set up the fake.

        Args:
            loaded: Model names that /api/ps reports as loaded.
            ps_error: Make /api/ps fail.
            load_error: Raise this error for a load request (``/api/generate``
                for the client's own model).
        """
        self.loaded = loaded or []
        self.ps_error = ps_error
        self.load_error = load_error
        self.calls: List[Dict[str, Any]] = []

    @staticmethod
    def _reply(payload: Dict[str, Any]) -> MagicMock:
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

    def _record(self, method: str, url: str, kwargs: Dict[str, Any]) -> None:
        """
        Record one call.

        Args:
            method: ``GET`` or ``POST``.
            url: The URL.
            kwargs: The keyword arguments of the call.
        """
        self.calls.append(
            {
                "method": method,
                "path": url[url.index("/api/") :],
                "json": kwargs.get("json"),
                "timeout": kwargs.get("timeout"),
            }
        )

    def get(self, url: str, **kwargs: Any) -> MagicMock:
        """
        Fake ``requests.get``.

        Args:
            url: The URL.
            **kwargs: The call's keyword arguments.

        Returns:
            The response.

        Raises:
            requests.ConnectionError: When /api/ps should fail.
        """
        self._record("GET", url, kwargs)
        if url.endswith("/api/ps"):
            if self.ps_error:
                raise requests.ConnectionError("ps down")
            return self._reply({"models": [{"name": n} for n in self.loaded]})
        return self._reply({})

    def post(self, url: str, **kwargs: Any) -> MagicMock:
        """
        Fake ``requests.post``.

        Args:
            url: The URL.
            **kwargs: The call's keyword arguments.

        Returns:
            The response.

        Raises:
            Exception: ``load_error`` for a load request of the client's model.
        """
        self._record("POST", url, kwargs)
        body = kwargs.get("json") or {}
        is_load = url.endswith("/api/generate") and body.get("model") == MODEL
        if is_load and self.load_error is not None:
            raise self.load_error
        return self._reply(CHAT_REPLY if url.endswith("/api/chat") else {})

    def paths(self) -> List[str]:
        """
        The called paths in order; ``/api/generate`` shows its model.

        Returns:
            One entry per call.
        """
        out = []
        for call in self.calls:
            path = call["path"]
            if path == "/api/generate":
                path += f"({call['json']['model']})"
            out.append(path)
        return out

    def load_calls(self) -> List[Dict[str, Any]]:
        """
        The load requests for the client's model.

        Returns:
            The recorded ``/api/generate`` calls for ``MODEL``.
        """
        return [
            c
            for c in self.calls
            if c["path"] == "/api/generate" and c["json"]["model"] == MODEL
        ]


def chat(
    fake: FakeOllama, call_kwargs: Optional[Dict[str, Any]] = None, **client_kwargs: Any
) -> None:
    """
    Make one chat call with a client on the fake.

    Args:
        fake: The fake Ollama.
        call_kwargs: Extra ``generate`` arguments.
        **client_kwargs: Extra ``OllamaClient`` arguments.
    """
    with (
        patch.object(OllamaClient, "_is_ollama_running", return_value=True),
        patch.object(
            OllamaClient,
            "available_models",
            new_callable=PropertyMock,
            return_value=[MODEL],
        ),
        patch("src.llm.ollama_client.requests.get", side_effect=fake.get),
        patch("src.llm.ollama_client.requests.post", side_effect=fake.post),
    ):
        client = OllamaClient(config=LLMConfig(model=MODEL), **client_kwargs)
        client.generate(
            [Message(role=MessageType.USER, content="hi")],
            max_tokens=8,
            **(call_kwargs or {}),
        )


def test_model_not_loaded_is_loaded_before_the_chat() -> None:
    """The load request goes first: the model, the keep_alive, no prompt, 600 s."""
    fake = FakeOllama(loaded=[])
    chat(fake, keep_alive="10m")
    assert fake.paths() == ["/api/ps", f"/api/generate({MODEL})", "/api/chat"]
    load = fake.load_calls()[0]
    assert load["json"] == {"model": MODEL, "keep_alive": "10m"}
    assert "prompt" not in load["json"]
    assert load["timeout"] == 600


def test_loaded_model_gets_no_load_request() -> None:
    """The model is already in /api/ps: the chat runs at once."""
    fake = FakeOllama(loaded=[MODEL])
    chat(fake)
    assert fake.paths() == ["/api/ps", "/api/chat"]


def test_failing_ps_skips_the_load_and_runs_the_chat() -> None:
    """When /api/ps fails, the client does not guess; the chat runs as before."""
    fake = FakeOllama(ps_error=True)
    chat(fake)
    assert fake.paths() == ["/api/ps", "/api/chat"]


def test_load_timeout_logs_a_warning_and_runs_the_chat() -> None:
    """A load that times out gives a warning; the chat request still runs."""
    fake = FakeOllama(loaded=[], load_error=requests.Timeout("slow"))
    with patch("src.llm.ollama_client.logger") as log:
        chat(fake)
    assert fake.paths()[-1] == "/api/chat"
    assert log.warning.called
    assert MODEL in log.warning.call_args.args[0]


def test_load_error_logs_a_warning_and_runs_the_chat() -> None:
    """A load that fails (HTTP error) gives a warning; the chat request still runs."""
    fake = FakeOllama(loaded=[], load_error=requests.HTTPError("500"))
    with patch("src.llm.ollama_client.logger") as log:
        chat(fake)
    assert fake.paths()[-1] == "/api/chat"
    assert log.warning.called


def test_load_step_runs_with_one_model_at_a_time_off() -> None:
    """The defect does not depend on the one-model setting: the load still runs."""
    fake = FakeOllama(loaded=[OTHER])
    chat(fake, one_model_at_a_time=False)
    assert fake.paths() == ["/api/ps", f"/api/generate({MODEL})", "/api/chat"]


def test_unload_comes_first_then_the_load_with_one_ps_call() -> None:
    """One /api/ps call; the other model is unloaded, then this model is loaded."""
    fake = FakeOllama(loaded=[OTHER])
    chat(fake, one_model_at_a_time=True)
    assert fake.paths() == [
        "/api/ps",
        f"/api/generate({OTHER})",
        f"/api/generate({MODEL})",
        "/api/chat",
    ]


def test_no_keep_alive_sends_only_the_model() -> None:
    """Without a keep_alive, the load body has only the model (Ollama default)."""
    fake = FakeOllama(loaded=[])
    chat(fake)
    assert fake.load_calls()[0]["json"] == {"model": MODEL}


def test_keep_alive_of_the_call_is_used_for_the_load() -> None:
    """A keep_alive given to generate() overrides the client's keep_alive."""
    fake = FakeOllama(loaded=[])
    chat(fake, call_kwargs={"keep_alive": "30m"}, keep_alive="10m")
    assert fake.load_calls()[0]["json"]["keep_alive"] == "30m"


def test_load_timeout_can_be_set_on_the_client() -> None:
    """The constructor argument load_timeout sets the timeout of the load request."""
    fake = FakeOllama(loaded=[])
    chat(fake, load_timeout=900)
    assert fake.load_calls()[0]["timeout"] == 900
