"""
Smoke tests for POST /api/cover-letter/assess.

These tests hit the route end-to-end through the FastAPI app with a real
profile and job description. The underlying JobMatcher is a pure heuristic
scorer (no LLM or network calls), so only the profile-state globals and API
key auth are patched/overridden, mirroring test_cover_letter_manual.py.
"""

from typing import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.models.user_profile import UserProfile


@pytest.fixture
def client(sample_user_profile: UserProfile) -> Iterator[TestClient]:
    """FastAPI test client with an active profile and auth bypassed.

    Args:
        sample_user_profile: Canonical UserProfile fixture from conftest.

    Returns:
        A TestClient whose requests resolve ``profile-1`` as the active
        profile and skip API key verification.
    """
    profile_entry = {
        "profile": sample_user_profile,
        "resume_path": "/tmp/resume.pdf",
        "original_filename": "resume.pdf",
    }

    with patch(
        "src.api.routes.profile.stored_profiles",
        {"profile-1": profile_entry},
        create=True,
    ), patch("src.api.routes.profile.active_profile_id", "profile-1", create=True):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


class TestAssessJobMatch:
    """Tests for POST /api/cover-letter/assess."""

    def test_assess_returns_match_result(self, client: TestClient) -> None:
        """Should return a heuristic fit score and structured breakdown."""
        resp = client.post(
            "/api/cover-letter/assess",
            json={
                "title": "Senior Python Engineer",
                "company": "Tech Corp",
                "description": (
                    "We are looking for a senior Python engineer with Django "
                    "and FastAPI experience. You will design scalable APIs "
                    "and mentor junior developers. AWS and PostgreSQL "
                    "experience is a plus."
                ),
                "location": "Remote",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert 0 <= data["score"] <= 100
        assert isinstance(data["passed_threshold"], bool)
        assert data["recommendation"] in ("apply", "maybe", "skip")
        assert isinstance(data["breakdown"], dict)
        assert isinstance(data["matched_keywords"], list)
        assert isinstance(data["missing_skills"], list)
        assert data["scam_risk"] in ("low", "medium", "high")
        assert isinstance(data["scam_flags"], list)
        assert isinstance(data["reasoning"], str)

    def test_assess_without_active_profile_returns_400(
        self, client: TestClient
    ) -> None:
        """Should return 400 when no active profile exists."""
        with patch("src.api.routes.profile.active_profile_id", None, create=True):
            resp = client.post(
                "/api/cover-letter/assess",
                json={
                    "title": "Senior Python Engineer",
                    "company": "Tech Corp",
                    "description": "A long enough description to pass validation. " * 3,
                },
            )

        assert resp.status_code == 400
        assert "No active profile found" in resp.json()["message"]
