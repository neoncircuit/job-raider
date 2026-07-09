"""
Job Raider - Experiments Module

This module provides A/B testing capability for comparing different
scoring heuristics, model configurations, and pipeline parameters.

Author: Job Raider
Date: 2026-04-21
"""

from .ab_testing import (
    ABTester,
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
    ScoringExperimentBuilder,
    get_preset_experiments,
    run_scoring_experiment,
)

__all__ = [
    "ExperimentStatus",
    "ExperimentConfig",
    "ExperimentResult",
    "ABTester",
    "ScoringExperimentBuilder",
    "get_preset_experiments",
    "run_scoring_experiment",
]
