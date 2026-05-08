"""
Centralized error display utilities for the Streamlit dashboard.

Provides consistent error, warning, and info message rendering
for API connection failures, HTTP errors, and validation issues.
"""

from __future__ import annotations

import streamlit as st

from src.api.client import APIError, ConnectionError


def show_connection_error() -> None:
    """Display a backend connection error message.

    Shows a styled error indicating the backend API is unreachable,
    with guidance on how to resolve the issue.
    """
    st.error(
        "**Backend Unreachable**\n\n"
        "Could not connect to the Job Raider API. Please verify:\n"
        "- The backend container is running (`docker-compose ps`)\n"
        "- The API URL is correct (check BACKEND_API_URL)\n"
        "- No firewall is blocking the connection"
    )


def show_api_error(error: APIError) -> None:
    """Display an API error response.

    Args:
        error: The APIError exception with status code and detail.
    """
    if error.status_code == 404:
        st.warning(f"Resource not found: {error.detail}")
    elif error.status_code == 501:
        st.info(f"Feature not yet implemented: {error.detail}")
    elif error.status_code >= 500:
        st.error(f"**Server Error** ({error.status_code})\n\n{error.detail}")
    elif error.status_code >= 400:
        st.warning(f"**Request Error** ({error.status_code})\n\n{error.detail}")
    else:
        st.error(f"**Unexpected Error** ({error.status_code})\n\n{error.detail}")


def show_validation_error(message: str) -> None:
    """Display a form validation error.

    Args:
        message: Description of the validation failure.
    """
    st.warning(f"**Validation Error**\n\n{message}")
