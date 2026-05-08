"""
Sidebar navigation component for the Streamlit dashboard.

Renders the sidebar with page navigation, backend connection
status indicator, and project branding.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

import streamlit as st

from src.utils.session_state import get_api_client, set_selected_page


def render_sidebar(pages: Dict[str, Tuple[str, Callable[..., None]]]) -> None:
    """Render the sidebar navigation with backend connection status.

    Args:
        pages: Dict mapping page keys to (display_name, render_function) tuples.
    """
    with st.sidebar:
        st.title("Job Raider")
        st.caption("Automated Job Application Pipeline")

        st.divider()

        _render_connection_status()

        st.divider()

        st.markdown("### Navigation")

        current_key = st.session_state.get("selected_page", "dashboard")

        # Define icons for each page
        icons = {
            "dashboard": "🏠",
            "pipeline": "🚀",
            "jobs": "💼",
            "applications": "📋",
            "profile": "👤",
            "resume_analysis": "📄",
            "metrics": "📊",
            "settings": "⚙️",
        }

        for key, (label, _) in pages.items():
            icon = icons.get(key, "•")
            is_active = key == current_key

            if is_active:
                # Active tab styling
                st.markdown(
                    f"""
                    <div style="
                        padding: 10px 15px;
                        margin: 5px 0;
                        background: linear-gradient(90deg, #4A90E2 0%, #357ABD 100%);
                        border-radius: 8px;
                        color: white;
                        font-weight: 600;
                        box-shadow: 0 2px 4px rgba(74, 144, 226, 0.3);
                    ">
                        {icon} {label}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                # Inactive tab - clickable button
                if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
                    set_selected_page(key)
                    st.rerun()

        st.divider()

        _render_quick_stats()


def _render_connection_status() -> None:
    """Render backend connection status indicator in the sidebar."""
    try:
        client = get_api_client()
        health = client.get_health()
        status = health.get("status", "unknown")

        if status == "healthy":
            st.success("Backend: Connected")
            st.session_state._last_backend_status = "healthy"
        elif status == "degraded":
            st.warning("Backend: Degraded")
            st.session_state._last_backend_status = "degraded"
        else:
            st.error("Backend: Unhealthy")
            st.session_state._last_backend_status = "unhealthy"
    except Exception:
        last_status = st.session_state.get("_last_backend_status")
        if last_status == "healthy":
            st.warning("Backend: Processing...")
        else:
            st.error("Backend: Unreachable")


def _render_quick_stats() -> None:
    """Render quick stat indicators in the sidebar."""
    try:
        client = get_api_client()
        summary = client.get_metrics_summary()

        outcomes = summary.get("outcomes", {})
        cost = summary.get("cost", {})

        st.markdown("**Quick Stats**")
        col1, col2 = st.columns(2)
        col1.metric("Applications", outcomes.get("total_applications", 0))
        col2.metric("Total Cost", f"${cost.get('total_usd', 0):.2f}")
    except Exception:
        pass
