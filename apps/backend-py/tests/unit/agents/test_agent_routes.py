"""
Unit tests for the agent API routes.

Covers task submission endpoints and the asynchronous task-result retrieval
endpoint ``GET /api/agents/tasks/{task_id}``.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import agents as agents_module


@pytest.fixture
def mock_coordinator(monkeypatch):
    """Fixture providing a mocked agent coordinator for the route tests.

    The singleton manager used by the agents router is patched so that every
    request resolves to this mock coordinator without starting the real agent
    system.
    """
    coordinator = MagicMock()
    coordinator.submit_task = AsyncMock(return_value="task-abc")

    manager = MagicMock()
    manager.get_coordinator.return_value = coordinator
    manager._initialized = True
    manager._coordinator = coordinator
    manager._background_task = None

    monkeypatch.setattr(agents_module, "_agent_manager", manager)
    return coordinator


@pytest.fixture
def client(mock_coordinator, monkeypatch):
    """FastAPI TestClient with lifespan startup handlers disabled.

    This avoids making network calls to validate LLM providers or initialise
    the real agent system during focused route tests.
    """
    monkeypatch.setattr("src.api.main.validate_llm_providers", lambda: None)
    monkeypatch.setattr(
        "src.api.routes.agents.initialize_agent_system", lambda _router: None
    )
    return TestClient(app, raise_server_exceptions=False)


class TestGetTaskResult:
    """Tests for ``GET /api/agents/tasks/{task_id}``."""

    def test_get_pending_task_returns_202(self, client, mock_coordinator):
        """A pending task should return HTTP 202 with the record."""
        mock_coordinator.get_task_result.return_value = {
            "task_id": "task-1",
            "status": "pending",
            "agent": "career_coach",
            "task_type": "career_path_analysis",
            "result": None,
            "error": None,
        }

        response = client.get("/api/agents/tasks/task-1")

        assert response.status_code == 202
        assert response.json()["success"] is True
        assert response.json()["data"]["status"] == "pending"
        mock_coordinator.get_task_result.assert_called_once_with("task-1")

    def test_get_completed_task_returns_200(self, client, mock_coordinator):
        """A completed task should return HTTP 200 with the result payload."""
        mock_coordinator.get_task_result.return_value = {
            "task_id": "task-2",
            "status": "completed",
            "agent": "career_coach",
            "task_type": "gap_analysis",
            "result": {"gaps": ["kubernetes", "system design"]},
            "error": None,
        }

        response = client.get("/api/agents/tasks/task-2")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "completed"
        assert body["data"]["result"]["gaps"] == ["kubernetes", "system design"]

    def test_get_failed_task_returns_200(self, client, mock_coordinator):
        """A failed task should return HTTP 200 with the error details."""
        mock_coordinator.get_task_result.return_value = {
            "task_id": "task-3",
            "status": "failed",
            "agent": "career_coach",
            "task_type": "upskilling_roadmap",
            "result": None,
            "error": "LLM router unavailable",
        }

        response = client.get("/api/agents/tasks/task-3")

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "failed"
        assert body["data"]["error"] == "LLM router unavailable"

    def test_get_unknown_task_returns_404(self, client, mock_coordinator):
        """An unknown or expired task ID should return HTTP 404."""
        mock_coordinator.get_task_result.return_value = None

        response = client.get("/api/agents/tasks/missing-task")

        assert response.status_code == 404
        assert response.json()["message"] == "Task not found"

    def test_get_blank_task_id_returns_400(self, client, mock_coordinator):
        """A blank task ID should be rejected with HTTP 400."""
        response = client.get("/api/agents/tasks/%20")

        assert response.status_code == 400
        assert response.json()["message"] == "Task ID is required"


class TestTaskSubmission:
    """Tests for agent task submission endpoints."""

    def test_career_analysis_submits_task(self, client, mock_coordinator):
        """POST /career-analysis should return a task ID for valid input."""
        payload = {
            "profile": {"name": "Test User", "skills": ["python"]},
            "target_jobs": [],
        }

        response = client.post("/api/agents/career-analysis", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["task_id"] == "task-abc"
        assert body["data"]["task_type"] == "career_path_analysis"
        mock_coordinator.submit_task.assert_called_once()

    def test_gap_analysis_submits_task(self, client, mock_coordinator):
        """POST /gap-analysis should return a task ID for valid input."""
        payload = {
            "profile": {"name": "Test User"},
            "target_jobs": [{"title": "Backend Engineer"}],
        }

        response = client.post("/api/agents/gap-analysis", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["task_id"] == "task-abc"
        assert body["data"]["task_type"] == "gap_analysis"

    def test_upskilling_roadmap_submits_task(self, client, mock_coordinator):
        """POST /upskilling-roadmap should return a task ID for valid input."""
        payload = {
            "gap_analysis": {
                "skills_gap": ["kubernetes"],
                "profile": {"name": "Test User"},
            }
        }

        response = client.post("/api/agents/upskilling-roadmap", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["task_id"] == "task-abc"
        assert body["data"]["task_type"] == "upskilling_roadmap"

    def test_career_goals_submits_task(self, client, mock_coordinator):
        """POST /career-goals should return a task ID for valid input."""
        payload = {"profile": {"name": "Test User", "goals": ["become staff engineer"]}}

        response = client.post("/api/agents/career-goals", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["data"]["task_id"] == "task-abc"
        assert body["data"]["task_type"] == "career_goal_setting"

    def test_submission_without_profile_fails_validation(self, client):
        """Validation should reject an empty profile."""
        response = client.post("/api/agents/career-analysis", json={"profile": {}})

        assert response.status_code == 422
        assert response.json()["error"] == "Validation failed"

    def test_gap_analysis_requires_target_jobs(self, client):
        """Gap analysis should require at least one target job."""
        response = client.post(
            "/api/agents/gap-analysis",
            json={"profile": {"name": "Test User"}, "target_jobs": []},
        )

        assert response.status_code == 422
        assert response.json()["error"] == "Validation failed"

    def test_upskilling_roadmap_requires_skills_gap(self, client):
        """Upskilling roadmap should require a skills_gap field."""
        response = client.post(
            "/api/agents/upskilling-roadmap",
            json={"gap_analysis": {"missing": "skills_gap"}},
        )

        assert response.status_code == 422
        assert response.json()["error"] == "Validation failed"

    def test_coordinator_unavailable_returns_503(self, client, mock_coordinator):
        """When the coordinator cannot accept a task, the route should return 503."""
        mock_coordinator.submit_task.return_value = ""

        response = client.post(
            "/api/agents/career-analysis",
            json={"profile": {"name": "Test User"}},
        )

        assert response.status_code == 503
        body = response.json()
        assert body["error"] == "HTTP error"
        assert "try again later" in body["message"].lower()
