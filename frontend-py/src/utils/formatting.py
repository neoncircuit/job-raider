"""
Formatting utilities for the Streamlit dashboard.

Provides consistent formatters for currency, durations, dates,
percentages, and text truncation used across all dashboard pages.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def format_currency(value: float | int | None) -> str:
    """Format a numeric value as a USD currency string.

    Args:
        value: The numeric value to format.

    Returns:
        Formatted currency string (e.g. "$1,234.56" or "$0.00").
    """
    if value is None:
        return "$0.00"
    return f"${value:,.2f}"


def format_duration(seconds: float | int | None) -> str:
    """Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration (e.g. "2m 30s", "1h 15m", "45s").
    """
    if seconds is None or seconds < 0:
        return "0s"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


def format_datetime(iso_string: str | None) -> str:
    """Format an ISO datetime string to a readable format.

    Args:
        iso_string: ISO format datetime string (e.g. "2026-04-22T10:30:00").

    Returns:
        Formatted datetime (e.g. "Apr 22, 2026 10:30 AM") or "N/A".
    """
    if not iso_string:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %I:%M %p")
    except (ValueError, TypeError):
        return iso_string


def format_date(iso_string: str | None) -> str:
    """Format an ISO date string to a short readable format.

    Args:
        iso_string: ISO format date or datetime string.

    Returns:
        Formatted date (e.g. "Apr 22, 2026") or "N/A".
    """
    if not iso_string:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return iso_string


def format_percentage(value: float | int | None, decimals: int = 1) -> str:
    """Format a value as a percentage string.

    Args:
        value: The value to format (0-100 scale).
        decimals: Number of decimal places.

    Returns:
        Formatted percentage (e.g. "85.3%") or "0.0%".
    """
    if value is None:
        return f"0{'.' + '0' * decimals if decimals else ''}%"
    return f"{value:.{decimals}f}%"


def truncate_text(text: str | None, max_length: int = 300) -> str:
    """Truncate text to a maximum length with ellipsis.

    Args:
        text: The text to potentially truncate.
        max_length: Maximum character length before truncation.

    Returns:
        Original or truncated text with "..." appended.
    """
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def format_salary_range(salary_range: Optional[dict | str]) -> str:
    """Format a salary range dict or string for display.

    Args:
        salary_range: Salary data as a dict with min/max/currency or a string.

    Returns:
        Formatted salary string (e.g. "$80,000 - $120,000") or "Not disclosed".
    """
    if not salary_range:
        return "Not disclosed"
    if isinstance(salary_range, str):
        return salary_range
    min_val = salary_range.get("min")
    max_val = salary_range.get("max")
    if min_val and max_val:
        return f"{format_currency(min_val)} - {format_currency(max_val)}"
    if min_val:
        return f"From {format_currency(min_val)}"
    if max_val:
        return f"Up to {format_currency(max_val)}"
    return "Not disclosed"


def format_score(score: float) -> str:
    """Format a score as a string with one decimal place.

    Args:
        score: The score to format

    Returns:
        Formatted score string
    """
    return f"{score:.1f}/100"
