"""
Job Raider - Configuration Loader

Loads and merges configuration from YAML files with user settings.

Author: Job Raider
Date: 2026-04-24
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..api.settings import ModelRouting, Provider, UserSettings


class ConfigLoader:
    """Load and merge configuration from YAML files and user settings."""

    def __init__(self, config_dir: Path = None):
        """
        Initialize config loader.

        Args:
            config_dir: Directory containing config files (default: apps/backend-py/config/)
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "config"
        self.config_dir = config_dir
        self.model_config_path = self.config_dir / "model_config.yaml"

    def load_model_config(self) -> Dict[str, Any]:
        """
        Load model configuration from YAML file.

        Returns:
            Dictionary with model configuration
        """
        if not self.model_config_path.exists():
            return {}

        with open(self.model_config_path, "r") as f:
            return yaml.safe_load(f)

    def get_available_models(self) -> Dict[str, List[str]]:
        """
        Get list of available models by provider.

        Returns:
            Dict mapping provider names to lists of model names
        """
        config = self.load_model_config()
        models = {"anthropic": [], "ollama": []}

        if "models" in config:
            for provider_name, provider_config in config["models"].items():
                provider = provider_name.lower()
                if provider in models and "models" in provider_config:
                    models[provider] = list(provider_config["models"].keys())

        return models

    def get_model_info(self, provider: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific model.

        Args:
            provider: Provider name (anthropic or ollama)
            model: Model name

        Returns:
            Model info dict or None if not found
        """
        config = self.load_model_config()

        if "models" not in config:
            return None

        provider_config = config["models"].get(provider)
        if not provider_config or "models" not in provider_config:
            return None

        return provider_config["models"].get(model)

    def merge_with_user_settings(
        self, config: Dict[str, Any], settings: UserSettings
    ) -> Dict[str, Any]:
        """
        Merge YAML config with user settings.

        User settings take precedence over YAML defaults.

        Args:
            config: Base configuration from YAML
            settings: User settings to merge

        Returns:
            Merged configuration dictionary
        """
        merged = config.copy()

        # Update API configuration
        if "models" not in merged:
            merged["models"] = {}

        # Update Anthropic config with user API key
        if "anthropic" not in merged["models"]:
            merged["models"]["anthropic"] = {}
        if settings.api_config.anthropic_api_key:
            merged["models"]["anthropic"][
                "api_key"
            ] = settings.api_config.anthropic_api_key

        # Update Ollama config with user host
        if "ollama" not in merged["models"]:
            merged["models"]["ollama"] = {}
        merged["models"]["ollama"]["host"] = settings.api_config.ollama_host

        # Update router configuration with user routing preferences
        if "router" not in merged:
            merged["router"] = {"strategies": {}}

        router_strategies = merged["router"]["strategies"]
        for task_type, routing in settings.routing.items():
            strategy = {
                "primary": routing.primary_provider.value,
                "model": routing.primary_model,
                "fallback": routing.fallback_provider.value,
                "fallback_model": routing.fallback_model,
            }
            router_strategies[task_type] = strategy

        # Update cost optimization settings
        if "router" not in merged:
            merged["router"] = {}
        if "cost_optimization" not in merged["router"]:
            merged["router"]["cost_optimization"] = {}

        merged["router"]["cost_optimization"]["prefer_local"] = True
        merged["router"]["cost_optimization"][
            "max_api_cost_per_run"
        ] = settings.cost_limits.max_api_cost_per_run
        merged["router"]["cost_optimization"][
            "cache_enabled"
        ] = settings.cost_limits.enable_cache
        merged["router"]["cost_optimization"][
            "cache_ttl"
        ] = settings.cost_limits.cache_ttl

        # Update cache settings
        if "cache" not in merged:
            merged["cache"] = {}
        merged["cache"]["enabled"] = settings.cost_limits.enable_cache
        merged["cache"]["ttl"] = settings.cost_limits.cache_ttl

        # Update rate limits
        if "rate_limits" not in merged:
            merged["rate_limits"] = {}
        merged["rate_limits"]["ollama"] = {
            "concurrent_requests": settings.cost_limits.max_concurrent_requests
        }

        # Update model parameters
        if "model_params" not in merged:
            merged["model_params"] = {}

        merged["model_params"] = {
            "temperature": settings.model_params.temperature,
            "max_tokens": settings.model_params.max_tokens,
            "top_p": settings.model_params.top_p,
            "top_k": settings.model_params.top_k,
        }

        return merged

    def get_default_routing_from_config(self) -> Dict[str, Dict[str, str]]:
        """
        Get default routing configuration from YAML file.

        Returns:
            Dict mapping task types to provider/model pairs
        """
        config = self.load_model_config()
        routing = {}

        if "router" in config and "strategies" in config["router"]:
            for task_type, strategy in config["router"]["strategies"].items():
                routing[task_type] = {
                    "primary_provider": strategy.get("primary"),
                    "primary_model": strategy.get("model"),
                    "fallback_provider": strategy.get("fallback"),
                    "fallback_model": strategy.get("fallback_model"),
                }

        return routing


# Global config loader instance
_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get global config loader instance."""
    global _loader
    if _loader is None:
        _loader = ConfigLoader()
    return _loader
