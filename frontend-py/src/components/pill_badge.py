"""
Pill badge component for the Streamlit dashboard.

Provides HTML-based pill/chip badge rendering for skills, sources,
and status indicators using st.markdown with inline CSS styling.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st

# Color palette for source badges and skill categories.
_SOURCE_COLORS: Dict[str, str] = {
    "linkedin": "#0A66C2",
    "jsearch": "#6366F1",
    "manual": "#6B7280",
}

_SKILL_COLORS: List[str] = [
    "#4A90E2",
    "#6366F1",
    "#8B5CF6",
    "#EC4899",
    "#F59E0B",
    "#10B981",
    "#EF4444",
    "#3B82F6",
]


def render_pill(
    text: str,
    bg_color: str = "#4A90E2",
    text_color: str = "white",
    font_size: str = "0.8em",
) -> str:
    """Return HTML for a single pill badge span.

    Args:
        text: Label text to display inside the pill.
        bg_color: Background color (CSS value).
        text_color: Text color (CSS value).
        font_size: Font size for the pill text.

    Returns:
        HTML string for the pill badge element.
    """
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<span style="background:{bg_color}; color:{text_color}; '
        f"padding:2px 10px; border-radius:12px; font-size:{font_size}; "
        f'margin:2px 4px 2px 0; display:inline-block; '
        f'white-space:nowrap; '
        f'text-shadow:0 0 2px rgba(0,0,0,0.3);">{escaped}</span>'
    )


def render_pill_group(
    items: List[str],
    color_map: Optional[Dict[str, str]] = None,
    max_items: Optional[int] = None,
    bg_color: str = "#4A90E2",
) -> str:
    """Return HTML for a row of pill badges.

    Args:
        items: List of label strings to render as pills.
        color_map: Optional dict mapping item text to specific colors.
        max_items: If set, only render this many items with a "+N more" suffix.
        bg_color: Default background color when no color_map match exists.

    Returns:
        Combined HTML string for all pill badges.
    """
    if not items:
        return ""

    display = items[: max_items] if max_items else items
    remaining = len(items) - len(display) if max_items else 0

    pills: List[str] = []
    for i, item in enumerate(display):
        if color_map and item.lower() in color_map:
            color = color_map[item.lower()]
        else:
            color = _SKILL_COLORS[i % len(_SKILL_COLORS)]
        pills.append(render_pill(item, bg_color=color))

    if remaining > 0:
        pills.append(
            f'<span style="color:#6B7280; font-size:0.8em; '
            f'margin-left:4px;">+{remaining} more</span>'
        )

    return "".join(pills)


def render_source_badge(source: str) -> str:
    """Return HTML for a source badge pill with source-specific coloring.

    Args:
        source: Source name string (e.g. "linkedin", "jsearch").

    Returns:
        HTML string for the source badge.
    """
    color = _SOURCE_COLORS.get(source.lower(), "#6B7280")
    return render_pill(source.capitalize(), bg_color=color)


def render_score_badge(score: int) -> str:
    """Return HTML for a score indicator pill, color-coded by value.

    Args:
        score: Numeric score (0-100).

    Returns:
        HTML string for the score badge.
    """
    if score >= 80:
        color = "#10B981"
    elif score >= 60:
        color = "#F59E0B"
    else:
        color = "#EF4444"
    return render_pill(f"{score}/100", bg_color=color)


def display_pills(
    items: List[str],
    color_map: Optional[Dict[str, str]] = None,
    max_items: Optional[int] = None,
    bg_color: str = "#4A90E2",
) -> None:
    """Render a row of pill badges directly to the Streamlit app.

    Convenience function that combines render_pill_group with st.markdown.

    Args:
        items: List of label strings to render as pills.
        color_map: Optional dict mapping item text to specific colors.
        max_items: If set, only render this many items.
        bg_color: Default background color.
    """
    html = render_pill_group(items, color_map, max_items, bg_color)
    if html:
        st.markdown(html, unsafe_allow_html=True)


def render_semantic_badge(similarity: float) -> str:
    """Return HTML for a semantic similarity badge.

    Color-codes the badge based on the similarity percentage:
    - Green (#10B981) for 70% and above.
    - Yellow (#F59E0B) for 50% to 69%.
    - Red (#EF4444) for below 50%.

    Args:
        similarity: Similarity score as a float between 0.0 and 1.0.

    Returns:
        HTML string for the similarity pill badge.
    """
    percentage = int(similarity * 100)
    if similarity >= 0.70:
        color = "#10B981"
    elif similarity >= 0.50:
        color = "#F59E0B"
    else:
        color = "#EF4444"
    return render_pill(f"{percentage}% match", bg_color=color)
