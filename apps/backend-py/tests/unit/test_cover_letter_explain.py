"""
Tests for POST /api/cover-letter/explain-fit and /api/cover-letter/explain-letter.

The LLM router is patched at its import site in cover_letter.py so these tests
never make a network or local-model call, mirroring the profile-state and auth
patches in test_cover_letter_assess.py.
"""

import json
from typing import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models.user_profile import UserProfile

VALID_EXPLANATION_JSON = json.dumps(
    {
        "strengths": ["Strong Python and FastAPI background"],
        "concerns": ["No direct AWS experience listed"],
        "improvements": ["Highlight cloud deployment work, if any"],
    }
)


def _mock_router(content: str) -> MagicMock:
    """Build a MagicMock LLM router whose async generate call returns content.

    Args:
        content: Raw text to return as the mocked LLM response's `.content`.

    Returns:
        A MagicMock standing in for the object `create_router()` returns.
    """
    router = MagicMock()
    router.generate_async = AsyncMock(return_value=MagicMock(content=content))
    return router


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


VALID_JOB_PAYLOAD = {
    "title": "Senior Python Engineer",
    "company": "Tech Corp",
    "description": (
        "We are looking for a senior Python engineer with Django and "
        "FastAPI experience. You will design scalable APIs and mentor "
        "junior developers. AWS and PostgreSQL experience is a plus."
    ),
    "location": "Remote",
}


class TestExplainFit:
    """Tests for POST /api/cover-letter/explain-fit."""

    def test_returns_explanation(self, client: TestClient) -> None:
        """Should return strengths/concerns/improvements grounded in the fit score."""
        with patch(
            "src.api.routes.cover_letter.create_router",
            return_value=_mock_router(VALID_EXPLANATION_JSON),
        ):
            resp = client.post("/api/cover-letter/explain-fit", json=VALID_JOB_PAYLOAD)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["strengths"], list) and data["strengths"]
        assert isinstance(data["concerns"], list) and data["concerns"]
        assert isinstance(data["improvements"], list) and data["improvements"]
        assert isinstance(data["fit_score"], int)
        assert 0 <= data["fit_score"] <= 100

    def test_without_active_profile_returns_400(self, client: TestClient) -> None:
        """Should return 400 when no active profile exists."""
        with patch("src.api.routes.profile.active_profile_id", None, create=True):
            resp = client.post("/api/cover-letter/explain-fit", json=VALID_JOB_PAYLOAD)

        assert resp.status_code == 400
        assert "No active profile found" in resp.json()["message"]

    def test_short_description_returns_422(self, client: TestClient) -> None:
        """Should return 422 when the description is under the 50-char minimum."""
        payload = {**VALID_JOB_PAYLOAD, "description": "Too short."}
        resp = client.post("/api/cover-letter/explain-fit", json=payload)

        assert resp.status_code == 422

    def test_malformed_llm_json_returns_500(self, client: TestClient) -> None:
        """Should return 500 when the LLM response is not parseable JSON."""
        with patch(
            "src.api.routes.cover_letter.create_router",
            return_value=_mock_router("not json at all"),
        ):
            resp = client.post("/api/cover-letter/explain-fit", json=VALID_JOB_PAYLOAD)

        assert resp.status_code == 500


class TestExplainLetter:
    """Tests for POST /api/cover-letter/explain-letter (no active profile required)."""

    def test_returns_explanation(self, client: TestClient) -> None:
        """Should return strengths/concerns/improvements for the supplied letter."""
        payload = {
            **VALID_JOB_PAYLOAD,
            "content": "Dear Hiring Manager, I am excited to apply for this role...",
        }
        with patch(
            "src.api.routes.cover_letter.create_router",
            return_value=_mock_router(VALID_EXPLANATION_JSON),
        ):
            resp = client.post("/api/cover-letter/explain-letter", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["strengths"], list) and data["strengths"]
        assert isinstance(data["concerns"], list) and data["concerns"]
        assert isinstance(data["improvements"], list) and data["improvements"]

    def test_without_active_profile_still_succeeds(self, client: TestClient) -> None:
        """Should succeed even without an active profile (no profile dependency)."""
        payload = {
            **VALID_JOB_PAYLOAD,
            "content": "Dear Hiring Manager, I am excited to apply for this role...",
        }
        with patch(
            "src.api.routes.profile.active_profile_id", None, create=True
        ), patch(
            "src.api.routes.cover_letter.create_router",
            return_value=_mock_router(VALID_EXPLANATION_JSON),
        ):
            resp = client.post("/api/cover-letter/explain-letter", json=payload)

        assert resp.status_code == 200

    def test_malformed_llm_json_returns_500(self, client: TestClient) -> None:
        """Should return 500 when the LLM response is not parseable JSON."""
        payload = {
            **VALID_JOB_PAYLOAD,
            "content": "Dear Hiring Manager, I am excited to apply for this role...",
        }
        with patch(
            "src.api.routes.cover_letter.create_router",
            return_value=_mock_router("not json at all"),
        ):
            resp = client.post("/api/cover-letter/explain-letter", json=payload)

        assert resp.status_code == 500
