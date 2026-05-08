"""
Tests for formatting utility functions.

Validates currency, duration, datetime, percentage, text truncation,
and salary range formatting.
"""

from __future__ import annotations

from src.utils.formatting import (
    format_currency,
    format_date,
    format_datetime,
    format_duration,
    format_percentage,
    format_salary_range,
    truncate_text,
)


class TestFormatCurrency:
    """Tests for format_currency."""

    def test_positive_value(self) -> None:
        assert format_currency(1234.56) == "$1,234.56"

    def test_zero(self) -> None:
        assert format_currency(0) == "$0.00"

    def test_none(self) -> None:
        assert format_currency(None) == "$0.00"

    def test_integer(self) -> None:
        assert format_currency(100) == "$100.00"

    def test_large_value(self) -> None:
        assert format_currency(1000000) == "$1,000,000.00"


class TestFormatDuration:
    """Tests for format_duration."""

    def test_seconds_only(self) -> None:
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(150) == "2m 30s"

    def test_hours_and_minutes(self) -> None:
        assert format_duration(3900) == "1h 5m"

    def test_zero(self) -> None:
        assert format_duration(0) == "0s"

    def test_none(self) -> None:
        assert format_duration(None) == "0s"

    def test_negative(self) -> None:
        assert format_duration(-5) == "0s"

    def test_exact_minute(self) -> None:
        assert format_duration(60) == "1m 0s"

    def test_exact_hour(self) -> None:
        assert format_duration(3600) == "1h 0m"


class TestFormatDatetime:
    """Tests for format_datetime."""

    def test_valid_iso(self) -> None:
        result = format_datetime("2026-04-22T10:30:00")
        assert "Apr 22, 2026" in result
        assert "10:30" in result

    def test_none(self) -> None:
        assert format_datetime(None) == "N/A"

    def test_empty_string(self) -> None:
        assert format_datetime("") == "N/A"

    def test_with_z_suffix(self) -> None:
        result = format_datetime("2026-04-22T10:30:00Z")
        assert "Apr 22, 2026" in result

    def test_invalid_format(self) -> None:
        assert format_datetime("not-a-date") == "not-a-date"


class TestFormatDate:
    """Tests for format_date."""

    def test_valid_iso(self) -> None:
        result = format_date("2026-04-22")
        assert result == "Apr 22, 2026"

    def test_none(self) -> None:
        assert format_date(None) == "N/A"


class TestFormatPercentage:
    """Tests for format_percentage."""

    def test_positive(self) -> None:
        assert format_percentage(85.3) == "85.3%"

    def test_zero(self) -> None:
        assert format_percentage(0) == "0.0%"

    def test_none(self) -> None:
        assert format_percentage(None) == "0.0%"

    def test_custom_decimals(self) -> None:
        assert format_percentage(85.333, decimals=2) == "85.33%"

    def test_zero_decimals(self) -> None:
        assert format_percentage(85.0, decimals=0) == "85%"

    def test_100(self) -> None:
        assert format_percentage(100) == "100.0%"


class TestTruncateText:
    """Tests for truncate_text."""

    def test_short_text(self) -> None:
        assert truncate_text("Hello", 100) == "Hello"

    def test_exact_length(self) -> None:
        text = "a" * 300
        assert truncate_text(text, 300) == text

    def test_long_text(self) -> None:
        text = "a" * 400
        result = truncate_text(text, 300)
        assert len(result) == 303  # 300 + "..."
        assert result.endswith("...")

    def test_none(self) -> None:
        assert truncate_text(None) == ""

    def test_empty(self) -> None:
        assert truncate_text("") == ""


class TestFormatSalaryRange:
    """Tests for format_salary_range."""

    def test_with_min_max(self) -> None:
        result = format_salary_range({"min": 80000, "max": 120000})
        assert result == "$80,000.00 - $120,000.00"

    def test_string_value(self) -> None:
        assert format_salary_range("$100k-$150k") == "$100k-$150k"

    def test_none(self) -> None:
        assert format_salary_range(None) == "Not disclosed"

    def test_min_only(self) -> None:
        result = format_salary_range({"min": 80000})
        assert "From" in result

    def test_max_only(self) -> None:
        result = format_salary_range({"max": 120000})
        assert "Up to" in result

    def test_empty_dict(self) -> None:
        assert format_salary_range({}) == "Not disclosed"
