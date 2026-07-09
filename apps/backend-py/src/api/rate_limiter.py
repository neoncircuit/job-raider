"""
Simple Rate Limiter for API endpoints

Provides in-memory rate limiting for API endpoints to prevent abuse and DoS attacks.
"""

import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.

    Provides rate limiting based on client IP addresses or API keys.
    """

    def __init__(self):
        """Initialize the rate limiter."""
        # Store request timestamps per client
        self.requests: Dict[str, list] = defaultdict(list)
        self.limits: Dict[str, Dict[str, int]] = {}

        # Default rate limits (requests per time window)
        self.default_limits = {
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "burst_requests": 10,  # Maximum requests in 1 second burst
        }

        logger.info("Rate limiter initialized")

    def set_endpoint_limits(
        self,
        endpoint: str,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ):
        """
        Set rate limits for a specific endpoint.

        Args:
            endpoint: Endpoint path (e.g., "/api/agents/career-analysis")
            requests_per_minute: Maximum requests per minute
            requests_per_hour: Maximum requests per hour
        """
        self.limits[endpoint] = {
            "requests_per_minute": requests_per_minute,
            "requests_per_hour": requests_per_hour,
        }
        logger.info(
            f"Rate limits set for {endpoint}: {requests_per_minute}/min, {requests_per_hour}/hour"
        )

    def get_limits(self, endpoint: str) -> Dict[str, int]:
        """
        Get rate limits for an endpoint.

        Args:
            endpoint: Endpoint path

        Returns:
            Dictionary with rate limits
        """
        return self.limits.get(endpoint, self.default_limits)

    def _clean_old_requests(self, client_id: str, cutoff_time: float):
        """
        Remove requests older than the cutoff time.

        Args:
            client_id: Client identifier
            cutoff_time: Unix timestamp cutoff
        """
        if client_id in self.requests:
            self.requests[client_id] = [
                timestamp
                for timestamp in self.requests[client_id]
                if timestamp > cutoff_time
            ]

    def check_rate_limit(
        self, client_id: str, endpoint: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a request should be rate limited.

        Args:
            client_id: Client identifier (IP address or API key)
            endpoint: Endpoint path

        Returns:
            Tuple of (allowed, error_message)
        """
        current_time = time.time()
        limits = self.get_limits(endpoint)

        # Clean old requests
        minute_ago = current_time - 60
        hour_ago = current_time - 3600
        self._clean_old_requests(client_id, hour_ago)

        # Get recent requests
        recent_requests = self.requests.get(client_id, [])

        # Count requests in time windows
        requests_last_minute = sum(1 for ts in recent_requests if ts > minute_ago)
        requests_last_hour = len(recent_requests)

        # Check rate limits
        if requests_last_minute >= limits["requests_per_minute"]:
            logger.warning(
                f"Rate limit exceeded for {client_id} on {endpoint}: {requests_last_minute}/min"
            )
            return (
                False,
                f"Rate limit exceeded: {requests_last_minute} requests per minute",
            )

        if requests_last_hour >= limits["requests_per_hour"]:
            logger.warning(
                f"Rate limit exceeded for {client_id} on {endpoint}: {requests_last_hour}/hour"
            )
            return False, f"Rate limit exceeded: {requests_last_hour} requests per hour"

        # Add current request
        self.requests[client_id].append(current_time)

        return True, None

    def reset_client(self, client_id: str):
        """
        Reset rate limit tracking for a client.

        Args:
            client_id: Client identifier
        """
        if client_id in self.requests:
            del self.requests[client_id]
            logger.info(f"Rate limit reset for client {client_id}")


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter


def rate_limit(requests_per_minute: int = 60, requests_per_hour: int = 1000):
    """
    Decorator for rate limiting FastAPI endpoints.

    Args:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs
            request: Optional[Request] = kwargs.get("request")
            if not request:
                # Try to get request from args
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                logger.warning(
                    "Rate limiting: No request object found, skipping rate limit check"
                )
                return await func(*args, **kwargs)

            # Get client identifier
            client_id = request.client.host if request.client else "unknown"

            # Get endpoint path
            endpoint = request.url.path

            # Check rate limit
            limiter = get_rate_limiter()
            allowed, error_message = limiter.check_rate_limit(client_id, endpoint)

            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": error_message,
                        "retry_after": 60,  # Suggest retry after 1 minute
                    },
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def setup_agent_rate_limits(app):
    """
    Set up rate limits for agent API endpoints.

    Args:
        app: FastAPI application instance
    """
    limiter = get_rate_limiter()

    # Set stricter limits for agent endpoints (resource-intensive operations)
    agent_limits = {
        "/api/agents/career-analysis": {
            "requests_per_minute": 10,
            "requests_per_hour": 100,
        },
        "/api/agents/gap-analysis": {
            "requests_per_minute": 10,
            "requests_per_hour": 100,
        },
        "/api/agents/upskilling-roadmap": {
            "requests_per_minute": 10,
            "requests_per_hour": 100,
        },
        "/api/agents/career-goals": {
            "requests_per_minute": 10,
            "requests_per_hour": 100,
        },
        "/api/agents/skill-development-plan": {
            "requests_per_minute": 10,
            "requests_per_hour": 100,
        },
        "/api/agents/status": {"requests_per_minute": 60, "requests_per_hour": 1000},
        "/api/agents/performance": {
            "requests_per_minute": 30,
            "requests_per_hour": 500,
        },
        "/api/agents/recommendations": {
            "requests_per_minute": 30,
            "requests_per_hour": 500,
        },
        "/api/agents/health": {"requests_per_minute": 60, "requests_per_hour": 1000},
    }

    for endpoint, limits in agent_limits.items():
        limiter.set_endpoint_limits(
            endpoint,
            requests_per_minute=limits["requests_per_minute"],
            requests_per_hour=limits["requests_per_hour"],
        )

    logger.info("Agent endpoint rate limits configured")
