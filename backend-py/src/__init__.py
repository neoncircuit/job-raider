"""
Job Raider - Source Module

Automated Job Application Pipeline

Author: Job Raider
Date: 2026-04-21
"""

__version__ = "0.1.0"

# Main pipeline components
from .pipeline.orchestrator import (
    PipelineOrchestrator,
    PipelineConfig,
    PipelineResult,
    PipelineStage,
)

from .pipeline.stages import (
    PipelineContext,
    StageResult,
)

# Data models
from .models.job_listing import (
    JobListing,
    JobListingCollection,
    JobSource,
    ExperienceLevel,
    JobType,
    WorkMode,
)

from .models.user_profile import (
    UserProfile,
    TargetJob,
    SkillCategory,
    ProficiencyLevel,
)

# Scrapers
from .scrapers.manager import ScraperManager

# Scoring
from .scoring.filter import JobFilter, QuickFilter
from .scoring.matcher import JobMatcher, SkillMatcher, MatchScore
from .scoring.scam_detector import JobScamDetector, ScamFilter

# Generation
from .generation.selector import ResumeSelector
from .generation.resume_writer import ResumeWriter
from .generation.formatter import ResumeFormatter
from .generation.validator import ResumeValidator

# Submission
from .submission.detector import AutoSubmitDetector, SubmissionInfo
from .submission.submitter import AutoSubmitter, ApplicationTracker

# Metrics
from .metrics.cost_tracker import (
    CostTracker,
    ModelProvider,
    TaskType,
    TokenUsage,
    PipelineCostSummary,
)

from .metrics.outcome_tracker import (
    OutcomeTracker,
    ApplicationStatus,
    InterviewStage,
    Outcome,
    ConversionMetrics,
)

from .metrics.mlflow_tracker import (
    MLflowTracker,
    ExperimentConfig,
    create_mlflow_tracker,
)

# Health checks
from .health.health_check import (
    HealthMonitor,
    HealthStatus,
    check_health,
)

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
