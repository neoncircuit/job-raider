"""
Unit tests for the dedicated manual cover-letter endpoint.

Tests cover:
- Successful generation from a pasted job description
- Optional ?deep=true LLM validation path
- Missing / not-found active profile errors
- Invalid request body (short description, missing fields)
- Graceful fallback when validation raises an exception

Author: Job Raider
Date: 2026-06-29
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.generation.cover_letter_validator import (
    CoverLetterIssue,
    CoverLetterValidationResult,
)
from src.generation.cover_letter_writer import GeneratedCoverLetter


@pytest.fixture
def mock_writer():
    """Mock CoverLetterWriter returning a deterministic cover letter."""
    writer = MagicMock()
    writer.write.return_value = GeneratedCoverLetter(
        content=(
            "Dear Hiring Manager,\n\n"
            "I am excited about the Senior Engineer role at TechCorp. "
            "My work on Job Raider has given me direct experience with scalable systems, "
            "and I have spent several years building backend services with Python and FastAPI. "
            "I would welcome the opportunity to discuss how my skills align with TechCorp's goals.\n\n"
            "Thank you for considering my application.\n\n"
            "Sincerely,\nAlex Chen"
        ),
        highlighted_experiences=[{"name": "Job Raider", "reason": "Relevant project"}],
        word_count=80,
        model_used="qwen2.5:7b",
    )
    return writer


@pytest.fixture
def mock_selector():
    """Mock ResumeSelector returning a deterministic selection strategy."""
    selector = MagicMock()
    selection = MagicMock()
    selection.selected_projects = [{"name": "Job Raider", "reason": "Relevant project"}]
    selection.keywords_to_emphasize = ["Python", "FastAPI"]
    selection.key_achievements = ["Built scalable system"]
    selector.select.return_value = selection
    return selector


@pytest.fixture
def mock_validator():
    """Mock CoverLetterValidator returning deterministic results."""
    validator = MagicMock()
    validator.validate.return_value = CoverLetterValidationResult(
        is_valid=True,
        score=85,
        issues=[],
        word_count=80,
        structure_score=80,
        content_score=90,
        tone_score=85,
        recommendation="approve",
        details={
            "paragraph_count": 5,
            "has_generic_opening": False,
            "has_call_to_action": True,
            "company_mentioned": True,
            "job_title_mentioned": True,
            "referenced_projects": ["Job Raider"],
        },
    )
    validator.validate_with_llm.return_value = CoverLetterValidationResult(
        is_valid=True,
        score=92,
        issues=[],
        word_count=80,
        structure_score=90,
        content_score=95,
        tone_score=90,
        recommendation="approve",
        details={"llm_feedback": ["Strong personalization"]},
    )
    return validator


@pytest.fixture
def client(mock_writer, mock_selector, mock_validator):
    """FastAPI test client with mocked cover-letter dependencies."""
    profile = {
        "profile": {
            "name": "Alex Chen",
            "contact": {
                "email": "alex.chen@example.com",
                "location": "San Francisco, CA",
            },
            "targets": {
                "keywords": ["Software Engineer"],
                "locations": ["San Francisco, CA"],
            },
            "skills": [],
            "experience": [],
            "projects": [],
            "education": [],
        }
    }

    with patch(
        "src.generation.cover_letter_service.create_router", return_value=MagicMock()
    ), patch(
        "src.generation.cover_letter_service.ResumeSelector", return_value=mock_selector
    ), patch(
        "src.generation.cover_letter_service.CoverLetterWriter",
        return_value=mock_writer,
    ), patch(
        "src.generation.cover_letter_service.CoverLetterValidator",
        return_value=mock_validator,
    ), patch(
        "src.api.routes.cover_letter.stored_profiles",
        {"profile-1": profile},
        create=True,
    ), patch(
        "src.api.routes.cover_letter.active_profile_id", "profile-1", create=True
    ):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


class TestGenerateManualCoverLetter:
    """Tests for POST /api/cover-letter/manual."""

    def test_manual_cover_letter_returns_validation(self, client):
        """Should return the generated letter and deterministic validation."""
        resp = client.post(
            "/api/cover-letter/manual",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Build scalable systems with Python and FastAPI. " * 5,
                "location": "Remote",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["job_id"].startswith("manual-")
        assert "content" in data["cover_letter"]
        assert data["cover_letter"]["model_used"] == "qwen2.5:7b"
        assert data["validation"]["is_valid"] is True
        assert data["validation"]["score"] == 85
        assert data["validation"]["recommendation"] == "approve"
        assert data["validation"]["details"]["referenced_projects"] == ["Job Raider"]

    def test_manual_cover_letter_with_deep_uses_llm(self, client):
        """Should call validate_with_llm when ?deep=true is passed."""
        resp = client.post(
            "/api/cover-letter/manual?deep=true",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Build scalable systems with Python and FastAPI. " * 5,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["score"] == 92
        assert data["validation"]["details"]["llm_feedback"] == [
            "Strong personalization"
        ]

    def test_manual_cover_letter_with_issues(self, client, mock_validator):
        """Should surface validation issues in the response."""
        mock_validator.validate.return_value = CoverLetterValidationResult(
            is_valid=False,
            score=55,
            issues=[CoverLetterIssue.MISSING_COMPANY, CoverLetterIssue.TOO_SHORT],
            word_count=80,
            structure_score=60,
            content_score=50,
            tone_score=55,
            recommendation="reject",
            details={},
        )

        resp = client.post(
            "/api/cover-letter/manual",
            json={
                "title": "Senior Engineer",
                "company": "OtherCorp",
                "description": "Build scalable systems with Python and FastAPI. " * 5,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["is_valid"] is False
        assert data["validation"]["recommendation"] == "reject"
        assert CoverLetterIssue.MISSING_COMPANY.value in data["validation"]["issues"]

    def test_manual_cover_letter_validation_failure_returns_fallback(
        self, client, mock_validator
    ):
        """Should return the cover letter with a permissive fallback on validation error."""
        mock_validator.validate.side_effect = RuntimeError("validation exploded")

        resp = client.post(
            "/api/cover-letter/manual",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Build scalable systems with Python and FastAPI. " * 5,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cover_letter"]["content"]
        assert data["validation"]["is_valid"] is True
        assert data["validation"]["recommendation"] == "approve"

    def test_manual_cover_letter_without_active_profile(self, client):
        """Should return 400 when no active profile exists."""
        with patch("src.api.routes.cover_letter.active_profile_id", None, create=True):
            resp = client.post(
                "/api/cover-letter/manual",
                json={
                    "title": "Senior Engineer",
                    "company": "TechCorp",
                    "description": "Build scalable systems with Python and FastAPI. "
                    * 5,
                },
            )

        assert resp.status_code == 400
        assert "No active profile found" in resp.json()["detail"]

    def test_manual_cover_letter_profile_not_found(self, client):
        """Should return 404 when the active profile ID is missing from storage."""
        with patch(
            "src.api.routes.cover_letter.stored_profiles", {}, create=True
        ), patch(
            "src.api.routes.cover_letter.active_profile_id", "missing", create=True
        ):
            resp = client.post(
                "/api/cover-letter/manual",
                json={
                    "title": "Senior Engineer",
                    "company": "TechCorp",
                    "description": "Build scalable systems with Python and FastAPI. "
                    * 5,
                },
            )

        assert resp.status_code == 404
        assert "Profile missing not found" in resp.json()["detail"]

    def test_manual_cover_letter_rejects_short_description(self, client):
        """Should reject descriptions shorter than the minimum length."""
        resp = client.post(
            "/api/cover-letter/manual",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Too short.",
            },
        )

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert any("description" in str(err).lower() for err in detail)

    def test_manual_cover_letter_rejects_missing_title(self, client):
        """Should reject a request missing the job title."""
        resp = client.post(
            "/api/cover-letter/manual",
            json={
                "company": "TechCorp",
                "description": "Build scalable systems with Python and FastAPI. " * 5,
            },
        )

        assert resp.status_code == 422
