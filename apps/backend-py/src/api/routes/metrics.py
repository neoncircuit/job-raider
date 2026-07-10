"""
Job Raider - Metrics API Routes

API endpoints for cost tracking and outcome metrics.

Author: Job Raider
Date: 2026-04-21
"""

from typing import Any, Dict

from fastapi import APIRouter

from ...health.health_check import check_health
from ...metrics.cost_tracker import CostTracker
from ...metrics.outcome_tracker import OutcomeTracker
from ...utils.logger import Components, get_logger
from ..models.responses import HealthCheckResponse, MetricsResponse

router = APIRouter()
logger = get_logger(Components.SCRAPERS)

# Global tracker instances (use database in production)
cost_tracker = CostTracker()
outcome_tracker = OutcomeTracker()


@router.get("/costs")
async def get_cost_metrics() -> MetricsResponse:
    """
    Get cost tracking metrics.

    Returns:
        Cost metrics including total spent, per-application costs,
        and API vs local model usage breakdown.
    """
    summary = cost_tracker.get_summary()

    total_calls = len(cost_tracker._calls)
    local_calls = [c for c in cost_tracker._calls if c.provider.value == "ollama"]
    local_percentage = (len(local_calls) / total_calls * 100) if total_calls > 0 else 0

    return MetricsResponse(
        total_cost_usd=summary.get("total_cost_usd", 0.0),
        cost_per_application=summary.get("cost_per_application", 0.0),
        api_costs_usd=summary.get("api_cost_usd", 0.0),
        local_model_usage=local_percentage,
        pipeline_runs=summary.get("total_calls", 0),
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
    # Get cost metrics
    cost_summary = cost_tracker.get_summary()

    # Get outcome metrics
    cm = outcome_tracker.get_conversion_metrics()

    # Get health check
    health_report = check_health()

    total_calls = len(cost_tracker._calls)
    local_calls = [c for c in cost_tracker._calls if c.provider.value == "ollama"]
    local_percentage = (len(local_calls) / total_calls * 100) if total_calls > 0 else 0

    return {
        "cost": {
            "total_usd": cost_summary.get("total_cost_usd", 0.0),
            "per_application": cost_summary.get("cost_per_application", 0.0),
            "api_usd": cost_summary.get("api_cost_usd", 0.0),
            "local_usage_percent": local_percentage,
            "total_calls": total_calls,
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
        "recent_calls": [
            {
                "task_type": call.task_type.value,
                "provider": call.provider.value,
                "model": call.model_name,
                "cost_usd": call.cost_usd,
                "timestamp": call.timestamp.isoformat(),
            }
            for call in cost_tracker._calls[-10:]
        ],
    }
