"""
Job Raider - Logs API Routes

Read-only access to recent API log records held in memory, so the app can
show logs without ``docker logs``. Secret-like values are already redacted.
"""

from typing import Any, Dict, Literal

from fastapi import APIRouter, Query

from ...utils.log_buffer import get_log_buffer

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
async def get_logs(
    level: Literal["INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    component: str = Query("", max_length=200),
    q: str = Query("", max_length=200),
    after: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
) -> Dict[str, Any]:
    """
    Get recent log records, oldest first.

    Args:
        level: Lowest level to include.
        component: Logger-name prefix, for example ``job_raider.pipeline``.
        q: Case-insensitive text to find in the message or logger name.
        after: Only records newer than this sequence number (for polling).
        limit: Maximum records returned; the newest are kept.

    Returns:
        Dict with ``records``, ``latest_seq``, ``capacity``, and ``loggers``.
    """
    buffer = get_log_buffer()
    result = buffer.query(
        min_level=level, component=component, search=q, after=after, limit=limit
    )
    result["loggers"] = buffer.loggers()
    return result
