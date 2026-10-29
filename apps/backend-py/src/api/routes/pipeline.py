"""
Job Raider - Pipeline Control API Routes

API endpoints for managing pipeline execution and monitoring.

Author: Job Raider
Date: 2026-04-21
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Coroutine, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ...models.user_profile import UserProfile
from ...pipeline.orchestrator import (
    PipelineConfig,
    PipelineOrchestrator,
    PipelineResult,
    PipelineStage,
)
from ...pipeline.shortlist import (
    enrich_shortlist_descriptions,
    enrich_shortlist_payload_descriptions,
    load_latest_shortlist,
    save_latest_shortlist,
)
from ...pipeline.stages import StageResult
from ...submission.applied_guard import AppliedGuard
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


def resolve_stop_at(mode: str, stop_at: Optional[str]) -> Optional[PipelineStage]:
    """
    Resolve the last stage to run for a pipeline request.

    Args:
        mode: ``discover`` or ``full``.
        stop_at: Optional stage name chosen by the user.

    Returns:
        The stage to stop after, or None to run every stage (full mode).
    """
    if stop_at:
        return PipelineStage(stop_at)
    if mode == "discover":
        return PipelineStage.RAG_RANK
    return None


def _attach_stage_events(
    orchestrator: PipelineOrchestrator,
    run_id: str,
    planned: List[PipelineStage],
    loop: asyncio.AbstractEventLoop,
) -> None:
    """
    Publish stage progress for one run while it executes in a worker thread.

    The hooks run in the worker thread. They update the run state that the
    status endpoint returns, and they schedule WebSocket broadcasts on the
    event loop with ``asyncio.run_coroutine_threadsafe``.

    Args:
        orchestrator: Orchestrator that will run the stages.
        run_id: Pipeline run identifier.
        planned: Stages that the run will execute, in order.
        loop: Event loop that owns the WebSocket connections.
    """
    run = pipeline_runs[run_id]
    run["stages_planned"] = [stage.value for stage in planned]
    run["stages_completed"] = []
    total = len(planned)

    def publish(coro: Coroutine[Any, Any, Any]) -> None:
        """
        Schedule a broadcast on the event loop without waiting for it.

        Args:
            coro: Broadcast coroutine.
        """
        asyncio.run_coroutine_threadsafe(coro, loop)

    def before(stage: PipelineStage) -> None:
        """
        Record and announce the stage that is starting.

        Args:
            stage: Stage that is about to run.
        """
        run["current_stage"] = stage.value
        publish(
            manager.broadcast_stage_started(
                run_id,
                stage.value,
                {"index": planned.index(stage) + 1, "total": total},
            )
        )

    def after(stage: PipelineStage, result: StageResult) -> None:
        """
        Record and announce a completed stage and the overall progress.

        Args:
            stage: Stage that finished.
            result: Result of the stage.
        """
        run["stages_completed"].append(stage.value)
        progress = int(len(run["stages_completed"]) * 100 / total) if total else 100
        run["stage_progress"] = progress
        publish(
            manager.broadcast_stage_completed(
                run_id, stage.value, {"success": result.success}
            )
        )
        publish(manager.broadcast_stage_progress(run_id, stage.value, progress))

    for stage in planned:
        orchestrator.register_before_hook(stage, before)
        orchestrator.register_after_hook(stage, after)


def _execute_pipeline(
    run_id: str,
    config: PipelineConfig,
    profile: UserProfile,
    stop_at: Optional[PipelineStage],
    loop: asyncio.AbstractEventLoop,
) -> Tuple[PipelineResult, Any]:
    """
    Run every blocking part of a pipeline run. Call this in a worker thread.

    Building the orchestrator, running the stages, and backfilling shortlist
    descriptions all block (scrapers, LLM calls, network fetches). Running
    them here keeps the event loop free for status polls and WebSockets.

    Args:
        run_id: Pipeline run identifier.
        config: Pipeline configuration.
        profile: User profile.
        stop_at: Last stage to run, or None for every stage.
        loop: Event loop that owns the WebSocket connections.

    Returns:
        Tuple of (pipeline result, shortlisted listings).
    """
    orchestrator = PipelineOrchestrator(config=config, user_profile=profile)
    planned = orchestrator.plan_stages(PipelineStage.SCRAPE, stop_at)
    _attach_stage_events(orchestrator, run_id, planned, loop)

    result = orchestrator.run(
        run_id=run_id,
        stop_at=stop_at,
        should_stop=lambda: pipeline_runs[run_id].get("status") == "cancelled",
    )

    # Prefer RAG-ranked shortlist when present; else heuristic scores.
    shortlist_src = (
        orchestrator.context.rag_ranked_listings or orchestrator.context.scored_listings
    )
    try:
        filled = enrich_shortlist_descriptions(shortlist_src)
        if filled:
            logger.info(
                "Backfilled descriptions for %d shortlisted job(s)",
                filled,
            )
        save_latest_shortlist(
            run_id=run_id,
            mode=getattr(config, "mode", "discover"),
            keywords=list(config.keywords),
            locations=list(config.locations),
            scored_listings=shortlist_src,
            results_dir=config.results_dir,
            jobs_scraped=result.jobs_scraped,
        )
    except Exception as shortlist_err:
        logger.warning(
            "Failed to persist discover shortlist for %s: %s",
            run_id,
            shortlist_err,
        )

    return result, shortlist_src


def _failure_message(result: PipelineResult) -> Tuple[str, Optional[str]]:
    """
    Describe why a pipeline run did not succeed.

    Args:
        result: Result of a run with ``success=False``.

    Returns:
        Tuple of (message, failing stage or None).
    """
    for stage_name, stage_result in result.stage_results.items():
        if not stage_result.success:
            detail = stage_result.error_message or "no error message"
            return f"Stage '{stage_name}' failed: {detail}", stage_name
    return "The pipeline did not complete every planned stage.", None


async def run_pipeline_async(
    run_id: str,
    config: PipelineConfig,
    profile: UserProfile,
    stop_at: Optional[PipelineStage] = None,
):
    """
    Run pipeline in background with WebSocket updates.

    The blocking work runs in a worker thread (``asyncio.to_thread``), so the
    API, status polls, and WebSockets stay responsive during a run.

    Args:
        run_id: Unique pipeline run identifier
        config: Pipeline configuration
        profile: User profile
        stop_at: Last stage to run, or None for every stage
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

        result, shortlist_src = await asyncio.to_thread(
            _execute_pipeline,
            run_id,
            config,
            profile,
            stop_at,
            asyncio.get_running_loop(),
        )

        pipeline_runs[run_id]["jobs_scraped"] = result.jobs_scraped
        pipeline_runs[run_id]["jobs_scored"] = result.jobs_scored
        pipeline_runs[run_id]["jobs_selected"] = len(shortlist_src or [])
        pipeline_runs[run_id]["applications_submitted"] = result.jobs_applied
        pipeline_runs[run_id]["result"] = result
        pipeline_runs[run_id]["completed_at"] = datetime.now()

        # A user cancel stops the run at the next stage boundary. Keep the
        # cancelled status; the cancel endpoint already announced it.
        if pipeline_runs[run_id].get("status") == "cancelled":
            logger.info(f"Pipeline {run_id} stopped after cancel request")
            return

        if not result.success:
            message, failed_stage = _failure_message(result)
            pipeline_runs[run_id]["status"] = "failed"
            pipeline_runs[run_id]["error"] = message
            await manager.broadcast_pipeline_failed(run_id, message, failed_stage)
            logger.warning(f"Pipeline {run_id} failed: {message}")
            return

        pipeline_runs[run_id]["status"] = "completed"
        pipeline_runs[run_id]["stage_progress"] = 100

        # Notify completion
        await manager.broadcast_pipeline_complete(
            run_id,
            {
                "success": result.success,
                "duration_seconds": result.duration_seconds,
                "jobs_scraped": result.jobs_scraped,
                "jobs_scored": result.jobs_scored,
                "jobs_applied": result.jobs_applied,
                "stages_completed": len(result.stages_completed),
                "mode": getattr(config, "mode", "discover"),
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
        mode=request.mode,
        min_score=request.min_score,
        scam_threshold=request.scam_threshold,
        scam_action=request.scam_action,
        fresh_grad_mode=request.fresh_grad_mode,
        max_jobs_to_present=request.max_jobs,
        submission_delay=request.submission_delay,
        max_submissions_per_hour=request.max_submissions_per_hour,
    )
    stop_at = resolve_stop_at(request.mode, request.stop_at)

    # Initialize run state early so status endpoints work even if profile
    # resolution fails.
    pipeline_runs[run_id] = {
        "run_id": run_id,
        "status": "pending",
        "config": config,
        "stop_at": stop_at.value if stop_at else None,
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
    background_tasks.add_task(run_pipeline_async, run_id, config, profile, stop_at)

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
    result = run.get("result")

    jobs_scraped = run.get("jobs_scraped", 0)
    jobs_scored = run.get("jobs_scored", 0)
    jobs_selected = run.get("jobs_selected", 0)
    applications_submitted = run.get("applications_submitted", 0)
    cloud_documents = 0
    jobs_for_resumes = 0
    resumes_generated = 0
    if result is not None:
        jobs_scraped = getattr(result, "jobs_scraped", jobs_scraped) or jobs_scraped
        jobs_scored = getattr(result, "jobs_scored", jobs_scored) or jobs_scored
        applications_submitted = (
            getattr(result, "jobs_applied", applications_submitted)
            or applications_submitted
        )
        stage_results = getattr(result, "stage_results", None) or {}
        select = stage_results.get("present_selection")
        if select is not None:
            meta = getattr(select, "metadata", None) or {}
            jobs_for_resumes = int(meta.get("selected_count") or 0)
        generate = stage_results.get("generate_resumes")
        if generate is not None:
            meta = getattr(generate, "metadata", None) or {}
            cloud_documents = int(meta.get("cloud_documents") or 0)
            resumes_generated = int(meta.get("generated_count") or 0)

    return PipelineStatusResponse(
        run_id=run_id,
        status=run["status"],
        current_stage=run.get("current_stage"),
        stage_progress=run.get("stage_progress", 0),
        jobs_scraped=jobs_scraped,
        jobs_scored=jobs_scored,
        jobs_selected=jobs_selected,
        applications_submitted=applications_submitted,
        started_at=run.get("started_at"),
        error_message=run.get("error"),
        stages_planned=run.get("stages_planned", []),
        stages_completed=run.get("stages_completed", []),
        cloud_documents=cloud_documents,
        jobs_for_resumes=jobs_for_resumes,
        resumes_generated=resumes_generated,
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
        "stages_completed": list(result.stages_completed),
        "jobs_scraped": result.jobs_scraped,
        "jobs_applied": result.jobs_applied,
        "stage_results": {
            stage_name: {
                "success": stage_result.success,
                "metadata": stage_result.metadata,
            }
            for stage_name, stage_result in result.stage_results.items()
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

    # The orchestrator checks this status before each stage, so the run stops
    # at the next stage boundary. A stage that is running is not interrupted.
    run["status"] = "cancelled"

    await manager.broadcast_pipeline_failed(
        run_id,
        "Pipeline cancelled by user",
    )

    logger.info(f"Cancelled pipeline {run_id}")

    return {"run_id": run_id, "status": "cancelled"}


@router.get("/shortlist/latest")
async def get_latest_discover_shortlist():
    """
    Return the latest discover shortlist for Jobs review.

    Written when a pipeline run completes (discover or full). Empty when no
    discover run has finished yet.

    Returns:
        Shortlist payload with jobs in the Jobs search response shape.
    """
    data = load_latest_shortlist()
    if data is None:
        return {
            "run_id": None,
            "mode": None,
            "created_at": None,
            "keywords": [],
            "locations": [],
            "jobs_scraped": 0,
            "total": 0,
            "jobs": [],
        }
    # One-shot backfill for shortlists saved before description enrich.
    try:
        data = enrich_shortlist_payload_descriptions(data)
    except Exception as enrich_err:
        logger.warning("Shortlist description backfill failed: %s", enrich_err)
    jobs = data.get("jobs")
    if isinstance(jobs, list) and jobs:
        try:
            AppliedGuard().annotate_job_dicts(jobs)
        except Exception as guard_err:
            logger.warning("Shortlist applied-guard annotate failed: %s", guard_err)
    return data


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
                "jobs_scraped": (
                    getattr(r.get("result"), "jobs_scraped", None)
                    if r.get("result") is not None
                    else r.get("jobs_scraped", 0)
                )
                or r.get("jobs_scraped", 0),
                "jobs_scored": (
                    getattr(r.get("result"), "jobs_scored", None)
                    if r.get("result") is not None
                    else r.get("jobs_scored", 0)
                )
                or r.get("jobs_scored", 0),
                "jobs_applied": (
                    getattr(r.get("result"), "jobs_applied", None)
                    if r.get("result") is not None
                    else r.get("applications_submitted", 0)
                )
                or r.get("applications_submitted", 0),
                "mode": getattr(r.get("config"), "mode", None),
            }
            for r in runs
        ],
        "total": len(runs),
    }
