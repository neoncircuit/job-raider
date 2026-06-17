"""
Job Raider - FastAPI Web Application

Main FastAPI application for the Job Raider automated job application pipeline.
Provides REST API endpoints and WebSocket support for real-time pipeline monitoring.

Author: Job Raider
Date: 2026-04-21
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..utils.logger import Components, get_logger
from ..utils.sentry import init_sentry
from .auth import verify_api_key
from .routes import (
    agents,
    applications,
    assessment,
    jobs,
    metrics,
    pipeline,
    profile,
    settings,
)
from .websocket.progress import manager

logger = get_logger(Components.SCRAPERS)


# Store active pipeline runs
active_runs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    logger.info("Job Raider API starting up...")
    init_sentry()

    # Critical: Check available LLM providers
    await validate_llm_providers()

    # Initialize the multi-agent system. Non-fatal: the API still boots if the
    # agent system cannot start; agent endpoints return 503 until it is ready.
    try:
        from ..llm.router import LLMRouter
        from .routes.agents import initialize_agent_system

        initialize_agent_system(LLMRouter())
        logger.info("Multi-agent system initialized")
    except Exception as e:
        logger.warning(
            "Multi-agent system initialization failed (agent endpoints will "
            f"return 503): {e}"
        )

    yield
    logger.info("Job Raider API shutting down...")


async def validate_llm_providers():
    """
    Validate available LLM providers at startup.

    This is a critical safety check to ensure the application can function.
    If no providers are available, we log a warning but don't crash -
    the application will fail gracefully when LLM features are used.
    """
    import os
    import sys

    logger.info("=== LLM Provider Validation ===")

    available_providers = []
    missing_providers = []

    # Check Ollama
    ollama_host = os.getenv("OLLAMA_HOST", "localhost:11434")
    try:
        import requests

        response = requests.get(
            f"http://{ollama_host.replace('http://', '')}/api/tags", timeout=3
        )
        if response.status_code == 200:
            models = response.json().get("models", [])
            available_providers.append(
                f"✅ Ollama ({ollama_host}): {len(models)} models"
            )
            if len(models) == 0:
                available_providers.append(
                    "  ⚠️  WARNING: Ollama connected but no models loaded!"
                )
        else:
            missing_providers.append(
                f"❌ Ollama ({ollama_host}): Returned status {response.status_code}"
            )
    except Exception as e:
        missing_providers.append(f"❌ Ollama ({ollama_host}): {str(e)[:50]}")

    # Check Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        available_providers.append("✅ Anthropic: API key configured")
    else:
        missing_providers.append("❌ Anthropic: No API key (fallback unavailable)")

    # Check Gemini
    if os.getenv("GEMINI_API_KEY"):
        available_providers.append("✅ Gemini: API key configured")
    else:
        missing_providers.append("❌ Gemini: No API key (fallback unavailable)")

    # Report results
    logger.info("Available Providers:")
    for provider in available_providers:
        logger.info(f"  {provider}")

    if missing_providers:
        logger.warning("Missing Providers:")
        for provider in missing_providers:
            logger.warning(f"  {provider}")
        logger.warning("⚠️  WARNING: Application has limited LLM fallback options!")
        logger.warning(
            "   Set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env for fallback"
        )

    if not available_providers:
        logger.error(
            "🚨 CRITICAL: No LLM providers available! Application will fail when LLM features are used."
        )

    logger.info("=== Provider Validation Complete ===")


# Create FastAPI application
app = FastAPI(
    title="Job Raider API",
    description="Automated Job Application Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for simple frontend
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Include routers — all protected by API key auth (WebSocket is excluded; it
# runs its own connect handshake before the auth header is available).
_auth = [Depends(verify_api_key)]

app.include_router(
    pipeline.router, prefix="/api/pipeline", tags=["Pipeline"], dependencies=_auth
)
app.include_router(
    profile.router, prefix="/api/profile", tags=["Profile"], dependencies=_auth
)
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"], dependencies=_auth)
app.include_router(
    applications.router,
    prefix="/api/applications",
    tags=["Applications"],
    dependencies=_auth,
)
app.include_router(
    metrics.router, prefix="/api/metrics", tags=["Metrics"], dependencies=_auth
)
app.include_router(
    settings.router, prefix="/api/settings", tags=["Settings"], dependencies=_auth
)
app.include_router(
    assessment.router, prefix="/api/assessment", tags=["Assessment"], dependencies=_auth
)
# The agents router declares its own prefix ("/api/agents") on the APIRouter
# itself (see routes/agents.py), so it is registered here WITHOUT a prefix to
# avoid double-prefixing to /api/api/agents.
app.include_router(agents.router, tags=["Agents"], dependencies=_auth)


@app.get("/")
async def root():
    """Root endpoint - redirect to API docs or simple UI."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "message": "Job Raider API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.

    Returns system health status including GPU, Ollama, and data directories.
    """
    from src.health.health_check import check_health

    report = check_health()
    return {
        "status": report["status"],
        "timestamp": report["timestamp"],
        "checks": report["checks"],
        "summary": report["summary"],
    }


@app.get("/api/version")
async def version():
    """API version information."""
    return {
        "version": "0.1.0",
        "name": "Job Raider API",
    }


@app.websocket("/api/pipeline/{run_id}/progress")
async def pipeline_progress(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time pipeline progress updates.

    Args:
        websocket: WebSocket connection
        run_id: Pipeline run ID to monitor
    """
    await manager.connect(run_id, websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back or handle client messages if needed
            await manager.send_message(run_id, {"type": "ping", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(run_id, websocket)
        logger.info(f"WebSocket disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
        manager.disconnect(run_id, websocket)


# Export for testing
__all__ = ["app", "active_runs"]
