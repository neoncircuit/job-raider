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
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ..utils.logger import get_logger, Components
from ..utils.sentry import init_sentry
from .auth import verify_api_key
from .routes import pipeline, profile, jobs, metrics, settings, applications
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
    yield
    logger.info("Job Raider API shutting down...")


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

app.include_router(pipeline.router, prefix="/api/pipeline", tags=["Pipeline"], dependencies=_auth)
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"], dependencies=_auth)
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"], dependencies=_auth)
app.include_router(applications.router, prefix="/api/applications", tags=["Applications"], dependencies=_auth)
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"], dependencies=_auth)
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"], dependencies=_auth)


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
