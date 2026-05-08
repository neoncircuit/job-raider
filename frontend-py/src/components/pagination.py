"""
Pagination component for the Streamlit dashboard.

Provides reusable pagination controls with page info display,
Previous/Next buttons, and session state integration.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


def render_pagination(
    current_page: int,
    total_items: int,
    per_page: int = 20,
    page_key: str = "jobs_page",
) -> None:
    """Render pagination controls with page info and navigation buttons.

    Displays "Showing X-Y of Z" text with Previous and Next buttons.
    Updates session state on click and triggers a rerun.

    Args:
        current_page: Zero-indexed current page number.
        total_items: Total number of items across all pages.
        per_page: Number of items per page.
        page_key: Session state key for storing the current page.
    """
    if total_items == 0:
        return

    total_pages = max(1, (total_items + per_page - 1) // per_page)
    start = current_page * per_page + 1
    end = min((current_page + 1) * per_page, total_items)

    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        if current_page > 0:
            if st.button("Previous", key=f"{page_key}_prev", use_container_width=True):
                st.session_state[page_key] = current_page - 1
                st.rerun()

    with col_info:
        st.markdown(
            f"<div style='text-align:center; padding-top:6px; color:#6B7280;'>"
            f"Showing {start}-{end} of {total_items} jobs "
            f"(page {current_page + 1} of {total_pages})"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        if current_page < total_pages - 1:
            if st.button("Next", key=f"{page_key}_next", use_container_width=True):
                st.session_state[page_key] = current_page + 1
                st.rerun()


def get_page_slice(
    items: list,
    page: int,
    per_page: int = 20,
) -> list:
    """Return the slice of items for the given page.

    Args:
        items: Full list of items to paginate.
        page: Zero-indexed page number.
        per_page: Number of items per page.

    Returns:
        Sublist of items for the requested page.
    """
    start = page * per_page
    end = start + per_page
    return items[start:end]
