"""
Job Raider - Scoring Module

This module provides job filtering and relevance scoring functionality.

Author: Job Raider
Date: 2026-04-20
"""

from .filter import FilterResult, JobFilter, MatchReason, QuickFilter
from .matcher import JobMatcher, MatchScore, ScoreCategory, SkillMatcher
from .scam_detector import JobScamDetector, ScamFilter, ScamIndicator, ScamReport

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
