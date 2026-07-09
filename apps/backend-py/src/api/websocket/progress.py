"""
Job Raider - WebSocket Progress Manager

Manages WebSocket connections for real-time pipeline progress updates.

Author: Job Raider
Date: 2026-04-21
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Set

from fastapi import WebSocket

from ...utils.logger import Components, get_logger

logger = get_logger(Components.SCRAPERS)


class ConnectionManager:
    """
    Manages WebSocket connections for pipeline progress updates.

    Maintains a mapping of run IDs to connected WebSocket clients
    and broadcasts progress events to all connected clients.
    """

    def __init__(self):
        """Initialize the connection manager."""
        # Map run_id to set of connected WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        """
        Connect a WebSocket client to a pipeline run.

        Args:
            run_id: Pipeline run ID
            websocket: WebSocket connection
        """
        await websocket.accept()

        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()

        self.active_connections[run_id].add(websocket)
        logger.info(f"WebSocket connected for run {run_id}")

        # Send connection confirmation
        await self.send_message(
            run_id,
            {
                "type": "connected",
                "run_id": run_id,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def disconnect(self, run_id: str, websocket: WebSocket):
        """
        Disconnect a WebSocket client from a pipeline run.

        Args:
            run_id: Pipeline run ID
            websocket: WebSocket connection
        """
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)

            # Clean up empty run groups
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
                logger.info(f"No more connections for run {run_id}")

        logger.info(f"WebSocket disconnected for run {run_id}")

    async def send_message(self, run_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to all connected clients for a run.

        Args:
            run_id: Pipeline run ID
            message: Message data to send

        Returns:
            True if message sent to at least one client, False otherwise
        """
        if run_id not in self.active_connections:
            return False

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()

        # Serialize to JSON
        data = json.dumps(message)

        # Send to all connected clients
        sent = False
        dead_connections = set()

        for websocket in self.active_connections[run_id]:
            try:
                await websocket.send_text(data)
                sent = True
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                dead_connections.add(websocket)

        # Clean up dead connections
        for websocket in dead_connections:
            self.disconnect(run_id, websocket)

        return sent

    async def broadcast_stage_started(
        self,
        run_id: str,
        stage: str,
        metadata: Dict[str, Any] = None,
    ):
        """
        Broadcast that a pipeline stage has started.

        Args:
            run_id: Pipeline run ID
            stage: Stage name
            metadata: Optional stage metadata
        """
        await self.send_message(
            run_id,
            {
                "type": "stage_started",
                "stage": stage,
                "metadata": metadata or {},
            },
        )

    async def broadcast_stage_progress(
        self,
        run_id: str,
        stage: str,
        progress: int,
        metadata: Dict[str, Any] = None,
    ):
        """
        Broadcast progress update for a pipeline stage.

        Args:
            run_id: Pipeline run ID
            stage: Stage name
            progress: Progress percentage (0-100)
            metadata: Optional progress metadata
        """
        await self.send_message(
            run_id,
            {
                "type": "stage_progress",
                "stage": stage,
                "progress": progress,
                "metadata": metadata or {},
            },
        )

    async def broadcast_stage_completed(
        self,
        run_id: str,
        stage: str,
        result: Dict[str, Any] = None,
    ):
        """
        Broadcast that a pipeline stage has completed.

        Args:
            run_id: Pipeline run ID
            stage: Stage name
            result: Optional stage result data
        """
        await self.send_message(
            run_id,
            {
                "type": "stage_completed",
                "stage": stage,
                "result": result or {},
            },
        )

    async def broadcast_jobs_found(
        self,
        run_id: str,
        count: int,
        source: str = None,
    ):
        """
        Broadcast that new jobs have been found.

        Args:
            run_id: Pipeline run ID
            count: Number of jobs found
            source: Optional source (linkedin, jsearch)
        """
        await self.send_message(
            run_id,
            {
                "type": "jobs_found",
                "count": count,
                "source": source,
            },
        )

    async def broadcast_jobs_scored(
        self,
        run_id: str,
        jobs: List[Dict[str, Any]],
    ):
        """
        Broadcast that jobs have been scored.

        Args:
            run_id: Pipeline run ID
            jobs: List of scored job data
        """
        await self.send_message(
            run_id,
            {
                "type": "jobs_scored",
                "count": len(jobs),
                "jobs": jobs[:20],  # Limit to top 20 for performance
            },
        )

    async def broadcast_resume_generated(
        self,
        run_id: str,
        job_id: str,
        resume_path: str,
    ):
        """
        Broadcast that a tailored resume has been generated.

        Args:
            run_id: Pipeline run ID
            job_id: Job ID
            resume_path: Path to generated resume
        """
        await self.send_message(
            run_id,
            {
                "type": "resume_generated",
                "job_id": job_id,
                "resume_path": resume_path,
            },
        )

    async def broadcast_application_submitted(
        self,
        run_id: str,
        job_id: str,
        application_id: str,
        method: str,
    ):
        """
        Broadcast that an application has been submitted.

        Args:
            run_id: Pipeline run ID
            job_id: Job ID
            application_id: Application tracking ID
            method: Submission method (auto_submit, manual, etc.)
        """
        await self.send_message(
            run_id,
            {
                "type": "application_submitted",
                "job_id": job_id,
                "application_id": application_id,
                "method": method,
            },
        )

    async def broadcast_pipeline_failed(
        self,
        run_id: str,
        error: str,
        stage: str = None,
    ):
        """
        Broadcast that the pipeline has failed.

        Args:
            run_id: Pipeline run ID
            error: Error message
            stage: Optional stage where failure occurred
        """
        await self.send_message(
            run_id,
            {
                "type": "pipeline_failed",
                "error": error,
                "stage": stage,
            },
        )

    async def broadcast_pipeline_complete(
        self,
        run_id: str,
        summary: Dict[str, Any],
    ):
        """
        Broadcast that the pipeline has completed successfully.

        Args:
            run_id: Pipeline run ID
            summary: Pipeline summary data
        """
        await self.send_message(
            run_id,
            {
                "type": "pipeline_complete",
                "summary": summary,
            },
        )

    def get_connection_count(self, run_id: str) -> int:
        """
        Get the number of active connections for a run.

        Args:
            run_id: Pipeline run ID

        Returns:
            Number of active connections
        """
        return len(self.active_connections.get(run_id, set()))


# Global connection manager instance
manager = ConnectionManager()
