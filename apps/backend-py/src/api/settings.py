"""
Job Raider - Settings Management

Provides models and storage for user-configurable settings including
model routing, API credentials, and parameters.

Author: Job Raider
Date: 2026-04-24
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from ..llm.router import TaskType


class Provider(str, Enum):
    """Available LLM providers."""

    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class ModelRouting(BaseModel):
    """Model routing configuration for a specific task type."""

    task_type: str = Field(description="Task type (selection, scoring, etc.)")
    primary_provider: Provider = Field(
        default=Provider.OLLAMA, description="Primary provider to use"
    )
    primary_model: str = Field(description="Primary model name")
    fallback_provider: Provider = Field(
        default=Provider.ANTHROPIC, description="Fallback provider"
    )
    fallback_model: str = Field(description="Fallback model name")

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
    ollama_host: str = Field(
        default="localhost:11434", description="Ollama service host:port"
    )

    @field_validator("ollama_host")
    @classmethod
    def validate_ollama_host(cls, v: str) -> str:
        """Validate Ollama host format."""
        if not v:
            return "localhost:11434"
        return v


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
    enable_cache: bool = Field(default=True, description="Enable response caching")
    cache_ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")
    max_concurrent_requests: int = Field(
        default=2, ge=1, le=10, description="Max concurrent LLM requests"
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
        """Get routing configuration for a specific task type."""
        return self.routing.get(task_type)


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

        Returns:
            UserSettings with loaded values or defaults
        """
        if not self.settings_file.exists():
            return self._get_default_settings()

        try:
            with open(self.settings_file, "r") as f:
                data = json.load(f)
            return UserSettings(**data)
        except Exception as e:
            # Log error but return defaults
            print(f"Error loading settings: {e}")
            return self._get_default_settings()

    def save_settings(self, settings: UserSettings) -> None:
        """
        Save settings to file.

        Args:
            settings: UserSettings to save
        """
        settings.updated_at = datetime.now()
        with open(self.settings_file, "w") as f:
            json.dump(settings.model_dump(), f, indent=2, default=str)

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
            Default UserSettings
        """
        # Default routing configurations
        default_routing = {
            "selection": ModelRouting(
                task_type="selection",
                primary_provider=Provider.OLLAMA,
                primary_model="qwen2.5:3b",
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-haiku-4-5-20251001",
            ),
            "scoring": ModelRouting(
                task_type="scoring",
                primary_provider=Provider.OLLAMA,
                primary_model="qwen2.5:3b",
                fallback_provider=Provider.OLLAMA,
                fallback_model="gemma3:4b",
            ),
            "jd_extraction": ModelRouting(
                task_type="jd_extraction",
                primary_provider=Provider.OLLAMA,
                primary_model="qwen2.5:7b",
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-sonnet-4-6",
            ),
            "resume_writing": ModelRouting(
                task_type="resume_writing",
                primary_provider=Provider.OLLAMA,
                primary_model="qwen2.5:7b",
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-sonnet-4-6",
            ),
            "resume_parsing": ModelRouting(
                task_type="resume_parsing",
                primary_provider=Provider.OLLAMA,
                primary_model="qwen2.5:7b",
                fallback_provider=Provider.ANTHROPIC,
                fallback_model="claude-sonnet-4-6",
            ),
        }

        return UserSettings(
            routing=default_routing,
            api_config=APIConfig(),
            model_params=ModelParameters(),
            cost_limits=CostLimits(),
        )


# Global storage instance
_storage: Optional[SettingsStorage] = None


def get_storage() -> SettingsStorage:
    """Get global settings storage instance."""
    global _storage
    if _storage is None:
        _storage = SettingsStorage()
    return _storage
