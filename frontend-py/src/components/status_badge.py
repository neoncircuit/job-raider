"""
Status badge component for the Streamlit dashboard.

Provides colored badges for pipeline status and health status
indicators used across multiple pages.
"""

from __future__ import annotations

import streamlit as st


PIPELINE_STATUS_STYLES = {
    "pending": ("blue", "Pending"),
    "running": ("orange", "Running"),
    "completed": ("green", "Completed"),
    "failed": ("red", "Failed"),
    "cancelled": ("gray", "Cancelled"),
}

HEALTH_STATUS_STYLES = {
    "healthy": ("green", "Healthy"),
    "degraded": ("orange", "Degraded"),
    "unhealthy": ("red", "Unhealthy"),
    "unknown": ("gray", "Unknown"),
}


def render_pipeline_status_badge(status: str) -> str:
    """Render a colored status badge for pipeline run status.

    Args:
        status: Pipeline status string (pending, running, completed, failed, cancelled).

    Returns:
        An HTML badge string for display in Streamlit markdown.
    """
    color, label = PIPELINE_STATUS_STYLES.get(
        status.lower(), ("gray", status.title())
    )
    return f":{color}[**{label}**]"


def render_health_status_badge(status: str) -> str:
    """Render a colored status badge for health check status.

    Args:
        status: Health status string (healthy, degraded, unhealthy, unknown).

    Returns:
        An HTML badge string for display in Streamlit markdown.
    """
    color, label = HEALTH_STATUS_STYLES.get(
        status.lower(), ("gray", status.title())
    )
    return f":{color}[**{label}**]"


def render_stage_status_icon(completed: bool, failed: bool = False) -> str:
    """Render an icon indicating stage completion status.

    Args:
        completed: Whether the stage has completed.
        failed: Whether the stage failed.

    Returns:
        A Streamlit emoji string.
    """
    if failed:
        return ":red[x]"
    if completed:
        return ":white_check_mark:"
    return ":white_large_square:"
