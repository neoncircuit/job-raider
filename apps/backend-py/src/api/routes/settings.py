"""
Job Raider - Settings API Routes

API endpoints for managing user-configurable settings.

Author: Job Raider
Date: 2026-04-24
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...api.ollama_models import (
    RECOMMENDED_OLLAMA_LARGE,
    RECOMMENDED_OLLAMA_SMALL,
    apply_ollama_tier_models,
    list_installed_ollama_models,
    resolve_effective_ollama_host,
)
from ...api.settings import UserSettings, get_storage
from ...config.loader import get_config_loader
from ...utils.logger import Components, get_logger

router = APIRouter()
logger = get_logger(Components.SCRAPERS)


class OllamaTierDefaults(BaseModel):
    """Request body for applying small/large Ollama model defaults."""

    small_model: str = Field(
        default=RECOMMENDED_OLLAMA_SMALL,
        description="Primary model for small/fast tasks",
    )
    large_model: str = Field(
        default=RECOMMENDED_OLLAMA_LARGE,
        description="Primary model for large/quality tasks",
    )


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


@router.post("/ollama-defaults", response_model=UserSettings)
async def apply_ollama_defaults(body: OllamaTierDefaults) -> UserSettings:
    """
    Apply small/large Ollama model choices across task routing and save.

    Updates every Ollama-primary tier task to use the given models.
    Recommended documented defaults remain qwen2.5:3b / qwen2.5:7b;
    any installed model name may be supplied.

    Args:
        body: Small and large model names to apply.

    Returns:
        Updated settings after save.
    """
    storage = get_storage()
    settings = storage.load_settings()
    settings.routing = apply_ollama_tier_models(
        settings.routing,
        body.small_model.strip(),
        body.large_model.strip(),
        cloud_fallback=settings.api_config.cloud_fallback_provider,
    )
    storage.save_settings(settings)
    logger.info(
        "Applied Ollama defaults: small=%s large=%s",
        body.small_model,
        body.large_model,
    )
    return settings


@router.get("/models", response_model=Dict[str, Any])
async def get_available_models() -> Dict[str, Any]:
    """
    Get available models by provider.

    Merges YAML catalog entries with models installed in the local Ollama
    instance (when reachable). Includes recommended small/large defaults.

    Returns:
        Dict with provider lists plus ``recommended`` and ``ollama_installed``.
    """
    loader = get_config_loader()
    storage = get_storage()
    settings = storage.load_settings()
    catalog = loader.get_available_models()

    effective_host = resolve_effective_ollama_host(settings.api_config.ollama_host)
    installed = list_installed_ollama_models(effective_host)
    catalog_ollama = list(catalog.get("ollama", []))
    merged_ollama = sorted(set(catalog_ollama) | set(installed))

    return {
        **catalog,
        "ollama": merged_ollama,
        "ollama_installed": installed,
        "ollama_host_effective": effective_host,
        "recommended": {
            "small": RECOMMENDED_OLLAMA_SMALL,
            "large": RECOMMENDED_OLLAMA_LARGE,
        },
    }


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


def _allowed_models_for_provider(
    provider: str,
    catalog: Dict[str, List[str]],
    installed_ollama: List[str],
) -> Optional[List[str]]:
    """
    Build the allowlist used during settings validation for a provider.

    Args:
        provider: Provider key (ollama, anthropic, ...).
        catalog: Models from YAML config.
        installed_ollama: Live Ollama tags.

    Returns:
        Combined allowlist, or None when the provider has no catalog entry
        (skip strict checks).
    """
    if provider not in catalog and provider != "ollama":
        return None
    base = list(catalog.get(provider, []))
    if provider == "ollama":
        return sorted(set(base) | set(installed_ollama))
    return base


@router.post("/validate", response_model=Dict[str, Any])
async def validate_settings(settings: UserSettings) -> Dict[str, Any]:
    """
    Validate settings without saving them.

    Checks if API keys are valid, models exist, and configuration is consistent.
    Ollama models may be either YAML-catalogued or installed locally.

    Args:
        settings: Settings to validate

    Returns:
        Validation results with success status and any errors/warnings
    """
    loader = get_config_loader()
    results: Dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

    catalog = loader.get_available_models()
    effective_host = resolve_effective_ollama_host(settings.api_config.ollama_host)
    installed = list_installed_ollama_models(effective_host)
    if not installed:
        results["warnings"].append(
            "Ollama is unreachable or has no models; installed-model checks skipped."
        )

    for task_type, routing in settings.routing.items():
        primary_provider = routing.primary_provider.value
        allowed = _allowed_models_for_provider(primary_provider, catalog, installed)
        if allowed is not None and routing.primary_model not in allowed:
            if primary_provider == "ollama" and not installed and routing.primary_model:
                results["warnings"].append(
                    f"{task_type}: Primary model '{routing.primary_model}' "
                    "could not be verified (Ollama unreachable)."
                )
            else:
                results["errors"].append(
                    f"{task_type}: Primary model '{routing.primary_model}' "
                    f"not found for {primary_provider}"
                )
                results["valid"] = False

        if routing.fallback_provider and routing.fallback_model:
            fallback_provider = routing.fallback_provider.value
            allowed_fb = _allowed_models_for_provider(
                fallback_provider, catalog, installed
            )
            if allowed_fb is not None and routing.fallback_model not in allowed_fb:
                if (
                    fallback_provider == "ollama"
                    and not installed
                    and routing.fallback_model
                ):
                    results["warnings"].append(
                        f"{task_type}: Fallback model '{routing.fallback_model}' "
                        "could not be verified (Ollama unreachable)."
                    )
                else:
                    results["errors"].append(
                        f"{task_type}: Fallback model '{routing.fallback_model}' "
                        f"not found for {fallback_provider}"
                    )
                    results["valid"] = False

    host_without_scheme = settings.api_config.ollama_host.replace(
        "http://", ""
    ).replace("https://", "")
    if settings.api_config.ollama_host and ":" not in host_without_scheme:
        results["warnings"].append(
            "Ollama host should be in format 'host:port' (e.g., 'host.docker.internal:11434')"
        )

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
    Get default routing configuration from YAML.

    Returns:
        Default routing map keyed by task type.
    """
    loader = get_config_loader()
    return loader.get_default_routing_from_config()
