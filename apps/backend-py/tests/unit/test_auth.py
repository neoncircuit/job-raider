"""
Unit tests for the API-key authentication dependency.

Author: Job Raider
Date: 2026-07-10
"""

import asyncio

import pytest
from fastapi import HTTPException

from src.api import auth as auth_module


@pytest.fixture(autouse=True)
def _reset_auth_state(monkeypatch):
    """Reset the mutable auth state before each test."""
    monkeypatch.setattr(auth_module, "_warned_missing", False)


async def _verify(header_value: str = "") -> None:
    """Call the auth dependency directly with a plain header value."""
    return await auth_module.verify_api_key(x_api_key=header_value)


class TestVerifyApiKey:
    """Tests for ``verify_api_key`` in development and production modes."""

    def test_development_no_key_bypasses_auth(self, monkeypatch):
        """In development, a missing API_KEY bypasses auth after warning."""
        monkeypatch.setattr(auth_module, "_API_KEY", "")
        monkeypatch.setattr(auth_module, "_ENVIRONMENT", "development")

        result = asyncio.run(_verify())
        assert result is None

    def test_development_with_key_requires_valid_header(self, monkeypatch):
        """In development, when API_KEY is set, invalid headers are rejected."""
        monkeypatch.setattr(auth_module, "_API_KEY", "dev-secret")
        monkeypatch.setattr(auth_module, "_ENVIRONMENT", "development")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_verify())
        assert exc_info.value.status_code == 401

    def test_development_with_key_accepts_valid_header(self, monkeypatch):
        """In development, a matching X-API-Key header is accepted."""
        monkeypatch.setattr(auth_module, "_API_KEY", "dev-secret")
        monkeypatch.setattr(auth_module, "_ENVIRONMENT", "development")

        result = asyncio.run(_verify("dev-secret"))
        assert result is None

    def test_production_no_key_rejects_requests(self, monkeypatch):
        """In production, an unset API_KEY causes all requests to fail closed."""
        monkeypatch.setattr(auth_module, "_API_KEY", "")
        monkeypatch.setattr(auth_module, "_ENVIRONMENT", "production")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_verify())
        assert exc_info.value.status_code == 401
        assert "Invalid or missing API key" in exc_info.value.detail

    def test_production_invalid_key_rejects_requests(self, monkeypatch):
        """In production, a mismatched key is rejected."""
        monkeypatch.setattr(auth_module, "_API_KEY", "prod-secret")
        monkeypatch.setattr(auth_module, "_ENVIRONMENT", "production")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(_verify("wrong-secret"))
        assert exc_info.value.status_code == 401

    def test_production_valid_key_accepts_requests(self, monkeypatch):
        """In production, a matching key is accepted."""
        monkeypatch.setattr(auth_module, "_API_KEY", "prod-secret")
        monkeypatch.setattr(auth_module, "_ENVIRONMENT", "production")

        result = asyncio.run(_verify("prod-secret"))
        assert result is None

    def test_development_bypass_logs_warning_only_once(self, monkeypatch, caplog):
        """The development bypass warning is emitted once per process."""
        monkeypatch.setattr(auth_module, "_API_KEY", "")
        monkeypatch.setattr(auth_module, "_ENVIRONMENT", "development")

        with caplog.at_level("WARNING", logger="src.api.auth"):
            asyncio.run(_verify())
            asyncio.run(_verify())

        bypass_messages = [
            record.message
            for record in caplog.records
            if "Authentication bypassed" in record.message
        ]
        assert len(bypass_messages) == 1
