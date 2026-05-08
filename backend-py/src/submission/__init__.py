"""
Job Raider - Submission Module

This module handles automated job application submission
and application tracking.

Author: Job Raider
Date: 2026-04-21
"""

from .detector import (
    AutoSubmitDetector,
    SubmissionInfo,
    ApplyMethod,
    SubmissionAnalyzer,
)

from .submitter import (
    AutoSubmitter,
    SubmissionResult,
    SubmissionStatus,
    ApplicationTracker,
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
