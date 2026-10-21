"""
Job Raider - Settings Management

Provides models and storage for user-configurable settings including
model routing, API credentials, and parameters.

Author: Job Raider
Date: 2026-04-24
"""

import json
import logging
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..llm.router import TaskType

_logger = logging.getLogger(__name__)

# Per-process revision is sufficient because Job Raider runs one uvicorn worker.
# It lets long-lived routers detect successful Settings writes.
_settings_revision = 0
_settings_revision_lock = threading.Lock()

# Hostnames allowed for Settings ``ollama_host`` (decision 5, Step 2.6).
ALLOWED_OLLAMA_HOSTNAMES = frozenset(
    {"localhost", "127.0.0.1", "host.docker.internal", "ollama"}
)


class Provider(str, Enum):
    """Available LLM providers."""

    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GEMINI = "gemini"


class CloudProvider(str, Enum):
    """Cloud API providers used as Ollama fallbacks.

    ``NONE`` means local-only: when Ollama fails, do not call a cloud API.
    """

    NONE = "none"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ModelRouting(BaseModel):
    """Model routing configuration for a specific task type."""

    task_type: str = Field(description="Task type (selection, scoring, etc.)")
    primary_provider: Provider = Field(
        default=Provider.OLLAMA, description="Primary provider to use"
    )
    primary_model: str = Field(description="Primary model name")
    fallback_provider: Optional[Provider] = Field(
        default=None, description="Fallback provider (None = local-only)"
    )
    fallback_model: Optional[str] = Field(
        default=None, description="Fallback model name"
    )

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        """Validate task type is known."""
        valid_types = [t.value for t in TaskType]
        if v not in valid_types:
            raise ValueError(f"Invalid task_type: {v}. Must be one of {valid_types}")
        return v


class APIConfig(BaseModel):
    """API and service configuration."""

    anthropic_api_key: Optional[str] = Field(
        default=None, description="Anthropic API key"
    )
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key"
    )
    has_anthropic_key: bool = Field(
        default=False,
        description="True when an Anthropic key is stored (client-facing only)",
    )
    has_gemini_key: bool = Field(
        default=False,
        description="True when a Gemini key is stored (client-facing only)",
    )
    cloud_fallback_provider: CloudProvider = Field(
        default=CloudProvider.NONE,
        description=(
            "Cloud provider used when local Ollama fails. "
            "none = never send prompts to a cloud API"
        ),
    )
    ollama_host: str = Field(
        default="host.docker.internal:11434",
        description=(
            "Ollama host:port. Default reaches host-machine Ollama from a "
            "Docker Desktop backend. Use localhost:11434 only for a native "
            "venv/WSL API process."
        ),
    )

    @field_validator("anthropic_api_key", "gemini_api_key", mode="before")
    @classmethod
    def empty_key_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Treat blank API keys as unset so env vars can still apply.

        Args:
            v: Raw key value from JSON or construction.

        Returns:
            Stripped key, or None when blank.
        """
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip() if isinstance(v, str) else v

    @field_validator("ollama_host")
    @classmethod
    def validate_ollama_host(cls, v: str) -> str:
        """
        Validate Ollama host: http(s) only, host and port, allowlisted host.

        Allowed hosts: ``localhost``, ``127.0.0.1``, ``host.docker.internal``,
        and ``ollama`` (Compose service name).

        Args:
            v: Host string from settings (with or without scheme).

        Returns:
            Stripped host string, or the Docker Desktop default when empty.

        Raises:
            ValueError: When the host is not allowlisted or has a path/query.
        """
        if not v or not str(v).strip():
            return "host.docker.internal:11434"
        raw = str(v).strip()
        to_parse = raw if "://" in raw else f"http://{raw}"
        parsed = urlparse(to_parse)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("ollama_host must use http or https")
        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_OLLAMA_HOSTNAMES:
            allowed = ", ".join(sorted(ALLOWED_OLLAMA_HOSTNAMES))
            raise ValueError(f"ollama_host host must be one of: {allowed}")
        if (
            parsed.path not in ("", "/")
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ollama_host must be host:port only (no path or query)")
        if parsed.username or parsed.password:
            raise ValueError("ollama_host must not include credentials")
        return raw


class ModelParameters(BaseModel):
    """Default model generation parameters."""

    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Generation temperature"
    )
    max_tokens: int = Field(
        default=4096, ge=1, le=128000, description="Maximum tokens to generate"
    )
    top_p: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Nucleus sampling parameter"
    )
    top_k: int = Field(default=40, ge=1, le=100, description="Top-k sampling parameter")


class CostLimits(BaseModel):
    """Cost and usage limits."""

    max_api_cost_per_run: float = Field(
        default=5.0, ge=0.0, description="Maximum API cost per pipeline run (USD)"
    )
    enable_cache: bool = Field(
        default=True,
        description=(
            "Enable kind-A LLM response caching for allowlisted TaskTypes "
            "(validation, jd_extraction, resume_parsing)"
        ),
    )
    cache_ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")
    max_concurrent_requests: int = Field(
        default=2, ge=1, le=10, description="Max concurrent LLM requests"
    )
    enable_jd_llm_extract: bool = Field(
        default=False,
        description=(
            "When rule-based JD paste extraction finds no skills, optionally "
            "run LLM JD_EXTRACTION (cover-letter manual paste only)"
        ),
    )
    enable_company_mission: bool = Field(
        default=False,
        description=(
            "When generating a cover letter, optionally search and verify a "
            "short company-mission brief against JD facts (skip on ambiguity)"
        ),
    )
    enable_prompt_cache: bool = Field(
        default=False,
        description=(
            "Enable Anthropic prompt-prefix caching (kind B) on system prompts"
        ),
    )
    ollama_keep_alive: Optional[str] = Field(
        default=None,
        description=("Ollama keep_alive duration for loaded models (e.g. 5m, 30m, -1)"),
    )


class UserSettings(BaseModel):
    """Complete user settings configuration."""

    routing: Dict[str, ModelRouting] = Field(
        default_factory=dict, description="Model routing per task type"
    )
    api_config: APIConfig = Field(
        default_factory=APIConfig, description="API configuration"
    )
    model_params: ModelParameters = Field(
        default_factory=ModelParameters, description="Default model parameters"
    )
    cost_limits: CostLimits = Field(
        default_factory=CostLimits, description="Cost and usage limits"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )
    version: str = Field(default="1.0", description="Settings schema version")

    def get_routing_for_task(self, task_type: str) -> Optional[ModelRouting]:
        """Get routing configuration for a specific task type.

        Args:
            task_type: Task type key (for example ``cover_letter_writing``).

        Returns:
            Routing for that task, or None when unset.
        """
        return self.routing.get(task_type)


def for_client(settings: UserSettings) -> UserSettings:
    """
    Return a deep copy safe to send to API clients (no key strings).

    Sets ``has_anthropic_key`` / ``has_gemini_key`` from stored keys, then
    clears the key fields so JSON responses never include secrets.

    Args:
        settings: Settings loaded from storage (may include key material).

    Returns:
        Copy with keys cleared and has_* flags set.
    """
    public = settings.model_copy(deep=True)
    public.api_config.has_anthropic_key = bool(settings.api_config.anthropic_api_key)
    public.api_config.has_gemini_key = bool(settings.api_config.gemini_api_key)
    public.api_config.anthropic_api_key = None
    public.api_config.gemini_api_key = None
    return public


def merge_preserving_api_keys(
    current: UserSettings, incoming: UserSettings
) -> UserSettings:
    """
    Merge incoming settings while keeping stored API keys when omitted.

    Clients that only send ``has_*`` flags (or null keys) must not wipe
    secrets already on disk.

    Args:
        current: Settings currently stored.
        incoming: Settings from the client PUT body.

    Returns:
        Merged settings ready to save (with keys filled from current when
        the client did not supply a new key).
    """
    merged = incoming.model_copy(deep=True)
    if not merged.api_config.anthropic_api_key:
        merged.api_config.anthropic_api_key = current.api_config.anthropic_api_key
    if not merged.api_config.gemini_api_key:
        merged.api_config.gemini_api_key = current.api_config.gemini_api_key
    # has_* are client-facing only; do not persist as source of truth
    merged.api_config.has_anthropic_key = False
    merged.api_config.has_gemini_key = False
    return merged


class SettingsStorage:
    """Storage manager for user settings."""

    def __init__(self, settings_dir: Path = None):
        """
        Initialize settings storage.

        Args:
            settings_dir: Directory for settings file (default: data/settings/)
        """
        if settings_dir is None:
            settings_dir = Path("data/settings")
        self.settings_dir = settings_dir
        self.settings_file = self.settings_dir / "user_settings.json"
        self.settings_dir.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> UserSettings:
        """
        Load settings from file.

        When the only validation failure is a disallowed ``ollama_host``,
        replace that host with the default and keep every other stored
        field (including API keys and routing). Other load errors still
        fall back to defaults.

        Returns:
            UserSettings with loaded values or defaults.
        """
        if not self.settings_file.exists():
            return self._get_default_settings()

        try:
            with open(self.settings_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
            return self._get_default_settings()

        try:
            return UserSettings(**data)
        except ValidationError as exc:
            if self._is_ollama_host_only_error(exc):
                bad_host = None
                if isinstance(data, dict):
                    api = data.get("api_config")
                    if isinstance(api, dict):
                        bad_host = api.get("ollama_host")
                        api["ollama_host"] = "host.docker.internal:11434"
                _logger.warning(
                    "Stored ollama_host %r is not allowed; "
                    "using host.docker.internal:11434 and keeping other settings",
                    bad_host,
                )
                try:
                    return UserSettings(**data)
                except Exception as e:
                    print(f"Error loading settings: {e}")
                    return self._get_default_settings()
            print(f"Error loading settings: {exc}")
            return self._get_default_settings()
        except Exception as e:
            print(f"Error loading settings: {e}")
            return self._get_default_settings()

    @staticmethod
    def _is_ollama_host_only_error(exc: ValidationError) -> bool:
        """
        Return True when every validation error is on ``api_config.ollama_host``.

        Args:
            exc: Pydantic validation error from constructing ``UserSettings``.

        Returns:
            True when the only invalid field is the Ollama host.
        """
        errors = exc.errors()
        if not errors:
            return False
        for err in errors:
            loc = err.get("loc") or ()
            if tuple(loc) != ("api_config", "ollama_host"):
                return False
        return True

    def save_settings(self, settings: UserSettings) -> None:
        """
        Save settings to file.

        Args:
            settings: UserSettings to save
        """
        settings.updated_at = datetime.now()
        with open(self.settings_file, "w") as f:
            json.dump(settings.model_dump(), f, indent=2, default=str)
        global _settings_revision
        with _settings_revision_lock:
            _settings_revision += 1

    def reset_settings(self) -> UserSettings:
        """
        Reset settings to defaults and save.

        Returns:
            Default UserSettings
        """
        defaults = self._get_default_settings()
        self.save_settings(defaults)
        return defaults

    def _get_default_settings(self) -> UserSettings:
        """
        Get default settings configuration.

        Returns:
            Default UserSettings mirrored from LLMRouter.DEFAULT_ROUTES
            (recommended Ollama defaults: qwen2.5:3b / qwen2.5:7b).
        """
        from ..llm.router import LLMRouter

        default_routing: Dict[str, ModelRouting] = {}
        for task_type, route in LLMRouter.DEFAULT_ROUTES.items():
            fallback_provider = None
            if route.fallback_provider:
                try:
                    fallback_provider = Provider(route.fallback_provider)
                except ValueError:
                    fallback_provider = None
            default_routing[task_type.value] = ModelRouting(
                task_type=task_type.value,
                primary_provider=Provider(route.primary_provider),
                primary_model=route.primary_model,
                fallback_provider=fallback_provider,
                fallback_model=route.fallback_model,
            )

        return UserSettings(
            routing=default_routing,
            api_config=APIConfig(),
            model_params=ModelParameters(),
            cost_limits=CostLimits(),
        )


# Global storage instance
_storage: Optional[SettingsStorage] = None


def get_settings_revision() -> int:
    """
    Return the process-local revision of successfully saved Settings.

    Returns:
        Monotonic Settings revision for this process.
    """
    with _settings_revision_lock:
        return _settings_revision


def get_storage() -> SettingsStorage:
    """Get global settings storage instance."""
    global _storage
    if _storage is None:
        _storage = SettingsStorage()
    return _storage
