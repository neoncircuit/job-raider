"""
Job Raider - Ollama model discovery and tier defaults.

Helpers for listing installed Ollama models and applying small/large
tier defaults onto per-task routing configuration.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import requests

from .settings import ModelRouting, Provider

# Documented recommended defaults (user may override with any installed model).
RECOMMENDED_OLLAMA_SMALL = "qwen2.5:3b"
RECOMMENDED_OLLAMA_LARGE = "qwen2.5:7b"

# Tasks that use the "small / fast" Ollama primary in DEFAULT_ROUTES.
OLLAMA_SMALL_TASKS = frozenset(
    {
        "selection",
        "scoring",
        "validation",
        "general",
        "question_answering",
        "trust_analysis",
        "cover_letter_review",
    }
)

# Tasks that use the "large / quality" Ollama primary in DEFAULT_ROUTES.
OLLAMA_LARGE_TASKS = frozenset(
    {
        "jd_extraction",
        "resume_writing",
        "resume_parsing",
        "resume_analysis",
        "linkedin_analysis",
        "classification",
        "cover_letter_writing",
        "assessment_generation",
        "assessment_evaluation",
    }
)


def parse_ollama_host_port(ollama_host: str) -> Tuple[str, int]:
    """
    Parse an Ollama host string into (hostname, port).

    Accepts forms such as ``localhost:11434``, ``http://localhost:11434``,
    or bare ``localhost``.

    Args:
        ollama_host: Host string from settings or env.

    Returns:
        Tuple of hostname and port (default 11434).
    """
    host = (ollama_host or "localhost:11434").strip()
    for prefix in ("http://", "https://"):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    host = host.rstrip("/")
    if ":" in host:
        name, port_str = host.rsplit(":", 1)
        try:
            return name or "localhost", int(port_str)
        except ValueError:
            return name or "localhost", 11434
    return host or "localhost", 11434


def ollama_base_url(ollama_host: str) -> str:
    """
    Build an HTTP base URL for the Ollama API.

    Args:
        ollama_host: Host string from settings or env.

    Returns:
        Base URL such as ``http://localhost:11434``.
    """
    name, port = parse_ollama_host_port(ollama_host)
    return f"http://{name}:{port}"


def list_installed_ollama_models(ollama_host: str, timeout: float = 3.0) -> List[str]:
    """
    List model names currently installed in a running Ollama instance.

    Args:
        ollama_host: Ollama host string.
        timeout: Request timeout in seconds.

    Returns:
        Sorted unique model names, or an empty list if Ollama is unreachable.
    """
    try:
        response = requests.get(
            f"{ollama_base_url(ollama_host)}/api/tags", timeout=timeout
        )
        response.raise_for_status()
        data = response.json()
        names = [
            model["name"]
            for model in data.get("models", [])
            if isinstance(model, dict) and model.get("name")
        ]
        return sorted(set(names))
    except Exception:
        return []


def apply_ollama_tier_models(
    routing: Dict[str, ModelRouting],
    small_model: str,
    large_model: str,
    *,
    small_tasks: Optional[Iterable[str]] = None,
    large_tasks: Optional[Iterable[str]] = None,
) -> Dict[str, ModelRouting]:
    """
    Set primary Ollama models for small/large task tiers.

    Only updates entries whose primary provider is Ollama (or creates
    Ollama-primary entries when a known tier task is missing). Embedding
    and other non-tier tasks are left unchanged.

    Args:
        routing: Current per-task routing map.
        small_model: Model name for small/fast tasks.
        large_model: Model name for large/quality tasks.
        small_tasks: Optional override of small-tier task keys.
        large_tasks: Optional override of large-tier task keys.

    Returns:
        New routing dict with tier models applied.
    """
    small = frozenset(small_tasks) if small_tasks is not None else OLLAMA_SMALL_TASKS
    large = frozenset(large_tasks) if large_tasks is not None else OLLAMA_LARGE_TASKS
    updated: Dict[str, ModelRouting] = dict(routing)

    for task_type, model in (
        *((t, small_model) for t in small),
        *((t, large_model) for t in large),
    ):
        existing = updated.get(task_type)
        if existing is None:
            updated[task_type] = ModelRouting(
                task_type=task_type,
                primary_provider=Provider.OLLAMA,
                primary_model=model,
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-haiku-4-5-20251001",
            )
            continue
        if existing.primary_provider != Provider.OLLAMA:
            continue
        updated[task_type] = existing.model_copy(update={"primary_model": model})

    return updated


def derive_ollama_tier_models(
    routing: Dict[str, ModelRouting],
) -> Tuple[str, str]:
    """
    Derive currently configured small/large Ollama models from routing.

    Args:
        routing: Per-task routing map.

    Returns:
        Tuple of (small_model, large_model), falling back to recommended
        defaults when a tier has no Ollama primary configured.
    """
    small = RECOMMENDED_OLLAMA_SMALL
    large = RECOMMENDED_OLLAMA_LARGE

    selection = routing.get("selection")
    if selection and selection.primary_provider == Provider.OLLAMA:
        small = selection.primary_model

    resume = routing.get("resume_writing")
    if resume and resume.primary_provider == Provider.OLLAMA:
        large = resume.primary_model

    return small, large
