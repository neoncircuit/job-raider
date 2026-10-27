"""
Job Raider - Metrics Module

This module provides tracking and analytics for costs,
outcomes, and pipeline effectiveness.

Author: Job Raider
Date: 2026-04-21
"""

from .cost_tracker import (
    CallRecord,
    CostTracker,
    LLMApiCall,
    ModelCost,
    ModelPrice,
    ModelProvider,
    PipelineCostSummary,
    ProcessCostTracker,
    TaskType,
    TokenUsage,
    calculate_usage_cost,
    cost_run_scope,
    get_cost_tracker,
    get_model_price,
    list_cost_run_files,
    load_latest_cost_run,
    log_cost_run_to_mlflow,
    reset_cost_tracker,
    write_cost_run_summary,
)
from .mlflow_tracker import (
    ExperimentConfig,
    MLflowRunContext,
    MLflowTracker,
    create_mlflow_tracker,
)
from .outcome_tracker import (
    ApplicationOutcome,
    ApplicationStatus,
    ConversionMetrics,
    InterviewEvent,
    InterviewStage,
    OfferDetails,
    Outcome,
    OutcomeTracker,
)

__all__ = [
    # Cost Tracker
    "CostTracker",
    "CallRecord",
    "ProcessCostTracker",
    "get_cost_tracker",
    "reset_cost_tracker",
    "cost_run_scope",
    "write_cost_run_summary",
    "log_cost_run_to_mlflow",
    "list_cost_run_files",
    "load_latest_cost_run",
    "ModelProvider",
    "TaskType",
    "TokenUsage",
    "ModelCost",
    "ModelPrice",
    "get_model_price",
    "calculate_usage_cost",
    "LLMApiCall",
    "PipelineCostSummary",
    # Outcome Tracker
    "OutcomeTracker",
    "ApplicationStatus",
    "InterviewStage",
    "Outcome",
    "InterviewEvent",
    "OfferDetails",
    "ApplicationOutcome",
    "ConversionMetrics",
    # MLflow Tracker
    "MLflowTracker",
    "ExperimentConfig",
    "MLflowRunContext",
    "create_mlflow_tracker",
]
