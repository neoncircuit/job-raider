"""
Agent Configuration Loader for Job Raider Multi-Agent System

Provides utilities for loading and accessing agent configuration
from the agent_config.yaml file.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class AgentConfig:
    """
    Agent configuration loader and manager.

    Provides access to agent configuration settings with environment-specific
    overrides and validation.
    """

    def __init__(
        self, config_path: Optional[str] = None, environment: Optional[str] = None
    ):
        """
        Initialize the agent configuration loader.

        Args:
            config_path: Optional path to agent config file
            environment: Optional environment name (development, production, None for no overrides)
        """
        # Allow None environment to skip overrides
        if environment is None:
            self.environment = None
        else:
            self.environment = environment or os.getenv("ENVIRONMENT", "development")

        self.config_path = config_path or self._find_config_path()
        self._config: Optional[Dict[str, Any]] = None

        logger.info(f"AgentConfig initialized with environment: {self.environment}")

    def _find_config_path(self) -> str:
        """
        Find the agent configuration file.

        Returns:
            Path to agent config file
        """
        # Try relative to current file
        current_dir = Path(__file__).parent
        config_dir = current_dir.parent.parent / "config"
        config_path = config_dir / "agent_config.yaml"

        if config_path.exists():
            return str(config_path)

        # Fallback to default locations (cwd may be the backend root or repo root)
        for fallback in (
            Path("config/agent_config.yaml"),
            Path("apps/backend-py/config/agent_config.yaml"),
        ):
            if fallback.exists():
                return str(fallback)

        raise FileNotFoundError(f"Agent configuration file not found at {config_path}")

    def load_config(self) -> Dict[str, Any]:
        """
        Load agent configuration from file.

        Returns:
            Configuration dictionary with environment-specific overrides
        """
        if self._config is not None:
            return self._config

        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            # Apply environment-specific overrides
            if self.environment in config.get("environments", {}):
                env_overrides = config["environments"][self.environment]
                config = self._apply_overrides(config, env_overrides)

            self._config = config
            logger.info(f"Agent configuration loaded from {self.config_path}")
            return config

        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

    def _apply_overrides(
        self, base_config: Dict[str, Any], overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply environment-specific overrides to base configuration.

        Args:
            base_config: Base configuration dictionary
            overrides: Environment-specific overrides

        Returns:
            Merged configuration dictionary
        """
        import copy

        # Deep copy base config to avoid mutation
        result = copy.deepcopy(base_config)

        # Apply overrides recursively
        def apply_recursive(
            base: Dict[str, Any], override: Dict[str, Any]
        ) -> Dict[str, Any]:
            for key, value in override.items():
                if (
                    key in base
                    and isinstance(base[key], dict)
                    and isinstance(value, dict)
                ):
                    base[key] = apply_recursive(base[key], value)
                else:
                    base[key] = value
            return base

        # Remove environments key before applying (don't override it)
        if "environments" in result:
            del result["environments"]

        result = apply_recursive(result, overrides)
        return result

    def get_coordinator_config(self) -> Dict[str, Any]:
        """
        Get coordinator-specific configuration.

        Returns:
            Coordinator configuration dictionary
        """
        config = self.load_config()
        return config.get("coordinator", {})

    def get_communication_config(self) -> Dict[str, Any]:
        """
        Get communication bus-specific configuration.

        Returns:
            Communication configuration dictionary
        """
        config = self.load_config()
        return config.get("communication", {})

    def get_agents_config(self) -> Dict[str, Any]:
        """
        Get general agent configuration.

        Returns:
            Agent configuration dictionary
        """
        config = self.load_config()
        return config.get("agents", {})

    def get_career_coach_config(self) -> Dict[str, Any]:
        """
        Get career coach-specific configuration.

        Returns:
            Career coach configuration dictionary
        """
        config = self.load_config()
        return config.get("career_coach", {})

    def get_pipeline_config(self) -> Dict[str, Any]:
        """
        Get pipeline orchestration configuration.

        Returns:
            Pipeline configuration dictionary
        """
        config = self.load_config()
        return config.get("pipeline", {})

    def get_value(self, *path: str, default: Any = None) -> Any:
        """
        Get a specific configuration value by path.

        Args:
            *path: Configuration path segments (e.g., "coordinator", "max_concurrent_pipelines")
            default: Default value if path not found

        Returns:
            Configuration value or default

        Example:
            config.get_value("coordinator", "max_concurrent_pipelines", default=3)
        """
        config = self.load_config()
        value = config

        for key in path:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration from file.

        Returns:
            Reloaded configuration dictionary
        """
        self._config = None
        return self.load_config()


# Global configuration instance
_global_config: Optional[AgentConfig] = None


def get_agent_config(
    config_path: Optional[str] = None, environment: Optional[str] = None
) -> AgentConfig:
    """
    Get global agent configuration instance.

    Args:
        config_path: Optional path to agent config file
        environment: Optional environment name

    Returns:
        AgentConfig instance
    """
    global _global_config

    if _global_config is None:
        _global_config = AgentConfig(config_path, environment)

    return _global_config


def reset_agent_config():
    """Reset global agent configuration instance (mainly for testing)."""
    global _global_config
    _global_config = None
