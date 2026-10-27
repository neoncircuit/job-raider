"""
Job Raider - Metrics API Routes

API endpoints for cost tracking and outcome metrics.

Author: Job Raider
Date: 2026-04-21
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from ...health.health_check import check_health
from ...metrics.cost_tracker import (
    CallRecord,
    get_cost_tracker,
    list_cost_run_files,
    load_latest_cost_run,
)
from ...metrics.outcome_tracker import OutcomeTracker
from ...utils.logger import Components, get_logger
from ..models.responses import HealthCheckResponse, MetricsResponse

router = APIRouter()
logger = get_logger(Components.SCRAPERS)

outcome_tracker = OutcomeTracker()


def _process_usage() -> Dict[str, Any]:
    """
    Build the process-wide usage block.

    Returns:
        Calls, tokens, flags, cost, and local share.
    """
    totals = get_cost_tracker().process_totals()
    calls = int(totals.get("calls") or 0)
    local = int(totals.get("local_calls") or 0)
    return {
        "calls": calls,
        "prompt_tokens": int(totals.get("prompt_tokens") or 0),
        "completion_tokens": int(totals.get("completion_tokens") or 0),
        "total_tokens": int(totals.get("total_tokens") or 0),
        "estimated_counts": int(totals.get("estimated_counts") or 0),
        "cache_hits": int(totals.get("cache_hits") or 0),
        "fallbacks": int(totals.get("fallbacks") or 0),
        "errors": int(totals.get("errors") or 0),
        "cost_usd": totals.get("cost_usd"),
        "local_share": (local / calls) if calls else 0.0,
    }


def _last_run_usage(latest: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Build the last-run usage block from a saved file.

    Args:
        latest: Parsed run file, or ``None``.

    Returns:
        Last-run counts, or ``None`` when no file exists.
    """
    if not latest:
        return None
    summary = latest.get("summary") or {}
    calls_data = latest.get("calls") or []
    local = sum(1 for call in calls_data if call.get("provider") == "ollama")
    calls = int(summary.get("total_calls") or 0)
    documents = int(summary.get("documents") or 0)
    cost = summary.get("total_cost_usd")
    per_app = summary.get("cost_per_application")
    if per_app is None and documents > 0 and cost is not None:
        per_app = cost / documents
    return {
        "run_id": latest.get("run_id"),
        "end_time": latest.get("end_time"),
        "calls": calls,
        "prompt_tokens": int(summary.get("prompt_tokens") or 0),
        "completion_tokens": int(summary.get("completion_tokens") or 0),
        "total_tokens": int(summary.get("total_tokens") or 0),
        "estimated_counts": int(summary.get("estimated_counts") or 0),
        "cache_hits": int(summary.get("cache_hits") or 0),
        "fallbacks": int(summary.get("fallbacks") or 0),
        "errors": int(summary.get("errors") or 0),
        "cost_usd": cost,
        "documents": documents,
        "cost_per_application": per_app,
        "local_share": (local / calls) if calls else 0.0,
    }


def _recent_payload(records: List[CallRecord]) -> List[Dict[str, Any]]:
    """
    Serialize recent call records for the API.

    Args:
        records: Recent records, oldest first.

    Returns:
        The last 10 records, newest last.
    """
    return [
        {
            "task_type": record.task_type,
            "provider": record.provider,
            "model": record.model,
            "cost_usd": record.cost_usd,
            "timestamp": record.timestamp.isoformat(),
            "prompt_tokens": record.prompt_tokens,
            "completion_tokens": record.completion_tokens,
            "total_tokens": record.total_tokens,
            "tokens_estimated": record.tokens_estimated,
            "cache_hit": record.cache_hit,
            "fallback": record.fallback,
            "error": record.error,
        }
        for record in records[-10:]
    ]


@router.get("/costs")
async def get_cost_metrics() -> MetricsResponse:
    """
    Get cost tracking metrics for this process and the last saved run.

    Returns:
        Cost metrics including tokens, flags, and the last run.
    """
    process = _process_usage()
    last_run = _last_run_usage(load_latest_cost_run())
    per_app = last_run.get("cost_per_application") if last_run else None
    return MetricsResponse(
        total_cost_usd=process["cost_usd"],
        cost_per_application=per_app,
        api_costs_usd=None,
        local_model_usage=process["local_share"] * 100,
        pipeline_runs=len(list_cost_run_files()),
        prompt_tokens=process["prompt_tokens"],
        completion_tokens=process["completion_tokens"],
        total_tokens=process["total_tokens"],
        estimated_counts=process["estimated_counts"],
        cache_hits=process["cache_hits"],
        fallbacks=process["fallbacks"],
        errors=process["errors"],
        last_run=last_run,
    )


@router.get("/outcomes")
async def get_outcome_metrics() -> MetricsResponse:
    """
    Get application outcome metrics.

    Returns:
        Outcome metrics including interviews, offers, and conversion rates.
    """
    cm = outcome_tracker.get_conversion_metrics()

    return MetricsResponse(
        total_applications=cm.total_applications,
        interview_rate=cm.screening_rate,
        offer_rate=cm.offer_rate,
        overall_rate=cm.acceptance_rate,
    )


@router.get("/health")
async def get_health_metrics() -> HealthCheckResponse:
    """
    Get system health metrics.

    Returns:
        System health status including GPU, Ollama, and data directories.
    """
    report = check_health()

    return HealthCheckResponse(
        status=report["status"],
        timestamp=report["timestamp"],
        checks=report["checks"],
        summary=report["summary"],
    )


@router.get("/summary")
async def get_metrics_summary() -> Dict[str, Any]:
    """
    Get combined metrics summary.

    Returns:
        Combined cost, outcome, and health metrics.
    """
    process = _process_usage()
    last_run = _last_run_usage(load_latest_cost_run())
    cm = outcome_tracker.get_conversion_metrics()
    health_report = check_health()
    per_app = last_run.get("cost_per_application") if last_run else None

    return {
        "cost": {
            "total_usd": process["cost_usd"],
            "per_application": per_app,
            "api_usd": None,
            "local_usage_percent": process["local_share"] * 100,
            "total_calls": process["calls"],
            "prompt_tokens": process["prompt_tokens"],
            "completion_tokens": process["completion_tokens"],
            "total_tokens": process["total_tokens"],
            "estimated_counts": process["estimated_counts"],
            "cache_hits": process["cache_hits"],
            "fallbacks": process["fallbacks"],
            "errors": process["errors"],
            "pipeline_runs": len(list_cost_run_files()),
            "last_run": last_run,
        },
        "outcomes": {
            "total_applications": cm.total_applications,
            "screening_rate": cm.screening_rate,
            "offer_rate": cm.offer_rate,
            "acceptance_rate": cm.acceptance_rate,
        },
        "health": {
            "status": health_report["status"],
            "checks": len(health_report["checks"]),
            "healthy": health_report["summary"]["healthy"],
            "degraded": health_report["summary"]["degraded"],
            "unhealthy": health_report["summary"]["unhealthy"],
        },
        "recent_calls": _recent_payload(get_cost_tracker().recent_calls()),
    }
