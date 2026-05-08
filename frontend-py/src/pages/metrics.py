"""
Metrics page - Cost tracking, application outcomes, and system health.

Provides four sections: cost dashboard, application funnel,
system health grid, and recent LLM call activity.
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.utils.session_state import get_api_client
from src.utils.error_handling import show_connection_error, show_api_error
from src.utils.formatting import format_currency, format_percentage, format_datetime
from src.api.client import APIError, ConnectionError


def render() -> None:
    """Render the Metrics dashboard page."""
    st.header("Metrics")

    client = get_api_client()

    try:
        summary = client.get_metrics_summary()
    except ConnectionError:
        show_connection_error()
        return
    except APIError as e:
        show_api_error(e)
        return

    # Section A: Cost dashboard
    _render_cost_dashboard(summary.get("cost", {}))

    st.divider()

    # Section B: Application outcomes
    _render_outcomes(summary.get("outcomes", {}))

    st.divider()

    # Section C: System health
    _render_system_health(summary.get("health", {}))

    st.divider()

    # Section D: Recent LLM calls
    _render_recent_calls(summary.get("recent_calls", []))


def _render_cost_dashboard(cost: Dict[str, Any]) -> None:
    """Render the cost tracking section.

    Args:
        cost: Cost metrics dictionary.
    """
    st.subheader("Cost Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Cost", format_currency(cost.get("total_usd")))
    col2.metric("Cost per Application", format_currency(cost.get("per_application")))
    col3.metric("Total LLM Calls", cost.get("total_calls", 0))

    # API vs Local cost pie chart
    local_pct = cost.get("local_usage_percent", 0)
    api_pct = 100 - local_pct

    fig = px.pie(
        values=[api_pct, local_pct],
        names=["API (Cloud)", "Local (Ollama)"],
        title="API vs Local Model Usage",
        color_discrete_sequence=["#FF6B6B", "#4ECDC4"],
    )
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)


def _render_outcomes(outcomes: Dict[str, Any]) -> None:
    """Render the application outcomes funnel.

    Args:
        outcomes: Outcome metrics dictionary.
    """
    st.subheader("Application Outcomes")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Applications", outcomes.get("total_applications", 0))
    col2.metric("Interviews", outcomes.get("interviews", 0))
    col3.metric("Offers", outcomes.get("offers", 0))
    col4.metric("Rejections", outcomes.get("rejection_count", 0))

    # Conversion rates
    col5, col6, col7 = st.columns(3)
    col5.metric("Interview Rate", format_percentage(outcomes.get("interview_rate")))
    col6.metric("Offer Rate", format_percentage(outcomes.get("offer_rate")))
    col7.metric("Overall Rate", format_percentage(outcomes.get("overall_rate")))

    # Funnel chart
    apps = outcomes.get("total_applications", 0)
    interviews = outcomes.get("interviews", 0)
    offers = outcomes.get("offers", 0)

    if apps > 0:
        fig = go.Figure(go.Funnel(
            y=["Applications", "Interviews", "Offers"],
            x=[apps, interviews, offers],
            textinfo="value+percent initial",
        ))
        fig.update_layout(title="Application Funnel", height=300)
        st.plotly_chart(fig, use_container_width=True)


def _render_system_health(health: Dict[str, Any]) -> None:
    """Render the system health status grid.

    Args:
        health: Health metrics dictionary.
    """
    st.subheader("System Health")

    status = health.get("status", "unknown")

    if status == "healthy":
        st.success(f"Overall Status: {status.title()}")
    elif status == "degraded":
        st.warning(f"Overall Status: {status.title()}")
    else:
        st.error(f"Overall Status: {status.title()}")

    healthy = health.get("healthy", 0)
    degraded = health.get("degraded", 0)
    unhealthy = health.get("unhealthy", 0)

    col1, col2, col3 = st.columns(3)
    col1.metric("Healthy Checks", healthy)
    col2.metric("Degraded Checks", degraded)
    col3.metric("Unhealthy Checks", unhealthy)

    # Health distribution bar
    if healthy + degraded + unhealthy > 0:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Healthy", "Degraded", "Unhealthy"],
            y=[healthy, degraded, unhealthy],
            marker_color=["#4ECDC4", "#FFE66D", "#FF6B6B"],
        ))
        fig.update_layout(title="Health Check Results", height=250, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


def _render_recent_calls(calls: list) -> None:
    """Render the recent LLM calls table.

    Args:
        calls: List of recent LLM call dictionaries.
    """
    st.subheader("Recent LLM Calls")

    if not calls:
        st.info("No recent LLM calls recorded.")
        return

    df = pd.DataFrame(calls)
    display_cols = [c for c in ["task_type", "provider", "model", "cost_usd", "timestamp"] if c in df.columns]

    if display_cols:
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
