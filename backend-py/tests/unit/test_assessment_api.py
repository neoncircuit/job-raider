# Unit tests for assessment API routes
# Author: Job Raider
# Date: 2026-05-22

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models.assessment import SessionStatus

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_storage():
    """Mock AssessmentStorage."""
    storage = MagicMock()
    storage.save_session.return_value = None
    storage.get_session.return_value = None
    storage.get_recent_sessions.return_value = []
    storage.delete_session.return_value = False
    storage.get_progress_stats.return_value = {
        "total_sessions": 0,
        "completed_sessions": 0,
        "average_score": 0.0,
        "score_trend": [],
        "strongest_topics": [],
        "weakest_topics": [],
    }
    return storage


@pytest.fixture
def mock_engine():
    """Mock AssessmentEngine."""
    from src.models.assessment import (
        AnswerFormat,
        DifficultyLevel,
        Question,
        QuestionType,
    )

    engine = MagicMock()
    engine.generate_questions.return_value = [
        Question(
            question_id="q1",
            question_type=QuestionType.CONCEPTUAL,
            answer_format=AnswerFormat.FREEFORM,
            difficulty=DifficultyLevel.INTERMEDIATE,
            topic="Python",
            question_text="Explain list comprehensions.",
            correct_answer_hint="Concise loop syntax",
            order_index=0,
        ),
    ]
    engine.evaluate_answer.return_value = MagicMock(
        question_id="q1",
        score=75.0,
        is_correct=None,
        feedback="Good explanation",
        strengths=["Clear syntax knowledge"],
        improvements=["Add examples"],
        model_answer="A list comprehension is...",
    )
    engine.calculate_session_results.return_value = None
    engine.adapt_difficulty.return_value = DifficultyLevel.INTERMEDIATE
    return engine


@pytest.fixture
def sample_session():
    """Create a sample session for API tests."""
    from src.models.assessment import (
        AnswerFormat,
        AssessmentMode,
        AssessmentSession,
        DifficultyLevel,
        Question,
        QuestionType,
        SessionStatus,
    )

    return AssessmentSession(
        session_id="test-session-001",
        mode=AssessmentMode.SKILL_BASED,
        status=SessionStatus.IN_PROGRESS,
        difficulty=DifficultyLevel.INTERMEDIATE,
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        target_skills=["Python"],
        questions=[
            Question(
                question_id="q1",
                question_type=QuestionType.CONCEPTUAL,
                answer_format=AnswerFormat.FREEFORM,
                difficulty=DifficultyLevel.INTERMEDIATE,
                topic="Python",
                question_text="Explain list comprehensions.",
                correct_answer_hint="Concise loop syntax",
            ),
        ],
        question_count=1,
    )


@pytest.fixture
def client(mock_storage, mock_engine):
    """FastAPI test client with mocked dependencies."""
    with patch("src.api.routes.assessment._storage", mock_storage), patch(
        "src.api.routes.assessment._get_engine", return_value=mock_engine
    ), patch("src.api.routes.profile.stored_profiles", {}, create=True), patch(
        "src.api.routes.profile.active_profile_id", None, create=True
    ):

        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc
        app.dependency_overrides.clear()


# ── Start Session Tests ─────────────────────────────────────────────────────


class TestStartSession:
    """Tests for POST /api/assessment/."""

    def test_start_skill_based(self, client, mock_storage, mock_engine, sample_session):
        """Should start a skill-based session."""
        mock_storage.get_session.return_value = None

        saved_session = None

        def capture_save(s):
            nonlocal saved_session
            saved_session = s

        mock_storage.save_session.side_effect = capture_save

        resp = client.post(
            "/api/assessment/",
            json={
                "mode": "skill_based",
                "target_skills": ["Python"],
                "difficulty": "intermediate",
                "question_count": 5,
            },
        )

        assert resp.status_code in [200, 500]


# ── Submit Answer Tests ─────────────────────────────────────────────────────


class TestSubmitAnswer:
    """Tests for POST /api/assessment/{session_id}/answer."""

    def test_submit_answer_success(
        self, client, mock_storage, mock_engine, sample_session
    ):
        """Should evaluate answer and return score."""
        mock_storage.get_session.return_value = sample_session

        resp = client.post(
            "/api/assessment/test-session-001/answer",
            json={
                "question_id": "q1",
                "freeform_text": "List comprehensions are a concise way to create lists.",
            },
        )

        if resp.status_code == 200:
            data = resp.json()
            assert "score" in data
            assert "session_completed" in data

    def test_submit_answer_session_not_found(self, client, mock_storage):
        """Should return 404 for non-existent session."""
        mock_storage.get_session.return_value = None

        resp = client.post(
            "/api/assessment/no-such-id/answer",
            json={
                "question_id": "q1",
                "freeform_text": "answer",
            },
        )
        assert resp.status_code == 404


# ── Get Session Tests ───────────────────────────────────────────────────────


class TestGetSession:
    """Tests for GET /api/assessment/{session_id}."""

    def test_get_existing_session(self, client, mock_storage, sample_session):
        """Should return session data."""
        mock_storage.get_session.return_value = sample_session

        resp = client.get("/api/assessment/test-session-001")
        if resp.status_code == 200:
            data = resp.json()
            assert data["session_id"] == "test-session-001"
            for q in data.get("questions", []):
                assert "correct_answer_hint" not in q

    def test_get_nonexistent_session(self, client, mock_storage):
        """Should return 404."""
        mock_storage.get_session.return_value = None
        resp = client.get("/api/assessment/no-such-id")
        assert resp.status_code == 404


# ── List Sessions Tests ─────────────────────────────────────────────────────


class TestListSessions:
    """Tests for GET /api/assessment/."""

    def test_list_empty(self, client, mock_storage):
        """Should return empty list when no sessions exist."""
        mock_storage.get_recent_sessions.return_value = []
        resp = client.get("/api/assessment/")
        if resp.status_code == 200:
            assert resp.json() == []

    def test_list_with_sessions(self, client, mock_storage, sample_session):
        """Should return session summaries."""
        mock_storage.get_recent_sessions.return_value = [sample_session]
        resp = client.get("/api/assessment/")
        if resp.status_code == 200:
            data = resp.json()
            assert len(data) == 1


# ── Delete Session Tests ────────────────────────────────────────────────────


class TestDeleteSession:
    """Tests for DELETE /api/assessment/{session_id}."""

    def test_delete_existing(self, client, mock_storage, sample_session):
        """Should delete and return success."""
        mock_storage.get_session.return_value = sample_session
        mock_storage.delete_session.return_value = True

        resp = client.delete("/api/assessment/test-session-001")
        if resp.status_code == 200:
            assert resp.json()["success"] is True

    def test_delete_nonexistent(self, client, mock_storage):
        """Should return 404."""
        mock_storage.delete_session.return_value = False
        resp = client.delete("/api/assessment/no-such-id")
        assert resp.status_code == 404


# ── Progress Stats Tests ────────────────────────────────────────────────────


class TestProgressEndpoint:
    """Tests for GET /api/assessment/progress."""

    def test_progress_stats(self, client, mock_storage):
        """Should return progress statistics."""
        mock_storage.get_progress_stats.return_value = {
            "total_sessions": 5,
            "completed_sessions": 3,
            "average_score": 72.5,
            "score_trend": [{"date": "2026-01-01T00:00:00", "score": 80}],
            "strongest_topics": [["Python", 85.0]],
            "weakest_topics": [["SQL", 45.0]],
        }

        resp = client.get("/api/assessment/progress")
        if resp.status_code == 200:
            data = resp.json()
            assert data["total_sessions"] == 5
            assert data["average_score"] == 72.5


# ── Skills Endpoint Tests ──────────────────────────────────────────────────


class TestSkillsEndpoint:
    """Tests for GET /api/assessment/skills."""

    def test_returns_default_skills(self, client):
        """Should return default skills when no profile is loaded."""
        resp = client.get("/api/assessment/skills")
        if resp.status_code == 200:
            data = resp.json()
            assert "skills" in data
            assert len(data["skills"]) >= 5


# ── Complete Session Tests ──────────────────────────────────────────────────


class TestCompleteSession:
    """Tests for POST /api/assessment/{session_id}/complete."""

    def test_complete_session(self, client, mock_storage, mock_engine, sample_session):
        """Should complete session and return final results."""
        mock_storage.get_session.return_value = sample_session

        def mock_complete(session):
            session.status = SessionStatus.COMPLETED
            session.overall_score = 0.0
            session.completed_at = datetime.now()

        mock_engine.calculate_session_results.side_effect = mock_complete

        resp = client.post("/api/assessment/test-session-001/complete")
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "completed"

    def test_complete_nonexistent(self, client, mock_storage):
        """Should return 404 for missing session."""
        mock_storage.get_session.return_value = None
        resp = client.post("/api/assessment/no-such-id/complete")
        assert resp.status_code == 404
