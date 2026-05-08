"""
Session state management helpers for Streamlit.

Provides centralized access to shared state including the API client
singleton, active pipeline run ID, search results cache, and profile data.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from src.api.client import APIClient


def get_api_client() -> APIClient:
    """Get or create a singleton API client from session state.

    Returns:
        The shared APIClient instance, creating one if none exists.
    """
    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient()
    return st.session_state.api_client


def get_active_run_id() -> Optional[str]:
    """Get the currently monitored pipeline run ID.

    Returns:
        The active run_id, or None if no pipeline is being monitored.
    """
    return st.session_state.get("active_run_id")


def set_active_run_id(run_id: str | None) -> None:
    """Set or clear the active pipeline run for monitoring.

    Args:
        run_id: The run_id to monitor, or None to clear.
    """
    if run_id is None:
        st.session_state.pop("active_run_id", None)
    else:
        st.session_state.active_run_id = run_id


def get_search_results() -> Optional[Dict[str, Any]]:
    """Get cached job search results.

    Returns:
        Cached search results dict, or None if no search has been performed.
    """
    return st.session_state.get("search_results")


def set_search_results(results: Dict[str, Any]) -> None:
    """Cache job search results.

    Args:
        results: Search results dict from the API.
    """
    st.session_state.search_results = results


def clear_search_results() -> None:
    """Clear cached search results."""
    st.session_state.pop("search_results", None)


def get_profile_data() -> Optional[Dict[str, Any]]:
    """Get cached user profile data.

    Returns:
        Cached profile dict, or None if not loaded.
    """
    return st.session_state.get("profile_data")


def set_profile_data(profile: Dict[str, Any]) -> None:
    """Cache user profile data.

    Args:
        profile: Profile dict from the API.
    """
    st.session_state.profile_data = profile


def clear_profile_data() -> None:
    """Clear cached profile data."""
    st.session_state.pop("profile_data", None)


def get_selected_page() -> str:
    """Get the currently selected sidebar page.

    Returns:
        The page identifier string (default: "dashboard").
    """
    return st.session_state.get("selected_page", "dashboard")


def set_selected_page(page: str) -> None:
    """Set the active sidebar page.

    Args:
        page: The page identifier to navigate to.
    """
    st.session_state.selected_page = page


# Default sources used as fallback when backend is unreachable.
_DEFAULT_SOURCES = ["linkedin", "jsearch"]


def get_available_sources(client: APIClient) -> list[str]:
    """Fetch available job sources from the backend, cached in session state.

    Falls back to a default list if the backend is unreachable.

    Args:
        client: The API client instance.

    Returns:
        List of source name strings.
    """
    if "available_sources" in st.session_state:
        return st.session_state.available_sources

    try:
        result = client.get_sources()
        sources = result.get("sources", _DEFAULT_SOURCES)
    except Exception:
        sources = _DEFAULT_SOURCES

    st.session_state.available_sources = sources
    return sources


# -- Pagination state --


def get_jobs_page() -> int:
    """Get the current jobs results page (0-indexed).

    Returns:
        Current page number, defaulting to 0.
    """
    return st.session_state.get("jobs_page", 0)


def set_jobs_page(page: int) -> None:
    """Set the current jobs results page.

    Args:
        page: Zero-indexed page number.
    """
    st.session_state.jobs_page = page


def reset_jobs_page() -> None:
    """Reset the jobs page to 0 (e.g. on new search)."""
    st.session_state.jobs_page = 0


# -- Selected job state --


def get_selected_job_id() -> Optional[str]:
    """Get the currently selected job ID for the detail panel.

    Returns:
        Selected job_id, or None if no job is selected.
    """
    return st.session_state.get("selected_job_id")


def set_selected_job_id(job_id: str | None) -> None:
    """Set or clear the selected job for the detail panel.

    Args:
        job_id: The job_id to show in detail, or None to clear.
    """
    if job_id is None:
        st.session_state.pop("selected_job_id", None)
    else:
        st.session_state.selected_job_id = job_id


# -- Saved jobs tracking --


def get_saved_job_ids() -> set[str]:
    """Get the set of saved/bookmarked job IDs cached in session.

    Returns:
        Set of job_id strings.
    """
    return st.session_state.get("saved_job_ids", set())


def add_saved_job_id(job_id: str) -> None:
    """Add a job ID to the saved set.

    Args:
        job_id: The job_id to mark as saved.
    """
    saved = get_saved_job_ids()
    saved.add(job_id)
    st.session_state.saved_job_ids = saved


def remove_saved_job_id(job_id: str) -> None:
    """Remove a job ID from the saved set.

    Args:
        job_id: The job_id to unsave.
    """
    saved = get_saved_job_ids()
    saved.discard(job_id)
    st.session_state.saved_job_ids = saved
