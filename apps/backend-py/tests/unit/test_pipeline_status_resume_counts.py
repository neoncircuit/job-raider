"""Tests for the resume counts of GET /api/pipeline/status (monitor resume count, MH-1)."""

from datetime import datetime
from typing import Dict, Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.auth import verify_api_key
from src.api.main import app
from src.api.routes.pipeline import pipeline_runs
from src.models.pipeline_stage import PipelineStage
from src.pipeline.orchestrator import PipelineResult
from src.pipeline.stages import StageResult


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Build a test client without the API key check.

    Yields:
        A FastAPI test client.
    """
    app.dependency_overrides[verify_api_key] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def store_run(run_id: str, metadata: Dict[str, Dict[str, int]]) -> None:
    """Store a completed run whose stages report the given metadata.

    Args:
        run_id: The run ID.
        metadata: The stage value and the metadata of each stage.
    """
    now = datetime.now()
    result = PipelineResult(
        success=True,
        stages_completed=list(metadata),
        stage_results={
            stage: StageResult(
                stage_name=stage, success=True, data=[], metadata=meta, timestamp=now
            )
            for stage, meta in metadata.items()
        },
        start_time=now,
        end_time=now,
    )
    pipeline_runs[run_id] = {
        "run_id": run_id,
        "status": "completed",
        "created_at": now,
        "result": result,
        "jobs_selected": 20,
        "stage_progress": 100,
    }


def test_status_reports_the_jobs_and_resumes_of_a_full_run(client: TestClient) -> None:
    """The status has the Select Jobs count and the generated resume count."""
    store_run(
        "run_resume_counts",
        {
            PipelineStage.PRESENT_SELECT.value: {
                "presented_count": 2,
                "selected_count": 2,
            },
            PipelineStage.GENERATE_RESUMES.value: {
                "attempted_count": 2,
                "generated_count": 1,
            },
        },
    )

    data = client.get("/api/pipeline/status/run_resume_counts").json()
    pipeline_runs.pop("run_resume_counts")

    assert data["jobs_selected"] == 20
    assert data["jobs_for_resumes"] == 2
    assert data["resumes_generated"] == 1


def test_status_reports_zero_for_a_discover_run(client: TestClient) -> None:
    """A run without the Select Jobs and Generate Resumes stages reports 0."""
    store_run(
        "run_discover_counts", {PipelineStage.SCRAPE.value: {"listings_count": 5}}
    )

    data = client.get("/api/pipeline/status/run_discover_counts").json()
    pipeline_runs.pop("run_discover_counts")

    assert data["jobs_for_resumes"] == 0
    assert data["resumes_generated"] == 0
