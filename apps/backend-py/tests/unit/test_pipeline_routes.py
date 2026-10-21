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
        """Discover may send MCF, JobStreet, and Careers@Gov ids."""
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


class TestPipelineOptions:
    """Tests for fresh-grad, submission pacing, and stop-stage options."""

    def _start(self, client, **extra):
        """POST a start request and return the stored run record."""
        from src.api.routes.pipeline import pipeline_runs

        resp = client.post(
            "/api/pipeline/start",
            json={"keywords": ["python"], "locations": ["Singapore"], **extra},
        )
        assert resp.status_code == 200, resp.text
        return pipeline_runs[resp.json()["run_id"]]

    def test_options_reach_pipeline_config(self, client):
        """Fresh-grad and pacing values are passed to PipelineConfig."""
        run = self._start(
            client,
            mode="full",
            fresh_grad_mode=True,
            submission_delay=5,
            max_submissions_per_hour=10,
        )

        config = run["config"]
        assert config.fresh_grad_mode is True
        assert config.submission_delay == 5
        assert config.max_submissions_per_hour == 10

    def test_defaults_keep_standard_scoring(self, client):
        """Without options, scoring stays standard and pacing uses defaults."""
        config = self._start(client)["config"]

        assert config.fresh_grad_mode is False
        assert config.submission_delay == 2.0
        assert config.max_submissions_per_hour == 30

    def test_discover_defaults_to_rag_rank(self, client):
        """Discover mode without stop_at stops after rag_rank."""
        assert self._start(client, mode="discover")["stop_at"] == "rag_rank"

    def test_explicit_stop_at_is_stored(self, client):
        """A chosen stop stage is honoured."""
        run = self._start(client, mode="discover", stop_at="score_and_rank")
        assert run["stop_at"] == "score_and_rank"

    def test_full_mode_without_stop_runs_all_stages(self, client):
        """Full mode without stop_at runs to the end."""
        assert self._start(client, mode="full")["stop_at"] is None

    @pytest.mark.parametrize(
        "extra",
        [
            {"mode": "discover", "stop_at": "generate_resumes"},
            {"stop_at": "not_a_stage"},
            {"submission_delay": 0.1},
            {"max_submissions_per_hour": 0},
        ],
    )
    def test_invalid_options_return_422(self, client, extra):
        """Out-of-range pacing and invalid stop stages fail validation."""
        resp = client.post(
            "/api/pipeline/start",
            json={"keywords": ["python"], "locations": ["Singapore"], **extra},
        )
        assert resp.status_code == 422


def test_resolve_stop_at():
    """Stop-stage resolution follows mode defaults and explicit choices."""
    from src.api.routes.pipeline import resolve_stop_at
    from src.pipeline.orchestrator import PipelineStage

    assert resolve_stop_at("discover", None) == PipelineStage.RAG_RANK
    assert resolve_stop_at("full", None) is None
    assert resolve_stop_at("full", "generate_resumes") == (
        PipelineStage.GENERATE_RESUMES
    )


def test_stage_order_matches_orchestrator():
    """The request model stage list mirrors the orchestrator enum."""
    from src.api.models.requests import PIPELINE_STAGE_ORDER
    from src.pipeline.orchestrator import PipelineStage

    assert list(PIPELINE_STAGE_ORDER) == [s.value for s in PipelineStage]


class TestRunEndpoints:
    """GET /status and GET /results for a finished run."""

    def _store_completed_run(self) -> str:
        """Store a completed run with a real PipelineResult.

        Returns:
            The run ID.
        """
        from src.api.routes.pipeline import pipeline_runs
        from src.pipeline.orchestrator import PipelineResult
        from src.pipeline.stages import StageResult

        now = datetime.now()
        result = PipelineResult(
            success=True,
            stages_completed=["scrape", "deduplicate"],
            stage_results={
                name: StageResult(
                    stage_name=name,
                    success=True,
                    data=[],
                    metadata={"count": 1},
                    timestamp=now,
                )
                for name in ["scrape", "deduplicate"]
            },
            start_time=now,
            end_time=now,
        )
        pipeline_runs["run_done"] = {
            "run_id": "run_done",
            "status": "completed",
            "created_at": now,
            "result": result,
            "stages_planned": ["scrape", "deduplicate"],
            "stages_completed": ["scrape", "deduplicate"],
            "current_stage": "deduplicate",
            "stage_progress": 100,
        }
        return "run_done"

    def test_results_returns_stage_names_as_strings(self, client):
        """GET /results works for a completed run (it used to raise)."""
        run_id = self._store_completed_run()

        resp = client.get(f"/api/pipeline/results/{run_id}")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["stages_completed"] == ["scrape", "deduplicate"]
        assert data["stage_results"]["scrape"] == {
            "success": True,
            "metadata": {"count": 1},
        }

    def test_status_reports_planned_and_completed_stages(self, client):
        """GET /status exposes the stage plan and progress for polling."""
        run_id = self._store_completed_run()

        data = client.get(f"/api/pipeline/status/{run_id}").json()

        assert data["stages_planned"] == ["scrape", "deduplicate"]
        assert data["stages_completed"] == ["scrape", "deduplicate"]
        assert data["current_stage"] == "deduplicate"
        assert data["stage_progress"] == 100

    def _store_run_with_generate_stage(self, cloud_documents: int) -> str:
        """Store a completed run whose generate stage reports cloud documents.

        The stage key comes from ``PipelineStage``, the same value the
        orchestrator uses for ``PipelineResult.stage_results``.

        Args:
            cloud_documents: Value for the generate stage ``cloud_documents``.

        Returns:
            The run ID.
        """
        from src.api.routes.pipeline import pipeline_runs
        from src.models.pipeline_stage import PipelineStage
        from src.pipeline.orchestrator import PipelineResult
        from src.pipeline.stages import StageResult

        now = datetime.now()
        generate = PipelineStage.GENERATE_RESUMES.value
        result = PipelineResult(
            success=True,
            stages_completed=[generate],
            stage_results={
                generate: StageResult(
                    stage_name=generate,
                    success=True,
                    data=[],
                    metadata={"generated_count": 2, "cloud_documents": cloud_documents},
                    timestamp=now,
                )
            },
            start_time=now,
            end_time=now,
        )
        pipeline_runs["run_generate"] = {
            "run_id": "run_generate",
            "status": "completed",
            "created_at": now,
            "result": result,
            "stages_planned": [generate],
            "stages_completed": [generate],
            "current_stage": generate,
            "stage_progress": 100,
        }
        return "run_generate"

    def test_status_reports_cloud_documents_from_generate_stage(self, client):
        """GET /status copies ``cloud_documents`` from the generate stage."""
        run_id = self._store_run_with_generate_stage(cloud_documents=2)

        data = client.get(f"/api/pipeline/status/{run_id}").json()

        assert data["cloud_documents"] == 2

    def test_status_reports_zero_cloud_documents_without_generate_stage(self, client):
        """A run that did not reach the generate stage reports 0."""
        run_id = self._store_completed_run()

        data = client.get(f"/api/pipeline/status/{run_id}").json()

        assert data["cloud_documents"] == 0
