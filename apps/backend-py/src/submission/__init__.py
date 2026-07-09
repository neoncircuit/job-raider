"""
Job Raider - Submission Module

This module handles automated job application submission
and application tracking.

Author: Job Raider
Date: 2026-04-21
"""

from .detector import (
    ApplyMethod,
    AutoSubmitDetector,
    SubmissionAnalyzer,
    SubmissionInfo,
)
from .submitter import (
    ApplicationTracker,
    AutoSubmitter,
    SubmissionResult,
    SubmissionStatus,
)

__all__ = [
    # Detector
    "AutoSubmitDetector",
    "SubmissionInfo",
    "ApplyMethod",
    "SubmissionAnalyzer",
    # Submitter
    "AutoSubmitter",
    "SubmissionResult",
    "SubmissionStatus",
    "ApplicationTracker",
]
