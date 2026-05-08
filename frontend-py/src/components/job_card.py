"""
Job card components for the Streamlit dashboard.

Provides compact job card rendering for list panels and full
detail panel rendering for the split-panel Jobs page layout.
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from src.utils.formatting import truncate_text, format_date, format_salary_range
from src.utils.error_handling import show_connection_error, show_api_error
from src.utils.session_state import (
    get_saved_job_ids,
    add_saved_job_id,
    remove_saved_job_id,
    set_selected_job_id,
)
from src.components.pill_badge import (
    render_source_badge,
    render_pill_group,
    render_score_badge,
    render_semantic_badge,
)
from src.api.client import APIError, ConnectionError


def render_compact_job_card(
    job: Dict[str, Any],
    is_selected: bool,
    is_saved: bool,
) -> None:
    """Render a compact job card for the list panel.

    Uses Streamlit-native components to avoid HTML rendering issues.
    Displays title, company, location, source badge, salary,
    top skills as pills, and a row of action buttons.

    Args:
        job: Job listing data dictionary.
        is_selected: Whether this card is currently selected.
        is_saved: Whether this job is bookmarked.
    """
    job_id = job.get("job_id", "unknown")
    title = job.get("title", "Untitled")
    company = job.get("company", "Unknown")
    location = job.get("location", "N/A")
    source = job.get("source", "N/A")
    remote = job.get("remote", False)
    salary = job.get("salary_range")
    skills = job.get("skills", [])

    source_badge = render_source_badge(source)
    salary_str = format_salary_range(salary) if salary else None

    border = is_selected
    with st.container(border=border):
        # Title line with remote tag
        remote_tag = " [Remote]" if remote else ""
        st.markdown(f"**{title}**{remote_tag}")

        # Metadata line: company, location, source pill, salary
        meta = f"{company} &middot; {location} &middot; {source_badge}"
        if salary_str:
            meta += f" &middot; {salary_str}"
        st.markdown(meta, unsafe_allow_html=True)

        # Skills as pill badges (max 3 shown)
        if skills:
            skills_html = render_pill_group(skills, max_items=3)
            st.markdown(skills_html, unsafe_allow_html=True)

        # Action buttons row
        col_select, col_save, col_score, col_apply = st.columns([2, 1, 1, 1])
        with col_select:
            if st.button("View", key=f"view_{job_id}", use_container_width=True):
                set_selected_job_id(job_id)
                st.rerun()
        with col_save:
            save_label = "Saved" if is_saved else "Save"
            if st.button(save_label, key=f"save_{job_id}", use_container_width=True):
                _toggle_save(job)
        with col_score:
            if st.button("Score", key=f"score_{job_id}", use_container_width=True):
                _handle_score(job_id)
        with col_apply:
            if st.button("Apply", key=f"apply_{job_id}", use_container_width=True):
                _handle_apply(job_id)


def render_detail_panel(job: Dict[str, Any], client: Any) -> None:
    """Render the full job detail panel for the right column.

    Shows complete job description, all skills as pills,
    score result, and application actions.

    Args:
        job: Full job listing data dictionary.
        client: The API client instance.
    """
    job_id = job.get("job_id", "unknown")
    title = job.get("title", "Untitled")
    company = job.get("company", "Unknown")
    location = job.get("location", "N/A")
    source = job.get("source", "N/A")
    remote = job.get("remote", False)
    salary = job.get("salary_range")
    posted = format_date(job.get("posted_date"))
    description = job.get("description", "No description available.")
    skills = job.get("skills", [])
    source_url = job.get("source_url")

    remote_tag = " [Remote]" if remote else ""
    st.subheader(f"{title}{remote_tag}")
    st.caption(f"{company} | {location} | Posted: {posted}")
    st.markdown(render_source_badge(source), unsafe_allow_html=True)

    if salary:
        st.caption(f"Salary: {format_salary_range(salary)}")

    st.divider()

    st.markdown(description)

    if skills:
        st.markdown("**Skills**")
        skills_html = render_pill_group(skills)
        st.markdown(skills_html, unsafe_allow_html=True)

    if source_url:
        st.markdown(f"[View Original Posting]({source_url})")

    st.divider()

    score_key = f"score_result_{job_id}"
    semantic_key = f"semantic_result_{job_id}"
    col_score, col_sim, col_apply = st.columns(3)
    with col_score:
        if st.button("Score Relevance", key=f"detail_score_{job_id}", use_container_width=True):
            _handle_score(job_id)
    with col_sim:
        if st.button("Similarity", key=f"detail_similarity_{job_id}", use_container_width=True):
            _handle_similarity(job_id)
    with col_apply:
        if st.button("Apply Now", key=f"detail_apply_{job_id}", type="primary", use_container_width=True):
            _handle_apply(job_id)

    if score_key in st.session_state and st.session_state[score_key]:
        result = st.session_state[score_key]
        score = result.get("total_score", 0)
        st.markdown(
            f"**Match Score:** {render_score_badge(score)}",
            unsafe_allow_html=True,
        )
        breakdown = result.get("details", {})
        if breakdown:
            with st.expander("Score Breakdown"):
                for category, value in breakdown.items():
                    st.markdown(f"- **{category}**: {value}")

    if semantic_key in st.session_state and st.session_state[semantic_key]:
        sem = st.session_state[semantic_key]
        heuristic = sem.get("heuristic_score", 0)
        semantic = sem.get("semantic_score", 0.0)
        combined = sem.get("combined_score", 0.0)

        st.markdown("**Similarity Metrics**")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Heuristic", f"{heuristic}/100")
        with m2:
            st.metric("Semantic", render_semantic_badge(semantic), unsafe_allow_html=True)
            st.caption(f"{semantic:.1%}")
        with m3:
            st.metric("Combined", f"{combined:.1%}")

        explanation = sem.get("explanation")
        if explanation:
            with st.expander("Similarity Explanation"):
                st.markdown(explanation)


def _toggle_save(job: Dict[str, Any]) -> None:
    """Toggle the saved/bookmarked state of a job.

    Args:
        job: Job listing data dictionary.
    """
    from src.utils.session_state import get_api_client

    job_id = job.get("job_id", "unknown")
    saved = get_saved_job_ids()
    client = get_api_client()

    try:
        if job_id in saved:
            client.unsave_job(job_id)
            remove_saved_job_id(job_id)
            st.toast("Job removed from saved")
        else:
            client.save_job(
                job_id,
                metadata={
                    "title": job.get("title", "Unknown"),
                    "company": job.get("company", "Unknown"),
                    "source_url": job.get("source_url"),
                },
            )
            add_saved_job_id(job_id)
            st.toast("Job saved")
    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _handle_score(job_id: str) -> None:
    """Score a job's relevance and cache the result.

    Args:
        job_id: The job identifier.
    """
    from src.utils.session_state import get_api_client

    client = get_api_client()
    try:
        with st.spinner("Scoring..."):
            result = client.score_job(job_id)
            st.session_state[f"score_result_{job_id}"] = result
            score = result.get("total_score", 0)
            st.toast(f"Relevance: {score}/100")
    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _handle_apply(job_id: str) -> None:
    """Submit a job application (dry run by default).

    Args:
        job_id: The job identifier.
    """
    from src.utils.session_state import get_api_client

    client = get_api_client()
    try:
        with st.spinner("Applying..."):
            result = client.apply_to_job(job_id, dry_run=True)
            st.toast(result.get("message", "Application submitted (dry run)"))
    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()


def _handle_similarity(job_id: str) -> None:
    """Fetch and cache semantic similarity scores for a job.

    Args:
        job_id: The job identifier.
    """
    from src.utils.session_state import get_api_client

    client = get_api_client()
    try:
        with st.spinner("Computing similarity..."):
            result = client.get_job_similarity(job_id)
            st.session_state[f"semantic_result_{job_id}"] = result
            combined = result.get("combined_score", 0.0)
            st.toast(f"Similarity: {combined:.1%}")
    except (ConnectionError, APIError) as e:
        show_api_error(e) if isinstance(e, APIError) else show_connection_error()
