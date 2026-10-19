"""
Unit tests for the API-key authentication dependency.

Author: Job Raider
Date: 2026-07-10
Updated: 2026-10-19 - AUTH_DISABLED=1 is the only bypass
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from src.api import auth as auth_module


@pytest.fixture(autouse=True)
def _reset_auth_state(monkeypatch):
    """Reset the mutable auth state before each test.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Yields:
        None.
    """
    monkeypatch.setattr(auth_module, "_warned_disabled", False)
    yield


async def _verify(header_value: str = "") -> None:
    """Call the auth dependency directly with a plain header value.

    Args:
        header_value: X-API-Key header value.

    Returns:
        None when authorized.
    """
    return await auth_module.verify_api_key(x_api_key=header_value)


class TestVerifyApiKey:
    """Tests for ``verify_api_key`` with and without ``AUTH_DISABLED``."""

    def test_empty_key_without_auth_disabled_rejects(self, monkeypatch):
        """An empty API_KEY without AUTH_DISABLED returns 401."""
        monkeypatch.setattr(auth_module, "_API_KEY", "")
        monkeypatch.setattr(auth_module, "_AUTH_DISABLED", False)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_verify())
        assert exc_info.value.status_code == 401

    def test_auth_disabled_allows_requests(self, monkeypatch):
        """AUTH_DISABLED=1 allows requests without a key."""
        monkeypatch.setattr(auth_module, "_API_KEY", "")
        monkeypatch.setattr(auth_module, "_AUTH_DISABLED", True)

        result = asyncio.run(_verify())
        assert result is None

    def test_auth_disabled_logs_warning_only_once(self, monkeypatch, caplog):
        """The AUTH_DISABLED bypass warning is emitted once per process."""
        monkeypatch.setattr(auth_module, "_API_KEY", "")
        monkeypatch.setattr(auth_module, "_AUTH_DISABLED", True)

        with caplog.at_level("WARNING", logger="src.api.auth"):
            asyncio.run(_verify())
            asyncio.run(_verify())

        bypass_messages = [
            record.message
            for record in caplog.records
            if "Authentication bypassed" in record.message
        ]
        assert len(bypass_messages) == 1

    def test_key_set_requires_valid_header(self, monkeypatch):
        """When API_KEY is set, invalid headers are rejected."""
        monkeypatch.setattr(auth_module, "_API_KEY", "dev-secret")
        monkeypatch.setattr(auth_module, "_AUTH_DISABLED", False)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_verify())
        assert exc_info.value.status_code == 401

    def test_key_set_accepts_valid_header(self, monkeypatch):
        """When API_KEY is set, a matching X-API-Key header is accepted."""
        monkeypatch.setattr(auth_module, "_API_KEY", "dev-secret")
        monkeypatch.setattr(auth_module, "_AUTH_DISABLED", False)

        result = asyncio.run(_verify("dev-secret"))
        assert result is None

    def test_invalid_key_rejects_requests(self, monkeypatch):
        """A mismatched key is rejected."""
        monkeypatch.setattr(auth_module, "_API_KEY", "prod-secret")
        monkeypatch.setattr(auth_module, "_AUTH_DISABLED", False)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_verify("wrong-secret"))
        assert exc_info.value.status_code == 401
