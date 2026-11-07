"""
Job Raider - Pipeline Stage Base

This module defines the stage result, the shared pipeline context, and the
base class that declares the state the stage mixins share.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..generation.formatter import ResumeFormatter
from ..generation.resume_writer import ResumeWriter
from ..generation.selector import ResumeSelector
from ..generation.validator import ResumeValidator
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..rag.ranker import RAGRanker
from ..scoring.filter import JobFilter
from ..scoring.matcher import JobMatcher, MatchScore
from ..scoring.scam_detector import JobScamDetector
from ..scrapers.manager import ScraperManager
from ..scrapers.storage import JobListingStorage
from ..submission.detector import AutoSubmitDetector, SubmissionInfo


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""

    stage_name: str
    success: bool
    data: Any
    metadata: Dict[str, Any]
    timestamp: datetime
    error_message: Optional[str] = None


@dataclass
class PipelineContext:
    """Context shared across pipeline stages."""

    user_profile: UserProfile
    storage: JobListingStorage
    results_dir: Path
    config: Dict[str, Any]

    # Optional intermediate results
    raw_listings: Optional[List[JobListing]] = None
    deduplicated_listings: Optional[List[JobListing]] = None
    filtered_listings: Optional[List[JobListing]] = None
    scored_listings: Optional[List[Tuple[JobListing, MatchScore]]] = None
    rag_ranked_listings: Optional[List[Any]] = (
        None  # List[RAGMatchScore] when RAG enabled
    )
    selected_listings: Optional[List[JobListing]] = None
    submission_info: Optional[List[SubmissionInfo]] = None


class StageBase:
    """
    State that the stage mixins share.

    ``PipelineStages.__init__`` sets each attribute. The mixins read them
    through ``self``, and these annotations give mypy their types.
    """

    context: PipelineContext
    logger: logging.Logger
    scraper_manager: ScraperManager
    job_filter: JobFilter
    job_matcher: JobMatcher
    scam_detector: JobScamDetector
    submit_detector: AutoSubmitDetector
    resume_selector: ResumeSelector
    resume_writer: ResumeWriter
    resume_validator: ResumeValidator
    resume_formatter: ResumeFormatter
    _rag_ranker: Optional[RAGRanker]

    def _generate_cover_letter(
        self,
        job: JobListing,
        selection: Any,
    ) -> Dict[str, Any]:
        """
        Generate one cover letter. ``PipelineStages`` implements this.

        Args:
            job: Target job.
            selection: Selection output that the resume step made for this job.

        Returns:
            Dict with ``status``, ``content``, ``validation``, and ``issues``.

        Raises:
            NotImplementedError: Always. The subclass gives the real method.
        """
        raise NotImplementedError
