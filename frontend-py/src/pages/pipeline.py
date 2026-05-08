"""
Pipeline page - Start, monitor, and review pipeline runs.

Provides a form to start new pipelines, a live progress monitor
using polling, and a history table with expandable results.
"""

from __future__ import annotations

import time
from typing import Any, Dict

import streamlit as st

from config.settings import Settings
from src.utils.session_state import get_api_client, set_active_run_id, get_active_run_id, get_available_sources
from src.utils.error_handling import show_connection_error, show_api_error
from src.utils.formatting import format_datetime, format_duration
from src.components.status_badge import render_pipeline_status_badge
from src.api.client import APIError, ConnectionError


PIPELINE_STAGES = [
    "scrape",
    "deduplicate",
    "filter_scams",
    "filter_by_profile",
    "score_and_rank",
    "detect_auto_submit",
    "present_selection",
    "generate_resumes",
    "submit_applications",
]


def render() -> None:
    """Render the Pipeline management page."""
    st.header("Pipeline")

    client = get_api_client()
    settings = Settings()

    # Section A: Start new pipeline
    _render_start_form(client)

    st.divider()

    # Section B: Active pipeline monitor
    active_run = get_active_run_id()
    if active_run:
        _render_active_monitor(client, active_run, settings)
        st.divider()

    # Section C: Pipeline history
    _render_history(client)


def _render_start_form(client) -> None:
    """Render the start new pipeline form.

    Args:
        client: The API client instance.
    """
    with st.expander("Start New Pipeline", expanded=False):
        with st.form("pipeline_start_form"):
            col1, col2 = st.columns(2)
            with col1:
                keywords = st.text_input(
                    "Keywords (comma-separated)", placeholder="python, engineer, backend"
                )
                locations = st.text_input(
                    "Locations (comma-separated)", placeholder="remote, new york"
                )
            with col2:
                available = get_available_sources(client)
                st.markdown("**Sources**")
                source_cols = st.columns(len(available))
                source_checked = {}
                for idx, src in enumerate(available):
                    source_checked[src] = source_cols[idx].checkbox(
                        src.capitalize(), value=(idx == 0), key=f"pipe_src_{src}"
                    )
                sources = [s for s, checked in source_checked.items() if checked]
                dry_run = st.checkbox("Dry Run Mode", value=True)

            col3, col4, col5 = st.columns(3)
            with col3:
                min_score = st.slider("Minimum Score", 0, 100, 60)
            with col4:
                max_jobs = st.number_input("Max Jobs", 1, 100, 20)
            with col5:
                scam_threshold = st.slider("Scam Threshold", 0.0, 1.0, 0.7, 0.1)

            submitted = st.form_submit_button("Start Pipeline", use_container_width=True)

            if submitted:
                if not keywords or not locations:
                    st.warning("Keywords and locations are required.")
                    return

                request = {
                    "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
                    "locations": [l.strip() for l in locations.split(",") if l.strip()],
                    "sources": sources or None,
                    "dry_run": dry_run,
                    "min_score": min_score,
                    "max_jobs": max_jobs,
                    "scam_threshold": scam_threshold,
                }

                try:
                    run_id = client.start_pipeline(request)
                    set_active_run_id(run_id)
                    st.success(f"Pipeline started: {run_id}")
                    st.rerun()
                except ConnectionError:
                    show_connection_error()
                except APIError as e:
                    show_api_error(e)


def _render_active_monitor(client, run_id: str, settings: Settings) -> None:
    """Render the active pipeline progress monitor.

    Args:
        client: The API client instance.
        run_id: The active pipeline run ID.
        settings: Application settings (for polling interval).
    """
    st.subheader(f"Active Pipeline: {run_id[:8]}...")

    try:
        status_data = client.get_pipeline_status(run_id)
    except (ConnectionError, APIError):
        st.warning("Unable to fetch pipeline status.")
        return

    pipeline_status = status_data.get("status", "unknown")
    is_active = pipeline_status in ("pending", "running")

    # Status badge
    st.markdown(f"Status: {render_pipeline_status_badge(pipeline_status)}")

    # Progress bar
    progress = status_data.get("stage_progress", 0) / 100.0
    st.progress(progress)

    # Live counters
    col1, col2, col3 = st.columns(3)
    col1.metric("Jobs Scraped", status_data.get("jobs_scraped", 0))
    col2.metric("Jobs Scored", status_data.get("jobs_scored", 0))
    col3.metric("Applications", status_data.get("applications_submitted", 0))

    # Stage tracker
    current_stage = status_data.get("current_stage", "")
    with st.expander("Stage Details"):
        for stage in PIPELINE_STAGES:
            if stage == current_stage:
                st.markdown(f":orange[**{stage}**] - In Progress")
            elif PIPELINE_STAGES.index(stage) < PIPELINE_STAGES.index(
                current_stage
            ) if current_stage in PIPELINE_STAGES else False:
                st.markdown(f":white_check_mark: {stage}")
            else:
                st.markdown(f":white_large_square: {stage}")

    # Error display
    error_msg = status_data.get("error_message")
    if error_msg:
        st.error(f"Error: {error_msg}")

    # Cancel button
    if is_active:
        if st.button("Cancel Pipeline"):
            try:
                client.cancel_pipeline(run_id)
                st.warning("Pipeline cancelled.")
                set_active_run_id(None)
                st.rerun()
            except (ConnectionError, APIError) as e:
                show_api_error(e) if isinstance(e, APIError) else show_connection_error()

    # Auto-refresh hint
    if is_active:
        st.caption(f"Auto-refresh every {settings.POLLING_INTERVAL_SEC}s")


def _render_history(client) -> None:
    """Render the pipeline run history table.

    Args:
        client: The API client instance.
    """
    st.subheader("Pipeline History")

    try:
        history = client.get_pipeline_history(limit=20)
        runs = history.get("runs", [])

        if not runs:
            st.info("No pipeline runs found.")
            return

        for run in runs:
            run_id = run.get("run_id", "unknown")
            status = run.get("status", "unknown")
            created = format_datetime(run.get("created_at"))

            with st.expander(f"{run_id[:8]}... | {render_pipeline_status_badge(status)} | {created}"):
                if st.button("View Results", key=f"results_{run_id}"):
                    try:
                        results = client.get_pipeline_results(run_id)
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Duration", format_duration(results.get("duration_seconds")))
                        col2.metric("Jobs Scraped", results.get("jobs_scraped", 0))
                        col3.metric("Jobs Applied", results.get("jobs_applied", 0))

                        stages = results.get("stages_completed", [])
                        if stages:
                            st.markdown(f"Stages completed: {', '.join(stages)}")

                    except (ConnectionError, APIError) as e:
                        show_api_error(e) if isinstance(e, APIError) else show_connection_error()

    except ConnectionError:
        show_connection_error()
    except APIError as e:
        show_api_error(e)
