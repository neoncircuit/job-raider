"""
Logging helpers for safe, PII-aware log output.

Free-form dictionaries (request payloads, task context, etc.) must be sanitized
before they are written to logs to avoid accidentally leaking passwords, API
keys, tokens, or personal information.
"""

import json
import re
from typing import Any, Dict

# Keys that commonly hold sensitive values. Matching values are redacted.
_SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "api_secret",
    "auth",
    "authorization",
    "cookie",
    "session",
    "email",
    "phone",
    "mobile",
    "ssn",
    "social_security",
    "credit_card",
    "card_number",
    "cvv",
}

# Simple regex for email-like strings.
_EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def _is_sensitive_key(key: str) -> bool:
    """Return True if ``key`` indicates a sensitive field."""
    normalized = key.lower().replace("-", "_").replace(" ", "_")
    return any(sensitive in normalized for sensitive in _SENSITIVE_KEYS)


def _sanitize_value(value: Any, max_length: int = 500) -> Any:
    """
    Recursively sanitize a value for logging.

    Args:
        value: The value to sanitize.
        max_length: Maximum length for individual string values.

    Returns:
        A sanitized value suitable for JSON serialization.
    """
    if isinstance(value, str):
        value = _EMAIL_RE.sub("[EMAIL]", value)
        if len(value) > max_length:
            return value[: max_length - 3] + "..."
        return value

    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                result[key] = "[REDACTED]"
            else:
                result[key] = _sanitize_value(item, max_length=max_length)
        return result

    if isinstance(value, list):
        return [_sanitize_value(item, max_length=max_length) for item in value]

    if isinstance(value, tuple):
        return [_sanitize_value(item, max_length=max_length) for item in value]

    return value


def sanitize_for_log(value: Any, max_length: int = 500) -> str:
    """
    Convert a value to a log-safe string.

    Strings are truncated to ``max_length`` characters. Dictionaries and lists
    are serialized to JSON with sensitive keys redacted and long strings
    truncated. Scalars use their default string representation.

    Args:
        value: The value to sanitize.
        max_length: Maximum number of characters for the returned string.

    Returns:
        A log-safe string representation of ``value``.
    """
    sanitized = _sanitize_value(value, max_length=max_length)
    text = json.dumps(sanitized, default=str, ensure_ascii=False)
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def summarize_payload(payload: Any, max_length: int = 500) -> str:
    """
    Produce a short, log-safe summary of a payload.

    Useful when only a high-level shape description is needed (for example,
    ``profile keys: name, experience``) rather than the full payload.

    Args:
        payload: The payload to summarize.
        max_length: Maximum length of the returned summary.

    Returns:
        A short summary string.
    """
    if isinstance(payload, dict):
        keys = ", ".join(str(key) for key in payload.keys())
        summary = f"dict with keys: {keys}"
    elif isinstance(payload, list):
        summary = f"list with {len(payload)} item(s)"
    else:
        summary = sanitize_for_log(payload, max_length=max_length)

    if len(summary) > max_length:
        return summary[: max_length - 3] + "..."
    return summary
