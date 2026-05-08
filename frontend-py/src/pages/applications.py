"""
Applications page - Job application tracker dashboard.

Displays tracked applications with summary metrics, filterable tabs
for all/bookmarked/hidden jobs, and expandable detail views.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from src.utils.session_state import get_api_client
from src.utils.error_handling import show_connection_error, show_api_error
from src.utils.formatting import format_date
from src.components.status_badge import render_pipeline_status_badge
from src.api.client import APIError, ConnectionError


def render() -> None:
    """Render the Applications tracker dashboard page."""
    st.header("Application Tracker")

    client = get_api_client()

    _render_summary(client)

    st.divider()

    _render_filter_bar(client)

    tab_all, tab_saved, tab_hidden = st.tabs(
        ["All Applications", "Bookmarked", "Hidden"]
    )

    with tab_all:
        _render_all_applications(client)

    with tab_saved:
        _render_bookmarked(client)

    with tab_hidden:
        _render_hidden(client)


def _render_summary(client: Any) -> None:
    """Render summary metric cards at the top of the page.

    Args:
        client: The API client instance.
    """
    try:
        dashboard = client.get_application_dashboard(
            include_hidden=True,
            include_bookmarked=True,
            include_external=True,
        )
        summary = dashboard.get("summary", {})

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Tracked", summary.get("total_applications", 0))
        col2.metric("Bookmarked", summary.get("bookmarked", 0))
        col3.metric("Hidden", summary.get("hidden", 0))
        col4.metric("External", summary.get("external", 0))

        by_status = summary.get("by_status", {})
        if by_status:
            with st.expander("Status Breakdown"):
                for status, count in sorted(by_status.items()):
                    st.markdown(f"- **{status}**: {count}")

    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _render_filter_bar(client: Any) -> None:
    """Render filter controls for the application lists.

    Args:
        client: The API client instance.
    """
    col1, col2, col3 = st.columns(3)
    with col1:
        company_filter = st.text_input(
            "Filter by Company", placeholder="e.g. Google", key="app_company_filter"
        )
    with col2:
        days_filter = st.number_input(
            "Last N Days",
            min_value=0,
            max_value=365,
            value=0,
            help="0 = show all",
            key="app_days_filter",
        )
    with col3:
        if st.button("Refresh", use_container_width=True, key="app_refresh"):
            st.rerun()

    st.session_state["_app_filters"] = {
        "company": company_filter or None,
        "days": days_filter if days_filter > 0 else None,
    }


def _get_filters() -> Dict[str, Any]:
    """Get the current filter values from session state.

    Returns:
        Dict with company and days filter values.
    """
    return st.session_state.get(
        "_app_filters", {"company": None, "days": None}
    )


def _render_all_applications(client: Any) -> None:
    """Render all tracked applications.

    Args:
        client: The API client instance.
    """
    filters = _get_filters()
    try:
        dashboard = client.get_application_dashboard(
            company=filters.get("company"),
            days=filters.get("days"),
            include_hidden=False,
            include_bookmarked=True,
            include_external=True,
        )
        applications = dashboard.get("applications", [])

        if not applications:
            st.info("No tracked applications yet.")
            return

        st.subheader(f"All Applications ({len(applications)})")
        for app in applications:
            _render_application_card(app, client, show_actions=True)

    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _render_bookmarked(client: Any) -> None:
    """Render bookmarked/saved jobs.

    Args:
        client: The API client instance.
    """
    try:
        dashboard = client.get_application_dashboard(
            include_bookmarked=True,
            include_hidden=False,
            include_external=False,
        )
        saved = [
            a for a in dashboard.get("applications", []) if a.get("is_bookmarked")
        ]

        if not saved:
            st.info("No bookmarked jobs. Save jobs from the Jobs page to see them here.")
            return

        st.subheader(f"Bookmarked ({len(saved)})")
        for app in saved:
            _render_application_card(app, client, show_actions=True)

    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _render_hidden(client: Any) -> None:
    """Render hidden/not-interested jobs.

    Args:
        client: The API client instance.
    """
    try:
        dashboard = client.get_application_dashboard(
            include_hidden=True,
            include_bookmarked=False,
            include_external=False,
        )
        hidden = [a for a in dashboard.get("applications", []) if a.get("is_hidden")]

        if not hidden:
            st.info("No hidden jobs.")
            return

        st.subheader(f"Hidden ({len(hidden)})")
        for app in hidden:
            _render_application_card(app, client, show_actions=True)

    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _render_application_card(
    app: Dict[str, Any], client: Any, show_actions: bool = True
) -> None:
    """Render a single application card with status and actions.

    Args:
        app: Application data dict from the dashboard API.
        client: The API client instance.
        show_actions: Whether to show action buttons.
    """
    app_id = app.get("application_id", "unknown")
    job_title = app.get("job_title", "Unknown")
    company = app.get("company", "Unknown")
    status = app.get("current_status", "unknown")
    applied_date = format_date(app.get("applied_date"))
    days_since = app.get("days_since_application", "?")
    custom_status = app.get("custom_status")
    is_bookmarked = app.get("is_bookmarked", False)
    is_hidden = app.get("is_hidden", False)

    with st.container(border=True):
        col_info, col_status, col_actions = st.columns([3, 1, 1])

        with col_info:
            st.markdown(f"**{job_title}**")
            caption_parts = [company, f"Applied: {applied_date}", f"{days_since}d ago"]
            if custom_status:
                caption_parts.append(custom_status.get("name", ""))
            st.caption(" | ".join(caption_parts))

        with col_status:
            status_display = status.replace("_", " ").title()
            if is_bookmarked:
                st.markdown(":blue[Bookmarked]")
            elif is_hidden:
                st.markdown(":gray[Hidden]")
            else:
                st.markdown(f"**{status_display}**")

        with col_actions:
            if show_actions:
                if st.button("Detail", key=f"app_detail_{app_id}", use_container_width=True):
                    st.session_state[f"_app_expanded_{app_id}"] = not st.session_state.get(
                        f"_app_expanded_{app_id}", False
                    )

        if st.session_state.get(f"_app_expanded_{app_id}", False):
            _render_application_detail(client, app_id, is_hidden, is_bookmarked)


def _render_application_detail(
    client: Any, app_id: str, is_hidden: bool, is_bookmarked: bool
) -> None:
    """Render expanded detail for a tracked application.

    Args:
        client: The API client instance.
        app_id: The application/job identifier.
        is_hidden: Whether the application is hidden.
        is_bookmarked: Whether the application is bookmarked.
    """
    try:
        detail = client.get_application_detail(app_id)

        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Status:** {detail.get('current_status', 'N/A')}")
                st.markdown(f"**Company:** {detail.get('company', 'N/A')}")
                st.markdown(f"**Applied:** {format_date(detail.get('applied_date'))}")
            with col2:
                interviews = detail.get("interviews", [])
                st.markdown(f"**Interviews:** {len(interviews)}")
                offer = detail.get("offer")
                if offer:
                    st.markdown(f"**Offer:** Available")
                custom_status = detail.get("custom_status")
                if custom_status:
                    st.markdown(f"**Custom Status:** {custom_status.get('name', 'N/A')}")

            timeline = detail.get("timeline_notes", [])
            if timeline:
                with st.expander("Timeline"):
                    for note in timeline:
                        st.markdown(f"- {note}")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if is_bookmarked:
                    if st.button("Unsave", key=f"detail_unsave_{app_id}", use_container_width=True):
                        try:
                            client.unsave_job(app_id)
                            st.toast("Unsaved")
                            st.rerun()
                        except (ConnectionError, APIError) as e:
                            show_api_error(e) if isinstance(e, APIError) else show_connection_error()
            with col_b:
                if is_hidden:
                    if st.button("Unhide", key=f"detail_unhide_{app_id}", use_container_width=True):
                        try:
                            client.unhide_job(app_id)
                            st.toast("Restored")
                            st.rerun()
                        except (ConnectionError, APIError) as e:
                            show_api_error(e) if isinstance(e, APIError) else show_connection_error()
            with col_c:
                if st.button("Hide", key=f"detail_hide_{app_id}", use_container_width=True):
                    try:
                        client.hide_job(app_id)
                        st.toast("Hidden")
                        st.rerun()
                    except (ConnectionError, APIError) as e:
                        show_api_error(e) if isinstance(e, APIError) else show_connection_error()

    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()
