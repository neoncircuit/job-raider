"""
Job Raider - Job Classifiers

This module provides LLM-based classification services for job listings,
enriching them with detailed metadata for better filtering and matching.

Author: Job Raider
Date: 2026-04-29
"""

from .job_classifier import JobClassifier, JobClassificationResult

__all__ = ["JobClassifier", "JobClassificationResult"]
