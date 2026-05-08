"""
Job Raider - Settings State Management

Manages settings persistence in Streamlit session state and localStorage.

Author: Job Raider
Date: 2026-04-24
"""

import streamlit as st

from src.api.client import get_api_client


def load_settings_to_session() -> dict:
    """
    Load settings from backend to session state.

    Returns:
        Settings dictionary or empty dict if load fails
    """
    if "_settings" not in st.session_state:
        try:
            client = get_api_client()
            settings = client.get_settings()
            st.session_state._settings = settings
        except Exception:
            st.session_state._settings = {}

    return st.session_state.get("_settings", {})


def save_settings_to_session(settings: dict) -> None:
    """
    Save settings to session state and backend.

    Args:
        settings: Settings dictionary to save
    """
    try:
        client = get_api_client()
        updated = client.update_settings(settings)
        st.session_state._settings = updated
    except Exception as e:
        st.error(f"Failed to save settings: {e}")


def get_setting(key: str, default=None):
    """
    Get a specific setting value.

    Args:
        key: Setting key (supports dot notation for nested keys)
        default: Default value if key not found

    Returns:
        Setting value or default
    """
    settings = load_settings_to_session()

    # Support dot notation for nested keys
    keys = key.split(".")
    value = settings

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value if value is not None else default


def get_routing_for_task(task_type: str) -> dict:
    """
    Get routing configuration for a specific task type.

    Args:
        task_type: Task type (selection, scoring, etc.)

    Returns:
        Routing configuration dict or empty dict
    """
    settings = load_settings_to_session()
    routing = settings.get("routing", {})
    return routing.get(task_type, {})


def get_model_parameters() -> dict:
    """
    Get current model parameters.

    Returns:
        Model parameters dict with defaults
    """
    settings = load_settings_to_session()
    return settings.get("model_params", {
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 0.9,
        "top_k": 40,
    })


def get_api_config() -> dict:
    """
    Get API configuration.

    Returns:
        API config dict
    """
    settings = load_settings_to_session()
    return settings.get("api_config", {
        "anthropic_api_key": None,
        "ollama_host": "localhost:11434",
    })
