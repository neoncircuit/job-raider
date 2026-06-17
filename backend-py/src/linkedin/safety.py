"""
Job Raider - Safety Controller

Enforces rate limits and human-like behavior patterns for
LinkedIn application submissions to avoid detection.

Author: Job Raider
Date: 2026-05-04
"""

import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..utils.logger import Components, get_logger


class SafetyConfig(BaseModel):
    """Configuration for application submission safety limits."""

    daily_application_limit: int = Field(
        default=20,
        description="Maximum applications per day",
    )
    hourly_application_limit: int = Field(
        default=5,
        description="Maximum applications per hour",
    )
    min_seconds_between_applications: float = Field(
        default=30.0,
        description="Minimum wait between applications in seconds",
    )
    max_seconds_between_applications: float = Field(
        default=120.0,
        description="Maximum wait between applications in seconds",
    )
    random_delay_range: tuple = Field(
        default=(5.0, 15.0),
        description="Additional random delay range in seconds",
    )
    take_breaks: bool = Field(
        default=True,
        description="Whether to take periodic breaks",
    )
    break_after_n_applications: int = Field(
        default=5,
        description="Number of applications before a break",
    )
    break_duration_minutes: float = Field(
        default=10.0,
        description="Break duration in minutes",
    )


class SafetyController:
    """
    Enforce rate limits and human-like behavior patterns.

    Tracks application timestamps to ensure daily/hourly limits are
    respected and adds random delays to mimic human behavior.
    """

    def __init__(self, config: Optional[SafetyConfig] = None) -> None:
        """
        Initialize the safety controller.

        Args:
            config: Safety configuration. Uses defaults if not provided.
        """
        self.config = config or SafetyConfig()
        self.logger = get_logger(Components.SUBMISSION)
        self._application_log: List[datetime] = []

    def can_apply(self) -> bool:
        """
        Check if another application is allowed right now.

        Returns:
            True if the application would not violate any rate limit.
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now - timedelta(hours=1)

        daily_count = sum(1 for t in self._application_log if t >= today_start)
        hourly_count = sum(1 for t in self._application_log if t >= hour_start)

        if daily_count >= self.config.daily_application_limit:
            self.logger.warning(
                f"Daily application limit reached ({daily_count}/{self.config.daily_application_limit})"
            )
            return False

        if hourly_count >= self.config.hourly_application_limit:
            self.logger.warning(
                f"Hourly application limit reached ({hourly_count}/{self.config.hourly_application_limit})"
            )
            return False

        if self._application_log:
            last_apply = self._application_log[-1]
            seconds_since_last = (now - last_apply).total_seconds()
            if seconds_since_last < self.config.min_seconds_between_applications:
                self.logger.info(
                    f"Too soon since last application ({seconds_since_last:.0f}s < "
                    f"{self.config.min_seconds_between_applications}s minimum)"
                )
                return False

        # Check if a break is needed
        if self.config.take_breaks and daily_count > 0:
            if daily_count % self.config.break_after_n_applications == 0:
                last_break = self._last_break_time()
                if (
                    last_break
                    and (now - last_break).total_seconds()
                    < self.config.break_duration_minutes * 60
                ):
                    self.logger.info(
                        "Break period active, waiting before next application"
                    )
                    return False

        return True

    def wait_if_needed(self) -> None:
        """
        Wait an appropriate amount of time between applications.

        Uses a random delay within the configured range to mimic
        human behavior patterns.
        """
        if not self._application_log:
            return

        now = datetime.now()
        last_apply = self._application_log[-1]
        seconds_since_last = (now - last_apply).total_seconds()

        # Calculate target wait time
        base_delay = random.uniform(
            self.config.min_seconds_between_applications,
            self.config.max_seconds_between_applications,
        )
        extra_delay = random.uniform(*self.config.random_delay_range)
        target_wait = base_delay + extra_delay

        remaining = target_wait - seconds_since_last
        if remaining > 0:
            self.logger.info(f"Waiting {remaining:.0f}s before next application")
            time.sleep(remaining)

        # Check if a break is needed
        if self.config.take_breaks and len(self._application_log) > 0:
            if len(self._application_log) % self.config.break_after_n_applications == 0:
                break_duration = self.config.break_duration_minutes * 60
                self.logger.info(
                    f"Taking a {self.config.break_duration_minutes:.0f} minute break "
                    f"after {self.config.break_after_n_applications} applications"
                )
                time.sleep(break_duration)

    def record_application(self) -> None:
        """
        Record that an application was just submitted.

        Updates the internal log with the current timestamp.
        """
        self._application_log.append(datetime.now())
        self.logger.debug(f"Application recorded (total: {len(self._application_log)})")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current application rate statistics.

        Returns:
            Dict with daily count, hourly count, and remaining capacity.
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now - timedelta(hours=1)

        daily_count = sum(1 for t in self._application_log if t >= today_start)
        hourly_count = sum(1 for t in self._application_log if t >= hour_start)

        return {
            "daily_count": daily_count,
            "daily_limit": self.config.daily_application_limit,
            "daily_remaining": self.config.daily_application_limit - daily_count,
            "hourly_count": hourly_count,
            "hourly_limit": self.config.hourly_application_limit,
            "hourly_remaining": self.config.hourly_application_limit - hourly_count,
            "total_submitted": len(self._application_log),
        }

    def _last_break_time(self) -> Optional[datetime]:
        """
        Calculate when the last break period started.

        Returns:
            Datetime of the last break, or None.
        """
        break_interval = self.config.break_after_n_applications
        if len(self._application_log) < break_interval:
            return None

        # The break would have started after the Nth application
        break_index = (len(self._application_log) // break_interval) * break_interval
        if break_index > 0 and break_index <= len(self._application_log):
            return self._application_log[break_index - 1]
        return None
