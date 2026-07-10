"""
Agent API Routes for Job Raider Multi-Agent System

Provides REST API endpoints for interacting with the multi-agent system,
including career analysis, recommendations, and agent status monitoring.
"""

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from ...agents.base import Task, TaskType
from ...agents.career_coach import CareerCoachAgent
from ...agents.coordinator import AgentCoordinator
from ...llm.router import LLMRouter
from ..auth import verify_api_key
from ..rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


# Thread-safe singleton for agent coordinator
class AgentSystemManager:
    """Thread-safe singleton manager for the agent system."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the manager (only called once)."""
        if not hasattr(self, "_initialized"):
            self._coordinator: Optional[AgentCoordinator] = None
            # Strong reference to the coordinator's background asyncio task.
            # Without it, the task can be garbage-collected and cancelled
            # before the coordinator finishes starting.
            self._background_task: Optional[Any] = None
            self._initialized = True

    def get_coordinator(self) -> Optional[AgentCoordinator]:
        """Get the agent coordinator instance."""
        return self._coordinator

    def set_coordinator(self, coordinator: AgentCoordinator):
        """Set the agent coordinator instance."""
        self._coordinator = coordinator

    def set_background_task(self, task: Any) -> None:
        """Retain a strong reference to the coordinator's background task.

        Args:
            task: The asyncio Task created for ``coordinator.start()``.
        """
        self._background_task = task


# Global singleton instance
_agent_manager = AgentSystemManager()


# Pydantic models for request validation
class CareerAnalysisRequest(BaseModel):
    """Request model for career analysis."""

    profile: Dict[str, Any] = Field(..., description="User profile data")
    target_jobs: List[Dict[str, Any]] = Field(
        default_factory=list, description="Optional target jobs for analysis"
    )

    @field_validator("profile")
    @classmethod
    def profile_must_not_be_empty(cls, v):
        if not v or not isinstance(v, dict):
            raise ValueError("Profile must be a non-empty dictionary")
        return v


class GapAnalysisRequest(BaseModel):
    """Request model for gap analysis."""

    profile: Dict[str, Any] = Field(..., description="User profile data")
    target_jobs: List[Dict[str, Any]] = Field(
        ..., min_length=1, description="Target jobs to analyze gaps against"
    )

    @field_validator("profile")
    @classmethod
    def profile_must_not_be_empty(cls, v):
        if not v or not isinstance(v, dict):
            raise ValueError("Profile must be a non-empty dictionary")
        return v

    @field_validator("target_jobs")
    @classmethod
    def target_jobs_must_not_be_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one target job must be provided")
        return v


class UpskillingRoadmapRequest(BaseModel):
    """Request model for upskilling roadmap generation."""

    gap_analysis: Dict[str, Any] = Field(..., description="Gap analysis results")
    profile: Optional[Dict[str, Any]] = Field(
        None, description="Optional user profile for context"
    )

    @field_validator("gap_analysis")
    @classmethod
    def gap_analysis_must_be_valid(cls, v):
        if not v or not isinstance(v, dict):
            raise ValueError("Gap analysis must be a valid dictionary")
        if "skills_gap" not in v:
            raise ValueError("Gap analysis must contain skills_gap field")
        return v


class CareerGoalsRequest(BaseModel):
    """Request model for career goal setting."""

    profile: Dict[str, Any] = Field(..., description="User profile data")

    @field_validator("profile")
    @classmethod
    def profile_must_not_be_empty(cls, v):
        if not v or not isinstance(v, dict):
            raise ValueError("Profile must be a non-empty dictionary")
        return v


def get_agent_coordinator() -> AgentCoordinator:
    """Dependency to get the agent coordinator instance."""
    coordinator = _agent_manager.get_coordinator()
    if coordinator is None:
        raise HTTPException(status_code=503, detail="Agent system not initialized")
    return coordinator


def _require_task_id(task_id: str) -> str:
    """
    Validate that the coordinator accepted a task submission.

    Args:
        task_id: Task identifier returned by the coordinator.

    Returns:
        The validated task identifier.

    Raises:
        HTTPException: 503 if the coordinator did not return a task ID, meaning
            the agent system is unable to accept work at this time.
    """
    if not task_id:
        raise HTTPException(
            status_code=503,
            detail="Agent system is currently unavailable. Please try again later.",
        )
    return task_id


async def _check_rate_limit(http_request: Request) -> None:
    """
    Enforce rate limiting for the current request path.

    Args:
        http_request: Incoming HTTP request.

    Raises:
        HTTPException: 429 if the rate limit has been exceeded.
    """
    limiter = get_rate_limiter()
    client_id = http_request.client.host if http_request.client else "unknown"
    endpoint = http_request.url.path
    allowed, error_message = limiter.check_rate_limit(client_id, endpoint)
    if not allowed:
        raise HTTPException(
            status_code=429, detail={"error": error_message, "retry_after": 60}
        )


def initialize_agent_system(llm_router: LLMRouter) -> AgentCoordinator:
    """
    Initialize the agent system with all required agents.

    Args:
        llm_router: LLM router for agent operations

    Returns:
        Initialized agent coordinator
    """
    coordinator = _agent_manager.get_coordinator()

    if coordinator is not None:
        return coordinator

    try:
        logger.info("Initializing agent system...")

        # Create coordinator
        coordinator = AgentCoordinator()

        # Initialize Career Coach Agent
        career_coach = CareerCoachAgent(llm_router=llm_router)
        coordinator.register_agent(career_coach)
        logger.info("Career Coach Agent registered")

        # Start coordinator (retain a strong reference so the task is not
        # garbage-collected and cancelled before it starts the coordinator).
        import asyncio

        start_task = asyncio.create_task(coordinator.start())
        _agent_manager.set_background_task(start_task)

        # Store in singleton
        _agent_manager.set_coordinator(coordinator)

        logger.info("Agent system initialized successfully")
        return coordinator

    except Exception as e:
        logger.error(f"Failed to initialize agent system: {e}")
        raise


@router.get("/status")
async def get_agent_status(
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
    authorized: None = Depends(verify_api_key),
) -> JSONResponse:
    """
    Get status of all registered agents.

    Returns:
        Dictionary containing agent status information
    """
    try:
        system_status = coordinator.get_system_status()
        return JSONResponse(
            content={
                "success": True,
                "data": system_status,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_agent_performance(
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
) -> JSONResponse:
    """
    Get performance metrics for all agents.

    Returns:
        Dictionary containing agent performance metrics
    """
    try:
        performance = coordinator.get_performance_metrics()
        return JSONResponse(
            content={
                "success": True,
                "data": performance,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error getting agent performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/career-analysis")
async def trigger_career_analysis(
    request: CareerAnalysisRequest,
    http_request: Request,
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
    authorized: None = Depends(verify_api_key),
) -> JSONResponse:
    """
    Trigger career analysis using the Career Coach agent.

    Args:
        request: Validated request containing profile and optional target jobs
        http_request: Incoming HTTP request for rate limiting
        coordinator: Agent coordinator dependency
        authorized: API key authorization dependency

    Returns:
        Task ID for tracking the analysis
    """
    await _check_rate_limit(http_request)

    try:
        task = Task(
            type=TaskType.CAREER_PATH_ANALYSIS,
            data={"profile": request.profile},
            context={"profile": request.profile, "target_jobs": request.target_jobs},
            priority=7,
        )

        task_id = _require_task_id(
            await coordinator.submit_task(task, agent_id="career_coach")
        )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "task_id": task_id,
                    "agent": "career_coach",
                    "task_type": "career_path_analysis",
                    "status": "submitted",
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering career analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gap-analysis")
async def trigger_gap_analysis(
    request: GapAnalysisRequest,
    http_request: Request,
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
    authorized: None = Depends(verify_api_key),
) -> JSONResponse:
    """
    Trigger gap analysis using the Career Coach agent.

    Args:
        request: Validated request containing profile and target jobs
        http_request: Incoming HTTP request for rate limiting
        coordinator: Agent coordinator dependency
        authorized: API key authorization dependency

    Returns:
        Task ID for tracking the analysis
    """
    await _check_rate_limit(http_request)

    try:
        task = Task(
            type=TaskType.GAP_ANALYSIS,
            data={"profile": request.profile, "target_jobs": request.target_jobs},
            context={"profile": request.profile, "target_jobs": request.target_jobs},
            priority=7,
        )

        task_id = _require_task_id(
            await coordinator.submit_task(task, agent_id="career_coach")
        )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "task_id": task_id,
                    "agent": "career_coach",
                    "task_type": "gap_analysis",
                    "status": "submitted",
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering gap analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upskilling-roadmap")
async def create_upskilling_roadmap(
    request: UpskillingRoadmapRequest,
    http_request: Request,
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
    authorized: None = Depends(verify_api_key),
) -> JSONResponse:
    """
    Generate upskilling roadmap based on gap analysis.

    Args:
        request: Validated request containing gap analysis results
        http_request: Incoming HTTP request for rate limiting
        coordinator: Agent coordinator dependency
        authorized: API key authorization dependency

    Returns:
        Task ID for tracking the roadmap generation
    """
    await _check_rate_limit(http_request)

    try:
        task = Task(
            type=TaskType.UPSKILLING_ROADMAP,
            data={"gap_analysis": request.gap_analysis},
            context={"gap_analysis": request.gap_analysis, "profile": request.profile},
            priority=6,
        )

        task_id = _require_task_id(
            await coordinator.submit_task(task, agent_id="career_coach")
        )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "task_id": task_id,
                    "agent": "career_coach",
                    "task_type": "upskilling_roadmap",
                    "status": "submitted",
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating upskilling roadmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/career-goals")
async def set_career_goals(
    request: CareerGoalsRequest,
    http_request: Request,
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
    authorized: None = Depends(verify_api_key),
) -> JSONResponse:
    """
    Generate SMART career goals based on profile and market analysis.

    Args:
        request: Validated request containing profile information
        http_request: Incoming HTTP request for rate limiting
        coordinator: Agent coordinator dependency
        authorized: API key authorization dependency

    Returns:
        Task ID for tracking the goal setting
    """
    await _check_rate_limit(http_request)

    try:
        task = Task(
            type=TaskType.CAREER_GOAL_SETTING,
            data={"profile": request.profile},
            context={"profile": request.profile},
            priority=5,
        )

        task_id = _require_task_id(
            await coordinator.submit_task(task, agent_id="career_coach")
        )

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "task_id": task_id,
                    "agent": "career_coach",
                    "task_type": "career_goal_setting",
                    "status": "submitted",
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting career goals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_result(
    task_id: str,
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
) -> JSONResponse:
    """
    Retrieve the result of a previously submitted agent task.

    Args:
        task_id: Task identifier returned by a task submission endpoint.
        coordinator: Agent coordinator dependency.

    Returns:
        ``200`` with the stored result envelope when complete, ``202`` when the
        task is still pending, or ``404`` when the task ID is unknown or expired.
    """
    if not task_id or not task_id.strip():
        raise HTTPException(status_code=400, detail="Task ID is required")

    record = coordinator.get_task_result(task_id.strip())
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if record["status"] == "pending":
        return JSONResponse(
            content={
                "success": True,
                "data": record,
                "timestamp": datetime.now().isoformat(),
            },
            status_code=202,
        )

    return JSONResponse(
        content={
            "success": True,
            "data": record,
            "timestamp": datetime.now().isoformat(),
        }
    )


@router.get("/recommendations")
async def get_recommendations(
    profile_id: Optional[str] = None,
    limit: int = 10,
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
) -> JSONResponse:
    """
    Get career recommendations from the Career Coach agent.

    Args:
        profile_id: Optional profile ID for personalized recommendations
        limit: Maximum number of recommendations to return

    Returns:
        Career recommendations
    """
    try:
        # This would typically fetch from a database of previous recommendations
        # For now, we'll return a sample response
        recommendations = [
            {
                "type": "skill_development",
                "title": "Learn Python",
                "description": "Python is a highly demanded skill across many job roles",
                "priority": "high",
                "confidence": 0.9,
                "timeline": "4-6 weeks",
            },
            {
                "type": "career_path",
                "title": "Pursue Full Stack Development",
                "description": "Your current skills align well with full stack development roles",
                "priority": "medium",
                "confidence": 0.85,
                "timeline": "6-12 months",
            },
        ]

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "recommendations": recommendations[:limit],
                    "total": len(recommendations),
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
) -> JSONResponse:
    """
    Perform health check on the agent system.

    Returns:
        Health status information
    """
    try:
        is_healthy = await coordinator.health_check()

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "healthy": is_healthy,
                    "coordinator_running": coordinator._running,
                    "registered_agents": len(coordinator.agents),
                    "communication_healthy": coordinator.communication_bus.is_healthy(),
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error performing health check: {e}")
        return JSONResponse(
            content={
                "success": False,
                "data": {"healthy": False, "error": str(e)},
                "timestamp": datetime.now().isoformat(),
            },
            status_code=503,
        )


@router.post("/shutdown")
async def shutdown_agents(
    coordinator: AgentCoordinator = Depends(get_agent_coordinator),
) -> JSONResponse:
    """
    Shutdown the agent system gracefully.

    Returns:
        Shutdown confirmation
    """
    try:
        await coordinator.stop()

        return JSONResponse(
            content={
                "success": True,
                "data": {"message": "Agent system shut down successfully"},
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error shutting down agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))
