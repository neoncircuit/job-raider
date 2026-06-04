"""
Job Raider - Assessment Storage

JSON file-based storage for assessment sessions. Follows the same
pattern as OutcomeTracker -- one JSON file per session in
data/assessments/, with an in-memory cache.

Author: Job Raider
Date: 2026-05-22
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..models.assessment import AssessmentSession
from ..utils.logger import get_logger, Components


class AssessmentStorage:
    """Persistent storage for assessment sessions.

    Each session is stored as a JSON file in data/assessments/.
    An in-memory cache avoids repeated file reads.

    Args:
        base_dir: Root data directory (default: data/).
    """

    def __init__(self, base_dir: str = "data"):
        """Initialize storage and load existing sessions.

        Args:
            base_dir: Root data directory path.
        """
        self.logger = get_logger(Components.GENERATION)
        self._sessions_dir = Path(base_dir) / "assessments"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, AssessmentSession] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load all existing sessions from disk into memory."""
        for path in self._sessions_dir.glob("*.json"):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                session = AssessmentSession(**data)
                self._cache[session.session_id] = session
            except Exception as e:
                self.logger.error("Failed to load session %s: %s", path.name, e)

    def save_session(self, session: AssessmentSession) -> None:
        """Save a session to disk and cache.

        Args:
            session: The session to persist.
        """
        self._cache[session.session_id] = session
        path = self._sessions_dir / f"{session.session_id}.json"
        with open(path, "w") as f:
            json.dump(session.model_dump(mode="json"), f, indent=2, default=str)

    def get_session(self, session_id: str) -> Optional[AssessmentSession]:
        """Retrieve a session by ID.

        Args:
            session_id: The session identifier.

        Returns:
            The session, or None if not found.
        """
        return self._cache.get(session_id)

    def get_all_sessions(self) -> List[AssessmentSession]:
        """Retrieve all stored sessions sorted by creation date (newest first).

        Returns:
            List of all sessions.
        """
        return sorted(
            self._cache.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )

    def get_recent_sessions(self, limit: int = 20) -> List[AssessmentSession]:
        """Retrieve the N most recent sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of recent sessions.
        """
        return self.get_all_sessions()[:limit]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session from disk and cache.

        Args:
            session_id: The session to delete.

        Returns:
            True if the session was found and deleted.
        """
        if session_id not in self._cache:
            return False

        del self._cache[session_id]
        path = self._sessions_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
        return True

    def get_progress_stats(self) -> Dict[str, object]:
        """Compute aggregate progress statistics across all sessions.

        Returns:
            Dict with total_sessions, completed_sessions, average_score,
            score_trend, strongest_topics, and weakest_topics.
        """
        completed = [s for s in self._cache.values() if s.overall_score is not None]

        if not completed:
            return {
                "total_sessions": len(self._cache),
                "completed_sessions": 0,
                "average_score": 0.0,
                "score_trend": [],
                "strongest_topics": [],
                "weakest_topics": [],
            }

        # Average score
        avg_score = round(
            sum(s.overall_score for s in completed) / len(completed), 1
        )

        # Score trend (last 10 completed sessions)
        sorted_completed = sorted(completed, key=lambda s: s.completed_at or datetime.min)
        trend = [
            {
                "date": (s.completed_at or datetime.now()).isoformat(),
                "score": s.overall_score,
            }
            for s in sorted_completed[-10:]
        ]

        # Topic breakdown across all completed sessions
        all_topics: Dict[str, List[float]] = {}
        for s in completed:
            for topic, score in s.topic_breakdown.items():
                all_topics.setdefault(topic, []).append(score)

        topic_avgs = {
            topic: round(sum(scores) / len(scores), 1)
            for topic, scores in all_topics.items()
        }

        sorted_topics = sorted(topic_avgs.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_sessions": len(self._cache),
            "completed_sessions": len(completed),
            "average_score": avg_score,
            "score_trend": trend,
            "strongest_topics": sorted_topics[:5],
            "weakest_topics": sorted_topics[-5:] if len(sorted_topics) > 5 else [],
        }
