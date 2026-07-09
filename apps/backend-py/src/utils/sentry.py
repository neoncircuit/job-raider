"""
Job Raider - Sentry Error Tracking Integration

Initializes Sentry SDK for error tracking and performance monitoring
when configured in app_config.yaml or via environment variables.

Author: Job Raider
Date: 2026-04-27
"""

import logging
import os
from typing import Optional

from .logger import Components, get_logger

logger = get_logger(Components.SCRAPERS)

# Track whether Sentry was initialized
_sentry_initialized: bool = False


def init_sentry(config: Optional[dict] = None) -> bool:
    """
    Initialize Sentry SDK for error tracking and performance monitoring.

    Reads configuration from the provided config dict or falls back to
    environment variables. Does nothing if Sentry is disabled or DSN
    is not configured.

    Args:
        config: Optional dict with 'enabled', 'dsn', 'environment' keys.
                Typically from app_config.yaml monitoring.sentry section.

    Returns:
        True if Sentry was initialized successfully, False otherwise.
    """
    global _sentry_initialized

    if config is None:
        config = {}

    enabled = config.get("enabled", False)
    dsn = config.get("dsn") or os.getenv("SENTRY_DSN")
    environment = config.get("environment", "development")

    if not enabled or not dsn:
        logger.info(
            "Sentry not initialized (enabled=%s, dsn_configured=%s)",
            enabled,
            bool(dsn),
        )
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            integrations=[
                FastApiIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )

        _sentry_initialized = True
        logger.info("Sentry initialized (environment=%s)", environment)
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed, skipping initialization")
        return False
    except Exception as e:
        logger.error("Failed to initialize Sentry: %s", str(e))
        return False


def is_sentry_initialized() -> bool:
    """
    Check if Sentry has been initialized.

    Returns:
        True if Sentry SDK was initialized successfully.
    """
    return _sentry_initialized
