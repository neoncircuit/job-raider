"""
Job Raider - Source Module

Automated Job Application Pipeline

Author: Job Raider
Date: 2026-04-21
"""

__version__ = "0.1.0"

from .generation.formatter import ResumeFormatter
from .generation.resume_writer import ResumeWriter

# Generation
from .generation.selector import ResumeSelector
from .generation.validator import ResumeValidator

# Health checks
from .health.health_check import HealthMonitor, HealthStatus, check_health

# Metrics
from .metrics.cost_tracker import (
    CostTracker,
    ModelProvider,
    PipelineCostSummary,
    TaskType,
    TokenUsage,
)
from .metrics.mlflow_tracker import (
    ExperimentConfig,
    MLflowTracker,
    create_mlflow_tracker,
)
from .metrics.outcome_tracker import (
    ApplicationStatus,
    ConversionMetrics,
    InterviewStage,
    Outcome,
    OutcomeTracker,
)

# Data models
from .models.job_listing import (
    ExperienceLevel,
    JobListing,
    JobListingCollection,
    JobSource,
    JobType,
    WorkMode,
)
from .models.user_profile import ProficiencyLevel, SkillCategory, TargetJob, UserProfile

# Main pipeline components
from .pipeline.orchestrator import (
    PipelineConfig,
    PipelineOrchestrator,
    PipelineResult,
    PipelineStage,
)
from .pipeline.stages import PipelineContext, StageResult

# Scoring
from .scoring.filter import JobFilter, QuickFilter
from .scoring.matcher import JobMatcher, MatchScore, SkillMatcher
from .scoring.scam_detector import JobScamDetector, ScamFilter

# Scrapers
from .scrapers.manager import ScraperManager

# Submission
from .submission.detector import AutoSubmitDetector, SubmissionInfo
from .submission.submitter import ApplicationTracker, AutoSubmitter

__all__ = [
    # Pipeline
    "PipelineOrchestrator",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
    "PipelineContext",
    "StageResult",
    # Models
    "JobListing",
    "JobListingCollection",
    "JobSource",
    "ExperienceLevel",
    "JobType",
    "WorkMode",
    "UserProfile",
    "TargetJob",
    "SkillCategory",
    "ProficiencyLevel",
    # Scrapers
    "ScraperManager",
    # Scoring
    "JobFilter",
    "QuickFilter",
    "JobMatcher",
    "SkillMatcher",
    "MatchScore",
    "JobScamDetector",
    "ScamFilter",
    # Generation
    "ResumeSelector",
    "ResumeWriter",
    "ResumeFormatter",
    "ResumeValidator",
    # Submission
    "AutoSubmitDetector",
    "SubmissionInfo",
    "AutoSubmitter",
    "ApplicationTracker",
    # Metrics
    "CostTracker",
    "ModelProvider",
    "TaskType",
    "TokenUsage",
    "PipelineCostSummary",
    "OutcomeTracker",
    "ApplicationStatus",
    "InterviewStage",
    "Outcome",
    "ConversionMetrics",
    "MLflowTracker",
    "ExperimentConfig",
    "create_mlflow_tracker",
    # Health
    "HealthMonitor",
    "HealthStatus",
    "check_health",
]
