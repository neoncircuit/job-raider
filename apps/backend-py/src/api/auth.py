"""
Job Raider - API Key Authentication

FastAPI dependency that validates the X-API-Key header on every protected route.
The expected key is read from the ``API_KEY`` environment variable at startup.

Auth is skipped only when ``AUTH_DISABLED=1`` is set explicitly. An empty
``API_KEY`` without that flag rejects every request.
"""

from __future__ import annotations

import os
from logging import getLogger

from fastapi import Header, HTTPException, status

logger = getLogger(__name__)

_API_KEY = os.getenv("API_KEY", "")
_AUTH_DISABLED = os.getenv("AUTH_DISABLED", "").strip() in {"1", "true", "True", "yes"}
_warned_disabled = False

# Log auth state at startup
if _AUTH_DISABLED:
    logger.warning(
        "Authentication DISABLED - AUTH_DISABLED=1 is set (API_KEY is not checked)"
    )
elif _API_KEY:
    logger.info("Authentication ENABLED - API key is configured")
else:
    logger.error(
        "Authentication MISCONFIGURED - API_KEY is not set and AUTH_DISABLED is not 1"
    )


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    """
    Validate the X-API-Key request header against the server-side API_KEY env var.

    Bypass is allowed only when ``AUTH_DISABLED=1``. Otherwise an empty or
    mismatched key is rejected.

    Args:
        x_api_key: Value of the X-API-Key header supplied by the caller.

    Raises:
        HTTPException: 401 if the request is not authorized.
    """
    global _warned_disabled

    if _AUTH_DISABLED:
        if not _warned_disabled:
            logger.warning(
                "Authentication bypassed - AUTH_DISABLED=1 (API_KEY is not checked)"
            )
            _warned_disabled = True
        return

    if not _API_KEY:
        logger.warning("Authentication failed - API key not configured")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

    if x_api_key != _API_KEY:
        logger.warning("Authentication failed - Invalid API key from client")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

    logger.debug("Authentication successful")
