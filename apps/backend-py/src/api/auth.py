"""
Job Raider - API Key Authentication

FastAPI dependency that validates the X-API-Key header on every protected route.
The expected key is read from the ``API_KEY`` environment variable at startup.

In development, an empty or unset ``API_KEY`` bypasses auth after logging a
one-time warning. In any other environment, an unset key is treated as a
configuration error and requests are rejected.
"""

import os
from logging import getLogger

from fastapi import Header, HTTPException, status

logger = getLogger(__name__)

_API_KEY = os.getenv("API_KEY", "")
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
_warned_missing = False

# Log auth state at startup
if _API_KEY:
    logger.info("Authentication ENABLED - API key is configured")
elif _ENVIRONMENT == "development":
    logger.warning(
        "Authentication DISABLED - Running in local dev mode (no API_KEY set)"
    )
else:
    logger.error(
        "Authentication MISCONFIGURED - API_KEY is not set in a non-development environment"
    )


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    """
    Validate the X-API-Key request header against the server-side API_KEY env var.

    The guard is fail-closed outside of development: if ``API_KEY`` is empty or
    unset and ``ENVIRONMENT`` is not ``development``, the request is rejected.

    Args:
        x_api_key: Value of the X-API-Key header supplied by the caller.

    Raises:
        HTTPException: 401 if the request is not authorized.
    """
    global _warned_missing

    if not _API_KEY:
        if _ENVIRONMENT == "development":
            if not _warned_missing:
                logger.warning(
                    "Authentication bypassed - API_KEY is not set in development environment"
                )
                _warned_missing = True
            return

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
