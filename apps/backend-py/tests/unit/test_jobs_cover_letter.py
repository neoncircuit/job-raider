"""
Unit tests for the cover-letter generation endpoint.

Tests cover:
- Successful generation with deterministic validation
- Optional ?deep=true LLM validation path
- Missing / not-found active profile errors
- Graceful fallback when validation raises an exception

Author: Job Raider
Date: 2026-06-29
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.generation.cover_letter_reviewer import CoverLetterReviewResult
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
            "I am excited about the Senior Engineer role at TechCorp. "
            "My work on Job Raider has given me direct experience with scalable systems. "
            "I would welcome the opportunity to discuss how my skills align with TechCorp's goals. "
            "Thank you for considering my application."
        ),
        highlighted_experiences=[{"name": "Job Raider", "reason": "Relevant project"}],
        word_count=48,
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
        word_count=48,
        structure_score=80,
        content_score=90,
        tone_score=85,
        recommendation="approve",
        details={
            "paragraph_count": 1,
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
        word_count=48,
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
        "src.generation.cover_letter_service.CoverLetterReviewer"
    ) as mock_reviewer, patch(
        "src.api.routes.jobs.stored_profiles", {"profile-1": profile}, create=True
    ), patch(
        "src.api.routes.jobs.active_profile_id", "profile-1", create=True
    ):
        mock_reviewer.return_value.review.return_value = CoverLetterReviewResult(
            critique="Looks good.",
            rewrite_needed=False,
            model_used="qwen2.5:3b",
        )
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


class TestGenerateCoverLetter:
    """Tests for POST /api/jobs/{job_id}/cover-letter."""

    def test_generate_cover_letter_returns_validation(self, client):
        """Should return the generated letter and deterministic validation."""
        resp = client.post(
            "/api/jobs/job-123/cover-letter",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Build scalable systems.",
                "location": "Remote",
                "source": "linkedin",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["job_id"] == "job-123"
        assert "content" in data["cover_letter"]
        assert data["cover_letter"]["model_used"] == "qwen2.5:7b"
        assert data["validation"]["is_valid"] is True
        assert data["validation"]["score"] == 85
        assert data["validation"]["recommendation"] == "approve"
        assert data["validation"]["details"]["referenced_projects"] == ["Job Raider"]

    def test_generate_cover_letter_with_deep_uses_llm(self, client):
        """Should call validate_with_llm when ?deep=true is passed."""
        resp = client.post(
            "/api/jobs/job-123/cover-letter?deep=true",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Build scalable systems.",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["score"] == 92
        assert data["validation"]["details"]["llm_feedback"] == [
            "Strong personalization"
        ]

    def test_generate_cover_letter_with_review_records_metadata(self, client):
        """Should include review metadata when ?review=true is passed."""
        resp = client.post(
            "/api/jobs/job-123/cover-letter?review=true",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Build scalable systems.",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["details"]["review"]["critique"] == "Looks good."
        assert data["validation"]["details"]["review"]["rewrite_needed"] is False
        assert data["validation"]["details"]["review"]["rewrite_count"] == 0
        assert data["validation"]["details"]["review"]["model_used"] == "qwen2.5:3b"

    def test_generate_cover_letter_with_review_and_deep(self, client):
        """Should compose review and deep flags independently."""
        resp = client.post(
            "/api/jobs/job-123/cover-letter?review=true&deep=true",
            json={
                "title": "Senior Engineer",
                "company": "TechCorp",
                "description": "Build scalable systems.",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["score"] == 92
        assert data["validation"]["details"]["llm_feedback"] == [
            "Strong personalization"
        ]
        assert data["validation"]["details"]["review"]["model_used"] == "qwen2.5:3b"

    def test_generate_cover_letter_with_issues(self, client, mock_validator):
        """Should surface validation issues in the response."""
        mock_validator.validate.return_value = CoverLetterValidationResult(
            is_valid=False,
            score=55,
            issues=[CoverLetterIssue.MISSING_COMPANY, CoverLetterIssue.TOO_SHORT],
            word_count=48,
            structure_score=60,
            content_score=50,
            tone_score=55,
            recommendation="reject",
            details={},
        )

        resp = client.post(
            "/api/jobs/job-123/cover-letter",
            json={"title": "Senior Engineer", "company": "OtherCorp"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["validation"]["is_valid"] is False
        assert data["validation"]["recommendation"] == "reject"
        assert CoverLetterIssue.MISSING_COMPANY.value in data["validation"]["issues"]

    def test_generate_cover_letter_validation_failure_returns_fallback(
        self, client, mock_validator
    ):
        """Should return the cover letter with a permissive fallback on validation error."""
        mock_validator.validate.side_effect = RuntimeError("validation exploded")

        resp = client.post(
            "/api/jobs/job-123/cover-letter",
            json={"title": "Senior Engineer", "company": "TechCorp"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cover_letter"]["content"]
        assert data["validation"]["is_valid"] is True
        assert data["validation"]["recommendation"] == "approve"

    def test_generate_cover_letter_without_active_profile(self, client):
        """Should return 400 when no active profile exists."""
        with patch("src.api.routes.jobs.active_profile_id", None, create=True):
            resp = client.post(
                "/api/jobs/job-123/cover-letter",
                json={"title": "Senior Engineer", "company": "TechCorp"},
            )

        assert resp.status_code == 400
        assert "No active profile found" in resp.json()["message"]

    def test_generate_cover_letter_profile_not_found(self, client):
        """Should return 404 when the active profile ID is missing from storage."""
        with patch("src.api.routes.jobs.stored_profiles", {}, create=True), patch(
            "src.api.routes.jobs.active_profile_id", "missing", create=True
        ):
            resp = client.post(
                "/api/jobs/job-123/cover-letter",
                json={"title": "Senior Engineer", "company": "TechCorp"},
            )

        assert resp.status_code == 404
        assert "Profile missing not found" in resp.json()["message"]
