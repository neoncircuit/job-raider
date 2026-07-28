"""
Job Raider - Ollama model discovery and tier defaults.

Helpers for listing installed Ollama models and applying small/large
tier defaults onto per-task routing configuration.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import requests

from .settings import CloudProvider, ModelRouting, Provider

# Documented recommended defaults (user may override with any installed model).
RECOMMENDED_OLLAMA_SMALL = "qwen2.5:3b"
RECOMMENDED_OLLAMA_LARGE = "qwen2.5:7b"

# Default cloud fallback models when local Ollama cannot serve a request.
CLOUD_FALLBACK_SMALL = {
    CloudProvider.ANTHROPIC: "claude-haiku-4-5-20251001",
    CloudProvider.GEMINI: "gemini-2.5-flash",
}
CLOUD_FALLBACK_LARGE = {
    CloudProvider.ANTHROPIC: "claude-sonnet-4-6",
    CloudProvider.GEMINI: "gemini-2.5-pro",
}

# Cloud providers that Settings can select as the Ollama fallback.
_CLOUD_FALLBACK_PROVIDERS = frozenset({Provider.ANTHROPIC, Provider.GEMINI})

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


def is_loopback_ollama_host(ollama_host: str) -> bool:
    """
    Return True when the host targets the local loopback interface.

    Args:
        ollama_host: Host string from settings or env.

    Returns:
        True for localhost / 127.0.0.1 / ::1 / 0.0.0.0 (any port).
    """
    name, _port = parse_ollama_host_port(ollama_host)
    return name.lower() in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def running_in_docker() -> bool:
    """
    Detect whether the process is running inside a Docker container.

    Returns:
        True when ``/.dockerenv`` is present.
    """
    from pathlib import Path

    return Path("/.dockerenv").exists()


def resolve_effective_ollama_host(
    settings_host: str | None = None,
    *,
    env_host: str | None = None,
    in_docker: bool | None = None,
) -> str:
    """
    Choose the Ollama host string for runtime / health checks.

    Preference: non-loopback Settings host, then ``OLLAMA_HOST`` when Settings
    is loopback inside Docker (``localhost`` inside a container is not the
    shared Ollama service), then Settings, then env, then localhost.

    Args:
        settings_host: Host from ``api_config.ollama_host``.
        env_host: Optional override of ``OLLAMA_HOST`` (for tests).
        in_docker: Optional override of Docker detection (for tests).

    Returns:
        Effective host:port string.
    """
    import os

    settings = (settings_host or "").strip()
    env = (env_host if env_host is not None else os.getenv("OLLAMA_HOST") or "").strip()
    docker = running_in_docker() if in_docker is None else in_docker

    if settings and not (
        docker
        and is_loopback_ollama_host(settings)
        and env
        and not is_loopback_ollama_host(env)
    ):
        return settings
    if env:
        return env
    if settings:
        return settings
    return "localhost:11434"


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


def default_cloud_fallback_model(cloud: CloudProvider, task_type: str) -> str:
    """
    Pick a default cloud fallback model for a task tier.

    Args:
        cloud: Selected cloud fallback provider.
        task_type: Routing task key.

    Returns:
        Provider-specific model id for small or large tier work.
    """
    if task_type in OLLAMA_SMALL_TASKS:
        return CLOUD_FALLBACK_SMALL[cloud]
    return CLOUD_FALLBACK_LARGE[cloud]


def apply_cloud_fallback_provider(
    routing: Dict[str, ModelRouting],
    cloud: CloudProvider,
) -> Dict[str, ModelRouting]:
    """
    Retarget cloud fallbacks (Anthropic/Gemini) to the selected provider.

    Local Ollama-to-Ollama fallbacks are left unchanged. Entries with no
    fallback are skipped.

    Args:
        routing: Current per-task routing map.
        cloud: Cloud provider to use when Ollama fails.

    Returns:
        New routing dict with cloud fallbacks updated.
    """
    cloud_provider = Provider(cloud.value)
    updated: Dict[str, ModelRouting] = {}
    for task_type, entry in routing.items():
        if (
            entry.fallback_provider is None
            or entry.fallback_provider not in _CLOUD_FALLBACK_PROVIDERS
        ):
            updated[task_type] = entry
            continue
        updated[task_type] = entry.model_copy(
            update={
                "fallback_provider": cloud_provider,
                "fallback_model": default_cloud_fallback_model(cloud, task_type),
            }
        )
    return updated


def apply_ollama_tier_models(
    routing: Dict[str, ModelRouting],
    small_model: str,
    large_model: str,
    *,
    small_tasks: Optional[Iterable[str]] = None,
    large_tasks: Optional[Iterable[str]] = None,
    cloud_fallback: CloudProvider = CloudProvider.ANTHROPIC,
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
        cloud_fallback: Cloud provider for newly created fallbacks.

    Returns:
        New routing dict with tier models applied.
    """
    small = frozenset(small_tasks) if small_tasks is not None else OLLAMA_SMALL_TASKS
    large = frozenset(large_tasks) if large_tasks is not None else OLLAMA_LARGE_TASKS
    updated: Dict[str, ModelRouting] = dict(routing)
    cloud_provider = Provider(cloud_fallback.value)

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
                fallback_provider=cloud_provider,
                fallback_model=default_cloud_fallback_model(cloud_fallback, task_type),
            )
            continue
        if existing.primary_provider != Provider.OLLAMA:
            continue
        updated[task_type] = existing.model_copy(update={"primary_model": model})

    return apply_cloud_fallback_provider(updated, cloud_fallback)


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
