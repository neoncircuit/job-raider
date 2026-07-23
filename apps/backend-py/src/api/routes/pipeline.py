"""
Job Raider - Pipeline Control API Routes

API endpoints for managing pipeline execution and monitoring.

Author: Job Raider
Date: 2026-04-21
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ...models.user_profile import UserProfile
from ...pipeline.orchestrator import PipelineConfig, PipelineOrchestrator
from ...utils.logger import Components, get_logger
from ..models.requests import PipelineStartRequest
from ..models.responses import (
    PipelineStatusResponse,
)
from ..websocket.progress import manager
from . import profile as profile_state

router = APIRouter()
logger = get_logger(Components.SCRAPERS)

# Store pipeline runs in memory (use Redis in production)
pipeline_runs: Dict[str, Dict[str, Any]] = {}


async def run_pipeline_async(
    run_id: str,
    config: PipelineConfig,
    profile: UserProfile,
):
    """
    Run pipeline in background with WebSocket updates.

    Args:
        run_id: Unique pipeline run identifier
        config: Pipeline configuration
        profile: User profile
    """
    try:
        # Update status
        pipeline_runs[run_id]["status"] = "running"
        pipeline_runs[run_id]["started_at"] = datetime.now()

        # Notify started
        await manager.send_message(
            run_id,
            {
                "type": "pipeline_started",
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Create orchestrator with progress callback
        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=profile,
        )

        # Run pipeline
        result = orchestrator.run()

        # Preserve an explicit user cancel; soft-cancel cannot stop the
        # orchestrator mid-flight, but the final status must stay cancelled.
        if pipeline_runs[run_id].get("status") == "cancelled":
            pipeline_runs[run_id]["result"] = result
            pipeline_runs[run_id]["completed_at"] = datetime.now()
            logger.info(f"Pipeline {run_id} finished after cancel request")
            return

        pipeline_runs[run_id]["status"] = "completed"
        pipeline_runs[run_id]["result"] = result
        pipeline_runs[run_id]["completed_at"] = datetime.now()

        # Notify completion
        await manager.broadcast_pipeline_complete(
            run_id,
            {
                "success": result.success,
                "duration_seconds": result.duration_seconds,
                "jobs_scraped": result.jobs_scraped,
                "jobs_applied": result.jobs_applied,
                "stages_completed": len(result.stages_completed),
            },
        )

        logger.info(f"Pipeline {run_id} completed successfully")

    except Exception as e:
        logger.error(f"Pipeline {run_id} failed: {e}", exc_info=True)

        if pipeline_runs[run_id].get("status") == "cancelled":
            pipeline_runs[run_id]["error"] = str(e)
            pipeline_runs[run_id]["completed_at"] = datetime.now()
            return

        # Update status
        pipeline_runs[run_id]["status"] = "failed"
        pipeline_runs[run_id]["error"] = str(e)
        pipeline_runs[run_id]["completed_at"] = datetime.now()

        # Notify failure
        await manager.broadcast_pipeline_failed(run_id, str(e))


@router.post("/start", response_model=Dict[str, str])
async def start_pipeline(
    request: PipelineStartRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a new pipeline run.

    Creates a new pipeline run with the given configuration and executes
    it in the background. Returns the run ID immediately for monitoring.

    Args:
        request: Pipeline start request with search parameters
        background_tasks: FastAPI background tasks

    Returns:
        Dict with run_id for monitoring progress
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    # Create pipeline config
    config = PipelineConfig(
        keywords=request.keywords,
        locations=request.locations,
        sources=request.sources,
        dry_run=request.dry_run,
        skip_submission=request.skip_submission,
        min_score=request.min_score,
        scam_threshold=request.scam_threshold,
        max_jobs_to_present=request.max_jobs,
    )

    # Initialize run state early so status endpoints work even if profile
    # resolution fails.
    pipeline_runs[run_id] = {
        "run_id": run_id,
        "status": "pending",
        "config": config,
        "created_at": datetime.now(),
    }

    # Create or load profile
    if request.profile_data:
        try:
            profile = UserProfile(**request.profile_data)
        except Exception as e:
            logger.warning(f"Invalid profile_data for run {run_id}: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid profile data: {e}",
            ) from e
    elif (
        profile_state.active_profile_id
        and profile_state.active_profile_id in profile_state.stored_profiles
    ):
        entry = profile_state.stored_profiles[profile_state.active_profile_id]
        maybe_profile = entry.get("profile")
        if not isinstance(maybe_profile, UserProfile):
            pipeline_runs[run_id]["status"] = "failed"
            raise HTTPException(
                status_code=400,
                detail="Active profile is not loaded correctly. Re-upload your resume.",
            )
        profile = maybe_profile
    else:
        pipeline_runs[run_id]["status"] = "failed"
        raise HTTPException(
            status_code=400,
            detail="No profile found. Upload a resume first via /api/profile/upload",
        )

    # Start pipeline in background
    background_tasks.add_task(run_pipeline_async, run_id, config, profile)

    logger.info(f"Started pipeline {run_id}")

    return {"run_id": run_id}


@router.get("/status/{run_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(run_id: str):
    """
    Get current status of a pipeline run.

    Args:
        run_id: Pipeline run ID

    Returns:
        Current pipeline status
    """
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    run = pipeline_runs[run_id]

    return PipelineStatusResponse(
        run_id=run_id,
        status=run["status"],
        current_stage=run.get("current_stage"),
        stage_progress=run.get("stage_progress", 0),
        jobs_scraped=run.get("jobs_scraped", 0),
        jobs_scored=run.get("jobs_scored", 0),
        jobs_selected=run.get("jobs_selected", 0),
        applications_submitted=run.get("applications_submitted", 0),
        started_at=run.get("started_at"),
        error_message=run.get("error"),
    )


@router.get("/results/{run_id}")
async def get_pipeline_results(run_id: str):
    """
    Get results of a completed pipeline run.

    Args:
        run_id: Pipeline run ID

    Returns:
        Pipeline results with job listings and generated resumes
    """
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    run = pipeline_runs[run_id]

    if run["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Pipeline not completed. Current status: {run['status']}",
        )

    result = run.get("result")
    if not result:
        raise HTTPException(status_code=404, detail="Results not available")

    return {
        "run_id": run_id,
        "status": run["status"],
        "success": result.success,
        "duration_seconds": result.duration_seconds,
        "stages_completed": [s.value for s in result.stages_completed],
        "jobs_scraped": result.jobs_scraped,
        "jobs_applied": result.jobs_applied,
        "stage_results": {
            stage.value: {
                "success": stage_result.success,
                "metadata": stage_result.metadata,
            }
            for stage, stage_result in result.stage_results.items()
        },
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
    }


@router.delete("/{run_id}")
async def cancel_pipeline(run_id: str):
    """
    Cancel a running pipeline.

    Args:
        run_id: Pipeline run ID

    Returns:
        Cancellation confirmation
    """
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    run = pipeline_runs[run_id]

    if run["status"] not in ["pending", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel pipeline in status: {run['status']}",
        )

    # TODO: Implement actual cancellation logic
    # This would require orchestrator to support cancellation
    run["status"] = "cancelled"

    await manager.broadcast_pipeline_failed(
        run_id,
        "Pipeline cancelled by user",
    )

    logger.info(f"Cancelled pipeline {run_id}")

    return {"run_id": run_id, "status": "cancelled"}


@router.get("/history")
async def get_pipeline_history(
    limit: int = 20,
    status: Optional[str] = None,
):
    """
    Get history of pipeline runs.

    Args:
        limit: Maximum number of runs to return
        status: Filter by status (optional)

    Returns:
        List of pipeline runs
    """
    runs = list(pipeline_runs.values())

    if status:
        runs = [r for r in runs if r["status"] == status]

    # Sort by created_at descending
    runs = sorted(runs, key=lambda r: r["created_at"], reverse=True)

    # Limit results
    runs = runs[:limit]

    return {
        "runs": [
            {
                "run_id": r["run_id"],
                "status": r["status"],
                "created_at": r["created_at"],
                "started_at": r.get("started_at"),
                "completed_at": r.get("completed_at"),
            }
            for r in runs
        ],
        "total": len(runs),
    }
