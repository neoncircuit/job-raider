"""
Job Raider - Settings Page

Streamlit page for configuring model routing, API credentials,
and application settings.

Author: Job Raider
Date: 2026-04-24
"""

import streamlit as st

from src.api.client import APIClient, APIError, ConnectionError
from src.utils.session_state import get_api_client


def render() -> None:
    """Render the settings page."""
    st.title("⚙️ Settings")
    st.caption("Configure model routing, API credentials, and application preferences")

    client = get_api_client()

    # Load current settings
    try:
        settings = client.get_settings()
    except ConnectionError:
        st.error("Backend unreachable. Cannot load settings.")
        st.stop()
    except APIError as e:
        st.error(f"Failed to load settings: {e.detail}")
        st.stop()

    # Initialize session state for settings form
    if "_settings_form_submitted" not in st.session_state:
        st.session_state._settings_form_submitted = False

    # Settings organized into sections
    with st.container(border=True):
        st.subheader("Model Routing")

        st.markdown("Configure which models to use for different task types:")

        # Display routing configuration for each task type
        routing = settings.get("routing", {})

        for task_type, routing_config in routing.items():
            with st.expander(f"**{task_type.replace('_', ' ').title()}**", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Primary Model**")
                    st.text_input(
                        "Provider",
                        value=routing_config.get("primary_provider", "ollama"),
                        key=f"primary_provider_{task_type}",
                        disabled=True,
                    )
                    st.text_input(
                        "Model",
                        value=routing_config.get("primary_model", ""),
                        key=f"primary_model_{task_type}",
                        disabled=True,
                    )

                with col2:
                    st.markdown("**Fallback Model**")
                    st.text_input(
                        "Provider",
                        value=routing_config.get("fallback_provider", "anthropic"),
                        key=f"fallback_provider_{task_type}",
                        disabled=True,
                    )
                    st.text_input(
                        "Model",
                        value=routing_config.get("fallback_model", ""),
                        key=f"fallback_model_{task_type}",
                        disabled=True,
                    )

                st.info("💡 To change model routing, use the API or edit the settings file directly.")

    st.divider()

    # API Configuration
    with st.container(border=True):
        st.subheader("API Configuration")

        api_config = settings.get("api_config", {})

        col1, col2 = st.columns(2)

        with col1:
            anthropic_key = st.text_input(
                "Anthropic API Key",
                value=api_config.get("anthropic_api_key", ""),
                type="password",
                help="Enter your Anthropic API key for Claude models",
                key="settings_anthropic_key",
            )

        with col2:
            ollama_host = st.text_input(
                "Ollama Host",
                value=api_config.get("ollama_host", "localhost:11434"),
                help="Ollama service host:port",
                key="settings_ollama_host",
            )

    st.divider()

    # Model Parameters
    with st.container(border=True):
        st.subheader("Model Parameters")

        model_params = settings.get("model_params", {})

        col1, col2, col3 = st.columns(3)

        with col1:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=model_params.get("temperature", 0.7),
                step=0.1,
                help="Higher = more creative, Lower = more focused",
                key="settings_temperature",
            )

        with col2:
            max_tokens = st.number_input(
                "Max Tokens",
                min_value=1,
                max_value=128000,
                value=model_params.get("max_tokens", 4096),
                step=100,
                help="Maximum tokens to generate",
                key="settings_max_tokens",
            )

        with col3:
            top_p = st.slider(
                "Top P",
                min_value=0.0,
                max_value=1.0,
                value=model_params.get("top_p", 0.9),
                step=0.05,
                help="Nucleus sampling parameter",
                key="settings_top_p",
            )

    st.divider()

    with st.form("settings_save_form", clear_on_submit=False):
        # Cost Limits
        st.subheader("Cost & Usage Limits")

        cost_limits = settings.get("cost_limits", {})

        col1, col2, col3 = st.columns(3)

        with col1:
            max_cost = st.number_input(
                "Max API Cost Per Run ($)",
                min_value=0.0,
                max_value=100.0,
                value=cost_limits.get("max_api_cost_per_run", 5.0),
                step=0.5,
                help="Maximum API cost per pipeline run in USD",
                key="settings_max_cost",
            )

        with col2:
            enable_cache = st.checkbox(
                "Enable Response Caching",
                value=cost_limits.get("enable_cache", True),
                help="Cache LLM responses to reduce costs",
                key="settings_cache",
            )

        with col3:
            cache_ttl = st.number_input(
                "Cache TTL (seconds)",
                min_value=0,
                max_value=86400,
                value=cost_limits.get("cache_ttl", 3600),
                step=60,
                help="How long to cache responses (0 = no cache)",
                key="settings_cache_ttl",
            )

        st.divider()

        # Actions
        col1, col2, col3 = st.columns(3)

        with col1:
            submitted = st.form_submit_button("Save Settings", use_container_width=True)

        with col2:
            pass  # Reset button must live outside the form

        with col3:
            pass  # Validate button must live outside the form

        if submitted:
            updated_settings = settings.copy()

            updated_settings["api_config"]["anthropic_api_key"] = anthropic_key or None
            updated_settings["api_config"]["ollama_host"] = ollama_host

            updated_settings["model_params"]["temperature"] = temperature
            updated_settings["model_params"]["max_tokens"] = max_tokens
            updated_settings["model_params"]["top_p"] = top_p

            updated_settings["cost_limits"]["max_api_cost_per_run"] = max_cost
            updated_settings["cost_limits"]["enable_cache"] = enable_cache
            updated_settings["cost_limits"]["cache_ttl"] = cache_ttl

            try:
                client.update_settings(updated_settings)
                st.success("Settings saved successfully!")
                st.rerun()
            except APIError as e:
                st.error(f"Failed to save settings: {e.detail}")

    st.divider()

    # Buttons that cannot live inside a form (they trigger navigation)
    col1, col2, col3 = st.columns(3)

    with col2:
        if st.button("Reset to Defaults", use_container_width=True, key="settings_reset"):
            try:
                defaults = client.reset_settings()
                st.success("Settings reset to defaults!")
                st.rerun()
            except APIError as e:
                st.error(f"Failed to reset settings: {e.detail}")

    with col3:
        if st.button("Validate Configuration", use_container_width=True, key="settings_validate"):
            validation_settings = settings.copy()
            validation_settings["api_config"]["anthropic_api_key"] = anthropic_key or None
            validation_settings["api_config"]["ollama_host"] = ollama_host

            try:
                result = client.validate_settings(validation_settings)
                if result.get("valid"):
                    st.success("Configuration is valid!")
                else:
                    st.error("Configuration has errors:")
                    for error in result.get("errors", []):
                        st.error(f"• {error}")
                for warning in result.get("warnings", []):
                    st.warning(f"• {warning}")
            except APIError as e:
                st.error(f"Validation failed: {e.detail}")

    st.divider()

    # Connection Status
    st.subheader("Connection Status")

    try:
        health = client.get_health()
        checks = health.get("checks", [])

        ollama_status = "Unknown"
        for check in checks:
            if check.get("name") == "ollama":
                ollama_status = check.get("status", "unknown")
                break

        if ollama_status == "healthy":
            st.success("Ollama: Connected")
        else:
            st.warning("Ollama: Not connected or unhealthy")

        # Test Anthropic connection if key is provided
        if anthropic_key:
            st.success("Anthropic: API key configured")
        else:
            st.info("Anthropic: No API key configured")

    except (ConnectionError, APIError):
        st.error("Backend: Unreachable")
