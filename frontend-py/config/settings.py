"""
Frontend configuration loaded from environment variables.

Provides centralized settings for the Streamlit dashboard including
backend API URL, polling intervals, timeouts, and display options.
"""

import os


class Settings:
    """Frontend configuration from environment variables.

    Attributes:
        BACKEND_API_URL: Base URL for the FastAPI backend.
        POLLING_INTERVAL_SEC: Seconds between pipeline status polls.
        REQUEST_TIMEOUT_SEC: Default HTTP request timeout in seconds.
        SEARCH_TIMEOUT_SEC: Timeout for job search requests (scraping is slow).
        PAGE_SIZE: Default number of items per page in listings.
        DEBUG: Enable debug logging and verbose error messages.
    """

    BACKEND_API_URL: str = os.environ.get("BACKEND_API_URL", "http://localhost:8000")
    POLLING_INTERVAL_SEC: int = int(os.environ.get("POLLING_INTERVAL_SEC", "2"))
    REQUEST_TIMEOUT_SEC: int = int(os.environ.get("REQUEST_TIMEOUT_SEC", "120"))
    SEARCH_TIMEOUT_SEC: int = int(os.environ.get("SEARCH_TIMEOUT_SEC", "120"))
    PAGE_SIZE: int = int(os.environ.get("PAGE_SIZE", "20"))
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
