"""
Job Raider - API Key Authentication

FastAPI dependency that validates the X-API-Key header on every protected route.
The expected key is read from the API_KEY environment variable at startup.

When API_KEY is empty or unset, auth is bypassed so local development without
a configured key still works.
"""

import os
from logging import getLogger

from fastapi import Header, HTTPException, status

logger = getLogger(__name__)
_API_KEY = os.getenv("API_KEY", "")

# Log auth state at startup
if _API_KEY:
    logger.info("🔒 Authentication ENABLED - API key is configured")
else:
    logger.warning(
        "🔓 Authentication DISABLED - Running in local dev mode (no API_KEY set)"
    )


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    """
    Validate the X-API-Key request header against the server-side API_KEY env var.

    Args:
        x_api_key: Value of the X-API-Key header supplied by the caller.

    Raises:
        HTTPException: 401 if API_KEY is configured and the header does not match.
    """
    if not _API_KEY:
        # Auth disabled — local dev mode.
        return
    if x_api_key != _API_KEY:
        logger.warning(f"🔒 Authentication failed - Invalid API key from client")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    logger.debug("🔒 Authentication successful")
