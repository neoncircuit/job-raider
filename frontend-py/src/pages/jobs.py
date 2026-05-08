"""
Jobs page - Search, browse, score, and apply to jobs.

Provides a search form, split-panel results with compact job list
on the left and detail view on the right, status tabs for All/Saved/Applied,
and pagination controls.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from src.utils.session_state import (
    get_api_client,
    get_search_results,
    set_search_results,
    clear_search_results,
    get_available_sources,
    get_jobs_page,
    set_jobs_page,
    reset_jobs_page,
    get_selected_job_id,
    set_selected_job_id,
    get_saved_job_ids,
    remove_saved_job_id,
)
from src.utils.error_handling import show_connection_error, show_api_error
from src.utils.formatting import truncate_text, format_date
from src.components.pagination import render_pagination, get_page_slice
from src.components.job_card import render_compact_job_card, render_detail_panel
from src.components.pill_badge import render_source_badge
from src.api.client import APIError, ConnectionError

_PER_PAGE = 20


def render() -> None:
    """Render the Jobs search and browse page."""
    st.header("Jobs")

    client = get_api_client()

    _render_search_form(client)

    st.divider()

    _render_results(client)


def _render_search_form(client: Any) -> None:
    """Render the job search form.

    Args:
        client: The API client instance.
    """
    with st.form("job_search_form"):
        col1, col2 = st.columns(2)
        with col1:
            keywords = st.text_input(
                "Keywords (comma-separated)", placeholder="python, engineer"
            )
            locations = st.text_input(
                "Locations (comma-separated)", placeholder="remote, san francisco"
            )
        with col2:
            available = get_available_sources(client)
            st.markdown("**Sources**")
            source_cols = st.columns(len(available))
            source_checked: Dict[str, bool] = {}
            for idx, src in enumerate(available):
                source_checked[src] = source_cols[idx].checkbox(
                    src.capitalize(), value=(idx == 0), key=f"src_{src}"
                )
            sources = [s for s, checked in source_checked.items() if checked]
            remote_only = st.checkbox("Remote Only")

        limit = st.slider("Results Limit", 1, 200, 50)

        submitted = st.form_submit_button("Search Jobs", use_container_width=True)

        if submitted:
            if not keywords or not locations:
                st.warning("Keywords and locations are required.")
                return

            request = {
                "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
                "locations": [l.strip() for l in locations.split(",") if l.strip()],
                "sources": sources or None,
                "limit": limit,
                "remote_only": remote_only,
            }

            try:
                with st.spinner("Searching jobs..."):
                    results = client.search_jobs(request)
                    set_search_results(results)
                    reset_jobs_page()
                    set_selected_job_id(None)
            except ConnectionError:
                show_connection_error()
            except APIError as e:
                show_api_error(e)

    # Semantic search section
    with st.expander("Semantic Search"):
        semantic_query = st.text_area(
            "Describe your ideal job",
            placeholder="E.g. Senior Python backend role working on distributed systems with a focus on observability and DevOps practices",
            key="semantic_search_query",
        )
        col_n, col_min = st.columns(2)
        with col_n:
            semantic_n = st.slider("Max results", 1, 50, 20, key="semantic_n_results")
        with col_min:
            semantic_min = st.slider(
                "Min similarity (%)", 0, 100, 30, key="semantic_min_similarity"
            )

        if st.button("Semantic Search", key="semantic_search_btn", use_container_width=True):
            if not semantic_query or not semantic_query.strip():
                st.warning("Please describe your ideal job to perform a semantic search.")
            else:
                try:
                    with st.spinner("Running semantic search..."):
                        results = client.semantic_search(
                            query=semantic_query.strip(),
                            n_results=semantic_n,
                            min_similarity=semantic_min / 100.0,
                        )
                        set_search_results(results)
                        reset_jobs_page()
                        set_selected_job_id(None)
                        st.toast(f"Found {results.get('total', 0)} semantically similar jobs")
                        st.rerun()
                except ConnectionError:
                    show_connection_error()
                except APIError as e:
                    show_api_error(e)


def _render_results(client: Any) -> None:
    """Render the search results with tabs and split-panel layout.

    Args:
        client: The API client instance.
    """
    results = get_search_results()
    if not results:
        st.info("No search results. Use the form above to search for jobs.")
        return

    total = results.get("total", 0)
    jobs: List[Dict[str, Any]] = results.get("jobs", [])

    tab_all, tab_saved, tab_applied = st.tabs(
        ["All", "Saved", "Applied"]
    )

    with tab_all:
        _render_all_jobs(client, jobs, total)

    with tab_saved:
        _render_saved_jobs(client)

    with tab_applied:
        _render_applied_jobs(client)


def _render_all_jobs(
    client: Any, jobs: List[Dict[str, Any]], total: int
) -> None:
    """Render all search results in a split-panel layout with pagination.

    Args:
        client: The API client instance.
        jobs: Full list of job results from search.
        total: Total number of jobs found.
    """
    if not jobs:
        st.info("No jobs matched your search criteria.")
        return

    st.subheader(f"Results ({total} jobs found)")

    page = get_jobs_page()
    page_jobs = get_page_slice(jobs, page, _PER_PAGE)

    render_pagination(page, total, _PER_PAGE, page_key="jobs_page")
    page = get_jobs_page()
    page_jobs = get_page_slice(jobs, page, _PER_PAGE)

    saved_ids = get_saved_job_ids()
    selected_id = get_selected_job_id()

    list_col, detail_col = st.columns([2, 3], gap="medium")

    with list_col:
        st.caption("Click View to see details")
        for job in page_jobs:
            job_id = job.get("job_id", "unknown")
            render_compact_job_card(
                job,
                is_selected=(job_id == selected_id),
                is_saved=(job_id in saved_ids),
            )

    with detail_col:
        selected_job = _find_job(jobs, selected_id)
        if selected_job:
            render_detail_panel(selected_job, client)
        else:
            st.info("Select a job from the list to view details.")

    st.divider()
    render_pagination(page, total, _PER_PAGE, page_key="jobs_page")


def _render_saved_jobs(client: Any) -> None:
    """Render bookmarked/saved jobs from the application tracker.

    Args:
        client: The API client instance.
    """
    try:
        dashboard = client.get_application_dashboard(
            include_bookmarked=True,
            include_hidden=False,
            include_external=False,
        )
        applications = dashboard.get("applications", [])
        saved = [a for a in applications if a.get("is_bookmarked")]

        if not saved:
            st.info("No saved jobs. Click **Save** on any job card to bookmark it.")
            return

        st.subheader(f"Saved Jobs ({len(saved)})")

        for app in saved:
            _render_saved_card(app, client)

    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _render_applied_jobs(client: Any) -> None:
    """Render jobs that have been applied to from the application tracker.

    Args:
        client: The API client instance.
    """
    try:
        dashboard = client.get_application_dashboard(
            include_bookmarked=False,
            include_hidden=False,
            include_external=True,
        )
        applications = dashboard.get("applications", [])

        applied_statuses = {
            "applied_auto",
            "applied_manual",
            "applied_elsewhere",
            "applied",
        }
        applied = [
            a
            for a in applications
            if a.get("current_status", "").lower() in applied_statuses
        ]

        if not applied:
            st.info(
                "No applications tracked yet. Apply to jobs or track external applications."
            )
            return

        st.subheader(f"Applied Jobs ({len(applied)})")

        for app in applied:
            _render_applied_card(app)

    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _render_saved_card(app: Dict[str, Any], client: Any) -> None:
    """Render a single saved/bookmarked job card.

    Args:
        app: Application data dict from the dashboard.
        client: The API client instance.
    """
    job_title = app.get("job_title", "Unknown")
    company = app.get("company", "Unknown")
    status = app.get("current_status", "")
    app_id = app.get("application_id", "")

    with st.container(border=True):
        col_info, col_action = st.columns([3, 1])
        with col_info:
            st.markdown(f"**{job_title}**")
            st.caption(f"{company} | Status: {status}")
        with col_action:
            if st.button("Unsave", key=f"unsave_{app_id}", use_container_width=True):
                try:
                    client.unsave_job(app_id)
                    remove_saved_job_id(app_id)
                    st.toast("Job unsaved")
                    st.rerun()
                except (ConnectionError, APIError) as e:
                    show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _render_applied_card(app: Dict[str, Any]) -> None:
    """Render a single applied job card.

    Args:
        app: Application data dict from the dashboard.
    """
    job_title = app.get("job_title", "Unknown")
    company = app.get("company", "Unknown")
    status = app.get("current_status", "")
    applied_date = app.get("applied_date", "")
    app_id = app.get("application_id", "")
    days_since = app.get("days_since_application", "?")

    with st.container(border=True):
        st.markdown(f"**{job_title}**")
        st.caption(
            f"{company} | Status: {status} | Applied: {applied_date} | {days_since} days ago"
        )


def _find_job(
    jobs: List[Dict[str, Any]], job_id: str | None
) -> Dict[str, Any] | None:
    """Find a job by ID in the results list.

    Args:
        jobs: List of job data dictionaries.
        job_id: The job_id to find, or None.

    Returns:
        Matching job dict, or None if not found or job_id is None.
    """
    if not job_id:
        return None
    for job in jobs:
        if job.get("job_id") == job_id:
            return job
    return None
