"""
Unit tests for PII-aware logging helpers.

Author: Job Raider
Date: 2026-07-10
"""

from src.utils.logging_helpers import sanitize_for_log, summarize_payload


class TestSanitizeForLog:
    """Tests for ``sanitize_for_log``."""

    def test_truncates_long_string(self):
        """Long strings are truncated to the configured limit."""
        long_value = "x" * 1000
        result = sanitize_for_log(long_value, max_length=100)
        assert result.endswith("...")
        assert len(result) == 100

    def test_redacts_sensitive_dict_keys(self):
        """Values for sensitive keys are replaced with a redaction marker."""
        payload = {
            "name": "Alex Chen",
            "email": "alex@example.com",
            "password": "super-secret",
            "api_key": "sk-12345",
        }
        result = sanitize_for_log(payload)
        assert '"password": "[REDACTED]"' in result
        assert '"api_key": "[REDACTED]"' in result
        assert '"name": "Alex Chen"' in result

    def test_redacts_emails_in_string_values(self):
        """Email addresses embedded in strings are redacted."""
        payload = {"bio": "Contact me at alex@example.com for details."}
        result = sanitize_for_log(payload)
        assert "[EMAIL]" in result
        assert "alex@example.com" not in result

    def test_handles_nested_structures(self):
        """Sanitization recurses into nested dicts and lists."""
        payload = {
            "users": [
                {"name": "Alice", "token": "abc"},
                {"name": "Bob", "secret": "xyz"},
            ]
        }
        result = sanitize_for_log(payload)
        assert '"token": "[REDACTED]"' in result
        assert '"secret": "[REDACTED]"' in result
        assert '"name": "Alice"' in result


class TestSummarizePayload:
    """Tests for ``summarize_payload``."""

    def test_summarizes_dict_keys(self):
        """Dictionaries are summarized by their keys."""
        result = summarize_payload({"profile": {}, "jobs": []})
        assert "dict with keys" in result
        assert "profile" in result
        assert "jobs" in result

    def test_summarizes_list_length(self):
        """Lists are summarized by their length."""
        result = summarize_payload([1, 2, 3])
        assert "3 item(s)" in result

    def test_truncates_long_summary(self):
        """Summaries are truncated when they exceed the max length."""
        result = summarize_payload({str(i): i for i in range(100)}, max_length=50)
        assert result.endswith("...")
        assert len(result) == 50
