"""
Job Raider - Pipeline Stage Identifiers

The single source of truth for pipeline stage names and their order. The
orchestrator, the API request models, and the tests all read the order from
here, so a stage cannot exist in one list and be missing from another.

This module has no heavy imports, so API models can use it without loading
the orchestrator.
"""

from enum import Enum
from typing import Tuple


class PipelineStage(str, Enum):
    """Pipeline stage identifiers, in execution order.

    The definition order of the members is the order in which the pipeline
    runs the stages. ``STAGE_ORDER`` is built from it.
    """

    SCRAPE = "scrape"
    DEDUPLICATE = "deduplicate"
    FILTER_SCAMS = "filter_scams"
    FILTER_PROFILE = "filter_by_profile"
    SCORE_RANK = "score_and_rank"
    RAG_RANK = "rag_rank"
    DETECT_AUTO_SUBMIT = "detect_auto_submit"
    LINKEDIN_AUTH = "linkedin_auth"
    PRESENT_SELECT = "present_selection"
    GENERATE_RESUMES = "generate_resumes"
    SUBMIT = "submit_applications"


STAGE_ORDER: Tuple[PipelineStage, ...] = tuple(PipelineStage)
"""All stages in execution order."""

DISCOVER_LAST_STAGE: PipelineStage = PipelineStage.RAG_RANK
"""Discover mode stops after this stage; full mode continues to submission."""
