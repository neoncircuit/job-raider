# Unit tests for assessment storage
# Author: Job Raider
# Date: 2026-05-22

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.assessment.storage import AssessmentStorage
from src.models.assessment import (
    AnswerFormat,
    AssessmentMode,
    AssessmentSession,
    DifficultyLevel,
    Question,
    QuestionScore,
    QuestionType,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def storage(tmp_path):
    """AssessmentStorage using a temporary directory."""
    return AssessmentStorage(base_dir=str(tmp_path / "data"))


def _make_session(
    session_id: str = "test-001",
    mode: AssessmentMode = AssessmentMode.SKILL_BASED,
    overall_score: float = None,
    topic_breakdown: dict = None,
    completed_at: datetime = None,
) -> AssessmentSession:
    """Helper to create a test session."""
    session = AssessmentSession(
        session_id=session_id,
        mode=mode,
        difficulty=DifficultyLevel.INTERMEDIATE,
        current_difficulty=DifficultyLevel.INTERMEDIATE,
        target_skills=["Python"],
        question_count=3,
    )
    if overall_score is not None:
        session.overall_score = overall_score
    if topic_breakdown is not None:
        session.topic_breakdown = topic_breakdown
    if completed_at is not None:
        session.completed_at = completed_at
        session.status = "completed"
    return session


# ── Save / Get Tests ─────────────────────────────────────────────────────────


class TestSaveAndGet:
    """Tests for saving and retrieving sessions."""

    def test_save_and_retrieve(self, storage, tmp_path):
        """Saved session should be retrievable by ID."""
        session = _make_session("s1")
        storage.save_session(session)

        retrieved = storage.get_session("s1")
        assert retrieved is not None
        assert retrieved.session_id == "s1"
        assert retrieved.mode == AssessmentMode.SKILL_BASED

    def test_persists_to_disk(self, storage, tmp_path):
        """Save should write a JSON file to disk."""
        session = _make_session("s2")
        storage.save_session(session)

        file_path = tmp_path / "data" / "assessments" / "s2.json"
        assert file_path.exists()
        data = json.loads(file_path.read_text())
        assert data["session_id"] == "s2"

    def test_get_nonexistent_returns_none(self, storage):
        """Getting a non-existent session should return None."""
        assert storage.get_session("no-such-id") is None

    def test_overwrite_existing(self, storage):
        """Saving a session with the same ID should overwrite."""
        session = _make_session("s3", overall_score=50.0)
        storage.save_session(session)

        updated = _make_session("s3", overall_score=90.0)
        storage.save_session(updated)

        retrieved = storage.get_session("s3")
        assert retrieved.overall_score == 90.0


# ── List Tests ───────────────────────────────────────────────────────────────


class TestListSessions:
    """Tests for listing sessions."""

    def test_get_all_sessions(self, storage):
        """Should return all sessions sorted by creation date."""
        for i in range(3):
            storage.save_session(_make_session(f"s{i}"))

        all_sessions = storage.get_all_sessions()
        assert len(all_sessions) == 3

    def test_get_recent_sessions_limits(self, storage):
        """Should respect the limit parameter."""
        for i in range(10):
            storage.save_session(_make_session(f"s{i}"))

        recent = storage.get_recent_sessions(limit=5)
        assert len(recent) == 5

    def test_sorted_newest_first(self, storage):
        """Sessions should be sorted newest first."""
        storage.save_session(_make_session("old"))
        storage.save_session(_make_session("new"))

        all_sessions = storage.get_all_sessions()
        assert len(all_sessions) == 2
        ids = {s.session_id for s in all_sessions}
        assert "old" in ids
        assert "new" in ids


# ── Delete Tests ─────────────────────────────────────────────────────────────


class TestDeleteSession:
    """Tests for session deletion."""

    def test_delete_existing(self, storage, tmp_path):
        """Should remove session from cache and disk."""
        storage.save_session(_make_session("del-me"))
        assert storage.get_session("del-me") is not None

        result = storage.delete_session("del-me")
        assert result is True
        assert storage.get_session("del-me") is None

        file_path = tmp_path / "data" / "assessments" / "del-me.json"
        assert not file_path.exists()

    def test_delete_nonexistent(self, storage):
        """Deleting a non-existent session should return False."""
        result = storage.delete_session("no-such")
        assert result is False


# ── Progress Stats Tests ────────────────────────────────────────────────────


class TestProgressStats:
    """Tests for aggregate progress statistics."""

    def test_empty_storage(self, storage):
        """Should return zeroed stats when no sessions exist."""
        stats = storage.get_progress_stats()
        assert stats["total_sessions"] == 0
        assert stats["completed_sessions"] == 0
        assert stats["average_score"] == 0.0

    def test_with_completed_sessions(self, storage):
        """Should compute average score from completed sessions."""
        storage.save_session(
            _make_session(
                "s1",
                overall_score=80.0,
                completed_at=datetime(2026, 1, 1),
                topic_breakdown={"Python": 80.0},
            )
        )
        storage.save_session(
            _make_session(
                "s2",
                overall_score=60.0,
                completed_at=datetime(2026, 1, 2),
                topic_breakdown={"SQL": 60.0},
            )
        )

        stats = storage.get_progress_stats()
        assert stats["total_sessions"] == 2
        assert stats["completed_sessions"] == 2
        assert stats["average_score"] == 70.0

    def test_ignores_incomplete_sessions(self, storage):
        """Sessions without overall_score should not affect averages."""
        storage.save_session(_make_session("incomplete"))
        storage.save_session(
            _make_session(
                "complete",
                overall_score=90.0,
                completed_at=datetime(2026, 1, 1),
            )
        )

        stats = storage.get_progress_stats()
        assert stats["completed_sessions"] == 1
        assert stats["average_score"] == 90.0

    def test_topic_breakdown(self, storage):
        """Should aggregate topic scores across sessions."""
        storage.save_session(
            _make_session(
                "s1",
                overall_score=75.0,
                completed_at=datetime(2026, 1, 1),
                topic_breakdown={"Python": 80.0, "SQL": 70.0},
            )
        )
        storage.save_session(
            _make_session(
                "s2",
                overall_score=85.0,
                completed_at=datetime(2026, 1, 2),
                topic_breakdown={"Python": 90.0, "Docker": 80.0},
            )
        )

        stats = storage.get_progress_stats()
        strongest = dict(stats["strongest_topics"])
        assert "Python" in strongest
        assert strongest["Python"] == 85.0

    def test_score_trend(self, storage):
        """Should return score trend for recent sessions."""
        for i in range(5):
            storage.save_session(
                _make_session(
                    f"s{i}",
                    overall_score=50.0 + i * 10,
                    completed_at=datetime(2026, 1, i + 1),
                )
            )

        stats = storage.get_progress_stats()
        trend = stats["score_trend"]
        assert len(trend) == 5
        assert trend[0]["score"] == 50.0
        assert trend[-1]["score"] == 90.0


# ── Cache Warm-up Tests ────────────────────────────────────────────────────


class TestCacheWarmUp:
    """Tests for initial cache loading from disk."""

    def test_loads_existing_files(self, tmp_path):
        """Storage should load sessions that exist on disk at startup."""
        dir = tmp_path / "data" / "assessments"
        dir.mkdir(parents=True)

        session_data = _make_session("pre-existing")
        file_path = dir / "pre-existing.json"
        file_path.write_text(
            json.dumps(session_data.model_dump(mode="json"), default=str)
        )

        new_storage = AssessmentStorage(base_dir=str(tmp_path / "data"))
        assert new_storage.get_session("pre-existing") is not None
