"""
Job Raider - Settings API Routes

API endpoints for managing user-configurable settings.

Author: Job Raider
Date: 2026-04-24
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ...api.settings import UserSettings, get_storage
from ...config.loader import get_config_loader
from ...utils.logger import Components, get_logger

router = APIRouter()
logger = get_logger(Components.SCRAPERS)


@router.get("/", response_model=UserSettings)
async def get_settings() -> UserSettings:
    """
    Get current user settings.

    Returns the complete user settings configuration including
    model routing, API configuration, parameters, and cost limits.
    """
    storage = get_storage()
    return storage.load_settings()


@router.put("/", response_model=UserSettings)
async def update_settings(settings: UserSettings) -> UserSettings:
    """
    Update user settings.

    Saves the provided settings to persistent storage.

    Args:
        settings: New settings configuration

    Returns:
        Updated settings (as saved)
    """
    storage = get_storage()
    storage.save_settings(settings)
    logger.info(f"Settings updated at {settings.updated_at}")
    return settings


@router.post("/reset", response_model=UserSettings)
async def reset_settings() -> UserSettings:
    """
    Reset settings to defaults.

    Resets all settings to their default values and saves them.

    Returns:
        Default settings
    """
    storage = get_storage()
    defaults = storage.reset_settings()
    logger.info("Settings reset to defaults")
    return defaults


@router.get("/models", response_model=Dict[str, list])
async def get_available_models() -> Dict[str, list]:
    """
    Get list of available models by provider.

    Returns models defined in model_config.yaml, organized by provider.

    Returns:
        Dict with provider names as keys and lists of model names as values
    """
    loader = get_config_loader()
    return loader.get_available_models()


@router.get("/models/{provider}/{model}", response_model=Dict[str, Any])
async def get_model_info(provider: str, model: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific model.

    Args:
        provider: Provider name (anthropic or ollama)
        model: Model name

    Returns:
        Model information including parameters, use cases, etc.

    Raises:
        HTTPException: If model not found
    """
    loader = get_config_loader()
    info = loader.get_model_info(provider, model)

    if info is None:
        raise HTTPException(
            status_code=404, detail=f"Model {model} not found for provider {provider}"
        )

    return info


@router.post("/validate", response_model=Dict[str, Any])
async def validate_settings(settings: UserSettings) -> Dict[str, Any]:
    """
    Validate settings without saving them.

    Checks if API keys are valid, models exist, and configuration is consistent.

    Args:
        settings: Settings to validate

    Returns:
        Validation results with success status and any errors/warnings
    """
    loader = get_config_loader()
    results = {"valid": True, "errors": [], "warnings": []}

    # Validate model names exist
    available_models = loader.get_available_models()

    for task_type, routing in settings.routing.items():
        # Check primary model exists
        primary_provider = routing.primary_provider.value
        if primary_provider in available_models:
            if routing.primary_model not in available_models[primary_provider]:
                results["errors"].append(
                    f"{task_type}: Primary model '{routing.primary_model}' not found for {primary_provider}"
                )
                results["valid"] = False

        # Check fallback model exists
        fallback_provider = routing.fallback_provider.value
        if fallback_provider in available_models:
            if routing.fallback_model not in available_models[fallback_provider]:
                results["errors"].append(
                    f"{task_type}: Fallback model '{routing.fallback_model}' not found for {fallback_provider}"
                )
                results["valid"] = False

    # Validate Ollama host format
    if settings.api_config.ollama_host and ":" not in settings.api_config.ollama_host:
        results["warnings"].append(
            "Ollama host should be in format 'host:port' (e.g., 'localhost:11434')"
        )

    # Validate cost limits
    if settings.cost_limits.max_api_cost_per_run < 0:
        results["errors"].append("max_api_cost_per_run cannot be negative")
        results["valid"] = False

    if settings.cost_limits.cache_ttl < 0:
        results["errors"].append("cache_ttl cannot be negative")
        results["valid"] = False

    logger.info(f"Settings validation: {'PASSED' if results['valid'] else 'FAILED'}")
    return results


@router.get("/config/merged", response_model=Dict[str, Any])
async def get_merged_config() -> Dict[str, Any]:
    """
    Get merged configuration (YAML + user settings).

    Returns the final configuration that would be used by the application,
    merging defaults from model_config.yaml with user settings.

    Returns:
        Merged configuration dictionary
    """
    loader = get_config_loader()
    storage = get_storage()

    yaml_config = loader.load_model_config()
    user_settings = storage.load_settings()

    return loader.merge_with_user_settings(yaml_config, user_settings)


@router.get("/config/default-routing", response_model=Dict[str, Dict[str, str]])
async def get_default_routing() -> Dict[str, Dict[str, str]]:
    """
    Get default routing from model_config.yaml.

    Returns the routing configuration as defined in the YAML file,
    before applying user settings.

    Returns:
        Default routing configuration
    """
    loader = get_config_loader()
    return loader.get_default_routing_from_config()
