"""
Job Raider - Ollama model management.

List, pull, and delete models on the Ollama server through its HTTP API, so
the app never needs ``docker exec`` or the Docker socket. Guards:

- One pull at a time (process-wide).
- Models of 9B parameters or more are refused (unstable on the target host).
- A model that routing or RAG embedding uses cannot be deleted.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Set, Tuple

import requests

from .ollama_models import ollama_base_url
from .settings import Provider, UserSettings

MAX_PARAMS_BILLION = 9.0
"""Pull is refused at or above this parameter count (billions)."""

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,199}$")
_SIZE_RE = re.compile(r"(?:(\d+)x)?(\d+(?:\.\d+)?)b(?![a-z0-9])")

_pull_lock = threading.Lock()
_pull_state: Dict[str, Any] = {"status": "idle"}


class OllamaAdminError(Exception):
    """Raised for a refused or failed Ollama admin operation.

    Attributes:
        status_code: HTTP status code that the route should return.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        """Create the error.

        Args:
            message: Message safe to show to the user.
            status_code: HTTP status code for the route.
        """
        super().__init__(message)
        self.status_code = status_code


def validate_model_name(name: str) -> str:
    """Check that a model tag is well formed.

    Args:
        name: Model tag such as ``qwen2.5:3b``.

    Returns:
        The stripped model tag.

    Raises:
        OllamaAdminError: If the tag is empty or has unsafe characters.
    """
    cleaned = (name or "").strip()
    if not _NAME_RE.match(cleaned):
        raise OllamaAdminError(f"Invalid model name: {name!r}")
    return cleaned


def parameter_billions(name: str) -> Optional[float]:
    """Read the parameter count from a model tag.

    Mixture tags such as ``8x7b`` multiply out to 56.

    Args:
        name: Model tag.

    Returns:
        Largest parameter count found in billions, or None if the tag has none.
    """
    sizes = [
        float(match.group(2)) * (int(match.group(1)) if match.group(1) else 1)
        for match in _SIZE_RE.finditer(name.lower())
    ]
    return max(sizes) if sizes else None


def check_pull_allowed(name: str) -> None:
    """Refuse models that are too large for this host.

    Args:
        name: Validated model tag.

    Raises:
        OllamaAdminError: If the tag is 9B parameters or more.
    """
    size = parameter_billions(name)
    if size is not None and size >= MAX_PARAMS_BILLION:
        raise OllamaAdminError(
            f"{name} is about {size:g}B parameters. Models of "
            f"{MAX_PARAMS_BILLION:g}B or more are blocked because this host "
            "is unstable under large models."
        )


def models_in_use(settings: UserSettings, embedding_model: str) -> Set[str]:
    """Collect Ollama models that routing or RAG embedding depends on.

    Args:
        settings: Current user settings.
        embedding_model: RAG embedding model tag.

    Returns:
        Set of model tags that must not be deleted.
    """
    used: Set[str] = {embedding_model} if embedding_model else set()
    for route in settings.routing.values():
        if route.primary_provider == Provider.OLLAMA and route.primary_model:
            used.add(route.primary_model)
        if route.fallback_provider == Provider.OLLAMA and route.fallback_model:
            used.add(route.fallback_model)
    return used


def _same_model(a: str, b: str) -> bool:
    """Compare tags, treating a missing tag as ``latest``.

    Args:
        a: First model tag.
        b: Second model tag.

    Returns:
        True when both tags name the same model.
    """

    def norm(tag: str) -> str:
        return tag if ":" in tag else f"{tag}:latest"

    return norm(a) == norm(b)


def is_in_use(name: str, used: Iterable[str]) -> bool:
    """Check whether a tag matches any in-use model.

    Args:
        name: Model tag.
        used: In-use model tags.

    Returns:
        True when the tag is in use.
    """
    return any(_same_model(name, u) for u in used)


def list_models(host: str, used: Set[str], timeout: float = 5.0) -> Dict[str, Any]:
    """List installed models with size and in-use flags.

    Args:
        host: Effective Ollama host string.
        used: Model tags that routing or RAG uses.
        timeout: Request timeout in seconds.

    Returns:
        Dict with ``host``, ``reachable``, ``models`` and ``in_use``.
    """
    base = {"host": host, "in_use": sorted(used)}
    try:
        response = requests.get(f"{ollama_base_url(host)}/api/tags", timeout=timeout)
        response.raise_for_status()
        raw = response.json().get("models", [])
    except Exception as exc:  # noqa: BLE001 - surface any transport error
        return {**base, "reachable": False, "error": str(exc)[:200], "models": []}

    models = [
        {
            "name": m["name"],
            "size": m.get("size", 0),
            "modified_at": m.get("modified_at"),
            "parameter_size": (m.get("details") or {}).get("parameter_size"),
            "in_use": is_in_use(m["name"], used),
        }
        for m in raw
        if isinstance(m, dict) and m.get("name")
    ]
    models.sort(key=lambda m: m["name"])
    return {**base, "reachable": True, "models": models}


def get_pull_state() -> Dict[str, Any]:
    """Return a copy of the current pull state.

    Returns:
        Dict with ``status`` (idle, pulling, success, error) and progress fields.
    """
    return dict(_pull_state)


def begin_pull(name: str) -> Dict[str, Any]:
    """Reserve the single pull slot for a model.

    Args:
        name: Validated, allowed model tag.

    Returns:
        The new pull state.

    Raises:
        OllamaAdminError: With status 409 if another pull is running.
    """
    if not _pull_lock.acquire(blocking=False):
        current = _pull_state.get("model", "another model")
        raise OllamaAdminError(f"A pull is already running ({current}).", 409)
    _pull_state.clear()
    _pull_state.update(
        {
            "status": "pulling",
            "model": name,
            "message": "starting",
            "completed": 0,
            "total": 0,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "error": None,
        }
    )
    return get_pull_state()


def run_pull(
    host: str, name: str, timeout: Tuple[float, float] = (10.0, 300.0)
) -> None:
    """Stream an Ollama pull into the shared state, then free the slot.

    Call only after ``begin_pull`` succeeded. Runs in a worker thread.

    Args:
        host: Effective Ollama host string.
        name: Model tag to pull.
        timeout: Connect and per-read timeouts in seconds. Ollama can be
            silent for minutes while it verifies large layers.
    """
    try:
        with requests.post(
            f"{ollama_base_url(host)}/api/pull",
            json={"model": name, "stream": True},
            stream=True,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if event.get("error"):
                    raise OllamaAdminError(str(event["error"]))
                _pull_state["message"] = event.get("status", "")
                if event.get("total"):
                    _pull_state["total"] = event["total"]
                    _pull_state["completed"] = event.get("completed", 0)
        _pull_state["status"] = "success"
    except Exception as exc:  # noqa: BLE001 - report any failure to the UI
        _pull_state["status"] = "error"
        _pull_state["error"] = str(exc)[:300]
    finally:
        _pull_state["finished_at"] = datetime.now().isoformat()
        _pull_lock.release()


def delete_model(host: str, name: str, used: Set[str], timeout: float = 30.0) -> None:
    """Delete an installed model unless something depends on it.

    Args:
        host: Effective Ollama host string.
        name: Validated model tag.
        used: Model tags that routing or RAG uses.
        timeout: Request timeout in seconds.

    Raises:
        OllamaAdminError: 409 if in use, 404 if not installed, 502 on Ollama error.
    """
    if is_in_use(name, used):
        raise OllamaAdminError(
            f"{name} is used by model routing or RAG embedding. "
            "Change routing first.",
            409,
        )
    try:
        response = requests.delete(
            f"{ollama_base_url(host)}/api/delete",
            json={"model": name},
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        raise OllamaAdminError(f"Ollama unreachable: {exc}", 502) from exc
    if response.status_code == 404:
        raise OllamaAdminError(f"{name} is not installed.", 404)
    if response.status_code >= 400:
        raise OllamaAdminError(f"Ollama error: {response.text[:200]}", 502)
