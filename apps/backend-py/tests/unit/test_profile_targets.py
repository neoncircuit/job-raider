"""
Unit tests for profile target preference updates.

Covers wiring of target_experience and exclude_internships on PUT /profile.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.models.job_listing import ExperienceLevel
from src.models.user_profile import ContactInfo, TargetJob, UserProfile


@pytest.fixture
def profile_client():
    """Test client with an active in-memory profile."""
    profile = UserProfile(
        name="Test User",
        contact=ContactInfo(email="test@example.com", location="Remote"),
        targets=TargetJob(
            keywords=["python"],
            locations=["Remote"],
            experience_levels=[],
            remote_preference=False,
            constraint_mode="boost",
            exclude_internships=False,
        ),
    )
    stored = {
        "prof_1": {
            "profile": profile,
            "resume_path": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
    }

    with patch("src.api.routes.profile.stored_profiles", stored, create=True), patch(
        "src.api.routes.profile.active_profile_id", "prof_1", create=True
    ), patch("src.api.routes.profile._persist_state", lambda: None):
        from src.api.auth import verify_api_key
        from src.api.main import app

        app.dependency_overrides[verify_api_key] = lambda: None
        tc = TestClient(app, raise_server_exceptions=False)
        yield tc, stored
        app.dependency_overrides.clear()


class TestUpdateProfileTargets:
    """Tests for preference fields on PUT /api/profile."""

    def test_updates_experience_levels_and_exclude_internships(
        self, profile_client
    ) -> None:
        """Should persist target_experience and exclude_internships."""
        client, stored = profile_client
        resp = client.put(
            "/api/profile",
            json={
                "target_keywords": ["AI Engineer", "Machine Learning"],
                "target_locations": ["Singapore", "Remote"],
                "target_experience": ["Entry Level", "Mid Level"],
                "remote_preference": True,
                "constraint_mode": "filter",
                "exclude_internships": True,
            },
        )

        assert resp.status_code == 200
        targets = stored["prof_1"]["profile"].targets
        assert targets.keywords == ["AI Engineer", "Machine Learning"]
        assert targets.locations == ["Singapore", "Remote"]
        assert targets.experience_levels == [
            ExperienceLevel.ENTRY,
            ExperienceLevel.MID,
        ]
        assert targets.remote_preference is True
        assert targets.constraint_mode == "filter"
        assert targets.exclude_internships is True

    def test_ignores_unknown_experience_labels(self, profile_client) -> None:
        """Unknown experience strings are skipped without failing the request."""
        client, stored = profile_client
        resp = client.put(
            "/api/profile",
            json={"target_experience": ["Entry Level", "Wizard Level"]},
        )

        assert resp.status_code == 200
        targets = stored["prof_1"]["profile"].targets
        assert targets.experience_levels == [ExperienceLevel.ENTRY]

    def test_get_profile_includes_exclude_internships(self, profile_client) -> None:
        """GET /profile should serialize exclude_internships."""
        client, stored = profile_client
        stored["prof_1"]["profile"].targets.exclude_internships = True

        resp = client.get("/api/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["target_job"]["exclude_internships"] is True
