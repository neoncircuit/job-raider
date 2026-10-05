"""
Job Raider - Evaluation API Routes

Run the safe cover-letter model compare from the app. One compare runs at a
time in a worker thread; progress is polled and the result is logged to
MLflow. The same allow-list and cool-down rules as the CLI apply.
"""

import threading
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ...evaluation import cover_letter_compare as compare
from ...utils.logger import Components, get_logger
from ..ollama_models import ollama_base_url, resolve_effective_ollama_host
from ..settings import get_storage

router = APIRouter()
logger = get_logger(Components.GENERATION)

_run_lock = threading.Lock()
_state: Dict[str, Any] = {"status": "idle"}


class CompareRequest(BaseModel):
    """Request body for starting a cover-letter model compare."""

    models: List[str] = Field(
        default_factory=lambda: list(compare.ALLOWED_MODELS),
        description="Models to compare, run in order (allow-list only)",
    )
    cool_down_s: float = Field(
        default=compare.DEFAULT_COOL_DOWN_S,
        ge=0,
        le=120,
        description="Seconds to wait after unloading each model",
    )


def _ollama_base() -> str:
    """Resolve the Ollama base URL from Settings and the environment.

    Returns:
        Base URL such as ``http://host.docker.internal:11434``.
    """
    settings = get_storage().load_settings()
    return ollama_base_url(
        resolve_effective_ollama_host(settings.api_config.ollama_host)
    )


def _on_progress(model: str, case_id: str, done: int, total: int) -> None:
    """Record compare progress for the status endpoint.

    Args:
        model: Model tag being run.
        case_id: Fixture id about to run.
        done: Cases finished so far.
        total: Total cases.
    """
    _state.update(
        {"current_model": model, "current_case": case_id, "done": done, "total": total}
    )


def _run(models: List[str], base_url: str, cool_down_s: float) -> None:
    """Run the compare, save and log the report, then free the slot.

    Args:
        models: Validated, installed model tags.
        base_url: Ollama base URL.
        cool_down_s: Cool-down seconds after each model.
    """
    try:
        report = compare.run_compare(
            models, base_url=base_url, cool_down_s=cool_down_s, on_progress=_on_progress
        )
        path = compare.save_report(report)
        report["mlflow"] = compare.log_to_mlflow(report, path)
        compare.save_report(report, path)
        _state.update(
            {"status": "completed", "done": _state.get("total") or 0, "report": report}
        )
        logger.info("Cover-letter compare completed; winner=%s", report["winner"])
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        _state.update({"status": "failed", "error": str(exc)[:300]})
        logger.exception("Cover-letter compare failed")
    finally:
        _state["finished_at"] = datetime.now().isoformat()
        _run_lock.release()


@router.post("/cover-letter-compare", status_code=202, response_model=Dict[str, Any])
async def start_cover_letter_compare(
    body: CompareRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Start a cover-letter model compare in the background.

    Args:
        body: Models and cool-down.
        background_tasks: FastAPI background task runner.

    Returns:
        The compare state after it starts.
    """
    try:
        compare.validate_models(body.models)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    base_url = _ollama_base()
    try:
        installed = await run_in_threadpool(compare.list_installed_models, base_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    missing = [m for m in body.models if not compare.model_is_installed(m, installed)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Not installed: {', '.join(missing)}. Pull from Settings > Local models.",
        )

    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A compare is already running.")
    _state.clear()
    _state.update(
        {
            "status": "running",
            "models": body.models,
            "cool_down_s": body.cool_down_s,
            "current_model": None,
            "current_case": None,
            "done": 0,
            "total": None,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "error": None,
        }
    )
    background_tasks.add_task(_run, list(body.models), base_url, body.cool_down_s)
    logger.info("Cover-letter compare started: %s", body.models)
    return dict(_state)


@router.get("/cover-letter-compare/status", response_model=Dict[str, Any])
async def cover_letter_compare_status() -> Dict[str, Any]:
    """
    Get the progress of the current or last compare in this process.

    Returns:
        State with ``status`` (idle, running, completed, failed) and progress.
    """
    return dict(_state)


@router.get("/cover-letter-compare/latest", response_model=Dict[str, Any])
async def latest_cover_letter_compare() -> Dict[str, Any]:
    """
    Get the last saved compare report (from the app or the CLI).

    Returns:
        Dict with ``report`` (or None when no compare has run).
    """
    return {"report": compare.load_report()}
