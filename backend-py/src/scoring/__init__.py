"""
Job Raider - Scoring Module

This module provides job filtering and relevance scoring functionality.

Author: Job Raider
Date: 2026-04-20
"""

from .filter import (
    JobFilter,
    QuickFilter,
    FilterResult,
    MatchReason,
)

from .matcher import (
    JobMatcher,
    SkillMatcher,
    MatchScore,
    ScoreCategory,
)

from .scam_detector import (
    JobScamDetector,
    ScamReport,
    ScamIndicator,
    ScamFilter,
)

__all__ = [
    # Filter
    "JobFilter",
    "QuickFilter",
    "FilterResult",
    "MatchReason",
    # Matcher
    "JobMatcher",
    "SkillMatcher",
    "MatchScore",
    "ScoreCategory",
    # Scam Detection
    "JobScamDetector",
    "ScamReport",
    "ScamIndicator",
    "ScamFilter",
]
