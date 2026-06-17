"""
Job Raider - Pipeline Module

This module orchestrates the complete job application pipeline
from scraping to submission.

Author: Job Raider
Date: 2026-04-21
"""

from .orchestrator import (
    PipelineConfig,
    PipelineOrchestrator,
    PipelineResult,
    PipelineStage,
)
from .stages import PipelineContext, PipelineStages, StageResult

__all__ = [
    # Stages
    "PipelineStages",
    "PipelineContext",
    "StageResult",
    # Orchestrator
    "PipelineOrchestrator",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
]
