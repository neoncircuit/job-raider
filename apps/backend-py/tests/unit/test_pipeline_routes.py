"""
Unit tests for pipeline API routes.

Tests cover:
- Starting a pipeline with a stored active profile
- Starting a pipeline with explicit profile_data
- Rejection when no profile is available

Author: Job Raider
Date: 2026-07-21
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def valid_profile():
    """Return a minimal valid UserProfile serialised as a dict."""
    return {
        "name": "Test User",
        "contact": {
            "email": "test@example.com",
            "location": "Singapore",
        },
        "summary": "A test profile.",
    }


@pytest.fixture
def client(valid_profile):
    """FastAPI test client with mocked profile state."""
    from src.api.auth import verify_api_key
    from src.api.main import app
    from src.models.user_profile import UserProfile

    stored = {
        "profile-1": {
            "profile": UserProfile(**valid_profile),
            "created_at": datetime.now(),
        }
    }

    with patch(
        "src.api.routes.pipeline.profile_state.stored_profiles",
        stored,
        create=True,
    ), patch(
        "src.api.routes.pipeline.profile_state.active_profile_id",
        "profile-1",
        create=True,
    ), patch(
        "src.api.routes.pipeline.PipelineOrchestrator"
    ) as mock_orchestrator:
        # Background tasks are not executed by TestClient, but the
        # orchestrator is instantiated inside the background task; mocking it
        # keeps route tests fast and isolated.
        mock_orchestrator.return_value.run.return_value = None

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


class TestStartPipeline:
    """Tests for POST /api/pipeline/start."""

    def test_start_with_active_profile_returns_run_id(self, client):
        """Should accept a request when a stored active profile exists."""
        resp = client.post(
            "/api/pipeline/start",
            json={
                "keywords": ["python"],
                "locations": ["Singapore"],
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["run_id"].startswith("run_")

    def test_start_with_explicit_profile_data_returns_run_id(
        self, client, valid_profile
    ):
        """Should accept a request with inline profile_data."""
        resp = client.post(
            "/api/pipeline/start",
            json={
                "keywords": ["python"],
                "locations": ["Singapore"],
                "profile_data": valid_profile,
            },
        )

        assert resp.status_code == 200
        assert "run_id" in resp.json()

    def test_start_without_profile_returns_400(self, client):
        """Should reject a request when no active profile or profile_data is supplied."""
        # Simulate no active profile by overriding the fixture's active id.
        with patch(
            "src.api.routes.pipeline.profile_state.active_profile_id",
            None,
            create=True,
        ):
            resp = client.post(
                "/api/pipeline/start",
                json={
                    "keywords": ["python"],
                    "locations": ["Singapore"],
                },
            )

        assert resp.status_code == 400
        assert "profile" in resp.json()["message"].lower()

    def test_start_with_invalid_profile_data_returns_400(self, client):
        """Should reject malformed profile_data with a clear error."""
        resp = client.post(
            "/api/pipeline/start",
            json={
                "keywords": ["python"],
                "locations": ["Singapore"],
                "profile_data": {"name": "Missing contact"},
            },
        )

        assert resp.status_code == 400
        assert "profile data" in resp.json()["message"].lower()

    def test_start_accepts_mycareersfuture_and_reserved_sources(self, client):
        """Discover may send MCF plus reserved board ids that have no scraper yet."""
        resp = client.post(
            "/api/pipeline/start",
            json={
                "keywords": ["python"],
                "locations": ["Singapore"],
                "sources": [
                    "linkedin",
                    "jsearch",
                    "mycareersfuture",
                    "careersatgov",
                    "jobstreet",
                ],
                "mode": "discover",
            },
        )

        assert resp.status_code == 200
        assert "run_id" in resp.json()

    def test_start_rejects_unknown_source(self, client):
        """Unknown source ids still fail validation."""
        resp = client.post(
            "/api/pipeline/start",
            json={
                "keywords": ["python"],
                "locations": ["Singapore"],
                "sources": ["not-a-board"],
            },
        )

        assert resp.status_code == 422
