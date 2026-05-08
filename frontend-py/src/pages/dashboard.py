"""
Dashboard page - Home/overview for the Streamlit dashboard.

Displays system health, quick stats, recent activity, and a
quick-launch button for starting a new pipeline run.
"""

from __future__ import annotations

import streamlit as st

from src.utils.session_state import get_api_client, set_selected_page
from src.utils.error_handling import show_connection_error, show_api_error
from src.api.client import APIError, ConnectionError


def render() -> None:
    """Render the Dashboard home page."""
    st.header("Dashboard")

    client = get_api_client()

    # System health
    _render_health_check(client)

    st.divider()

    # Quick stats
    _render_quick_stats(client)

    st.divider()

    # Recent activity
    _render_recent_activity(client)


def _render_health_check(client) -> None:
    """Render the system health check section.

    Args:
        client: The API client instance.
    """
    st.subheader("System Health")
    try:
        health = client.get_health()
        status = health.get("status", "unknown")

        if status == "healthy":
            st.success(f"System Status: {status.title()}")
        elif status == "degraded":
            st.warning(f"System Status: {status.title()}")
        else:
            st.error(f"System Status: {status.title()}")

        checks = health.get("checks", [])
        if checks:
            with st.expander("Health Check Details"):
                for check in checks:
                    name = check.get("name", "Unknown")
                    msg = check.get("message", "")
                    check_status = check.get("status", "unknown")
                    if check_status == "healthy":
                        st.success(f"{name}: {msg}")
                    elif check_status == "degraded":
                        st.warning(f"{name}: {msg}")
                    else:
                        st.error(f"{name}: {msg}")

        version = client.get_version()
        st.caption(f"API Version: {version.get('version', 'unknown')}")

    except ConnectionError:
        show_connection_error()
    except APIError as e:
        show_api_error(e)


def _render_quick_stats(client) -> None:
    """Render the quick stats row.

    Args:
        client: The API client instance.
    """
    st.subheader("Quick Stats")
    try:
        summary = client.get_metrics_summary()

        cost = summary.get("cost", {})
        outcomes = summary.get("outcomes", {})

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Applications", outcomes.get("total_applications", 0))
        col2.metric("Interviews", outcomes.get("interviews", 0))
        col3.metric("Total Cost", f"${cost.get('total_usd', 0):.2f}")
        col4.metric("Interview Rate", f"{outcomes.get('interview_rate', 0):.1f}%")

    except (ConnectionError, APIError):
        st.info("Stats unavailable - backend not reachable.")


def _render_recent_activity(client) -> None:
    """Render the recent pipeline activity section.

    Args:
        client: The API client instance.
    """
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Recent Pipeline Runs")
        try:
            history = client.get_pipeline_history(limit=5)
            runs = history.get("runs", [])

            if not runs:
                st.info("No pipeline runs yet.")
            else:
                for run in runs:
                    run_id = run.get("run_id", "unknown")
                    status = run.get("status", "unknown")
                    created = run.get("created_at", "N/A")
                    st.markdown(
                        f"- **{run_id[:8]}...** | {status.title()} | {created}"
                    )

        except (ConnectionError, APIError):
            st.info("Unable to load pipeline history.")

    with col_right:
        st.subheader("Quick Actions")
        if st.button("Start New Pipeline", use_container_width=True):
            set_selected_page("pipeline")
            st.rerun()
