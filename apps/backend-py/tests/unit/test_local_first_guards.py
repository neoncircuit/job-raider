"""
Tests for Step 2.6 local-first guards: ollama_host, LinkedIn profile URL,
and TrustedHostMiddleware.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.main import _allowed_hosts
from src.api.settings import APIConfig
from src.linkedin.profile_url import validate_linkedin_profile_url


class TestOllamaHostAllowlist:
    """Settings ollama_host must be a local allowlisted host:port."""

    def test_allows_known_hosts(self) -> None:
        """
        Accept localhost, 127.0.0.1, host.docker.internal, and ollama.

        Returns:
            None.
        """
        for host in (
            "localhost:11434",
            "127.0.0.1:11434",
            "host.docker.internal:11434",
            "ollama:11434",
            "http://localhost:11434",
            "https://127.0.0.1:11434",
        ):
            cfg = APIConfig(ollama_host=host)
            assert cfg.ollama_host

    def test_rejects_remote_and_path(self) -> None:
        """
        Reject remote hosts, file URLs, and path suffixes.

        Returns:
            None.
        """
        for bad in (
            "evil.example.com:11434",
            "http://8.8.8.8:11434",
            "file:///etc/passwd",
            "localhost:11434/admin",
            "http://localhost:11434/v1",
        ):
            with pytest.raises(ValidationError):
                APIConfig(ollama_host=bad)


class TestLinkedInProfileUrl:
    """Profile URLs for Playwright must be https LinkedIn /in/ paths."""

    def test_allows_https_in_profile(self) -> None:
        """
        Accept a normal LinkedIn profile URL.

        Returns:
            None.
        """
        url = "https://www.linkedin.com/in/jane-doe/"
        assert validate_linkedin_profile_url(url) == url

    def test_rejects_file_ip_and_non_linkedin(self) -> None:
        """
        Reject file://, bare IPs, and non-LinkedIn hosts.

        Returns:
            None.
        """
        for bad in (
            "file:///tmp/x",
            "http://www.linkedin.com/in/jane",
            "https://evil.com/in/jane",
            "https://192.168.1.1/in/jane",
            "https://www.linkedin.com/company/acme",
        ):
            with pytest.raises(ValueError):
                validate_linkedin_profile_url(bad)


class TestTrustedHostMiddleware:
    """API rejects unexpected Host headers."""

    def test_default_allowed_hosts_exclude_testserver(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Production defaults omit TestClient's ``testserver`` host.

        Args:
            monkeypatch: Pytest monkeypatch fixture.

        Returns:
            None.
        """
        monkeypatch.delenv("ALLOWED_HOSTS", raising=False)
        hosts = _allowed_hosts()
        assert "testserver" not in hosts
        assert "localhost" in hosts
        assert "127.0.0.1" in hosts
        assert "backend" in hosts

    def test_rejects_unknown_host(self, client: TestClient) -> None:
        """
        A forged Host header is refused.

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        response = client.get("/api/version", headers={"Host": "evil.example"})
        assert response.status_code == 400

    def test_cors_preflight_rejects_unknown_host(self, client: TestClient) -> None:
        """
        A CORS preflight with a forged Host still hits TrustedHost first.

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        response = client.options(
            "/api/health",
            headers={
                "Host": "evil.example",
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400

    def test_allows_testserver(self, client: TestClient) -> None:
        """
        TestClient Host testserver remains allowed.

        Args:
            client: Shared FastAPI TestClient.

        Returns:
            None.
        """
        response = client.get("/api/version")
        assert response.status_code == 200
