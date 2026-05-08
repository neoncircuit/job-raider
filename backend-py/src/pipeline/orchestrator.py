"""
Job Raider - Pipeline Orchestrator

This module manages the complete job application pipeline,
orchestrating all stages from scraping to submission.

Author: Job Raider
Date: 2026-04-21
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
from enum import Enum

from .stages import PipelineStages, PipelineContext, StageResult
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..scrapers.storage import JobListingStorage
from ..utils.logger import get_logger, setup_logging, Components


class PipelineStage(str, Enum):
    """Pipeline stage identifiers."""
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


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    # Search parameters
    keywords: List[str]
    locations: List[str]
    sources: Optional[List[str]] = None

    # Pipeline behavior
    dry_run: bool = True
    skip_submission: bool = False

    # Scoring thresholds
    min_score: int = 60
    scam_threshold: float = 0.7

    # Selection
    max_jobs_to_present: int = 20

    # Storage
    data_dir: str = "data"
    results_dir: str = "data/results"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # Submission
    submission_delay: float = 2.0
    max_submissions_per_hour: int = 30


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    success: bool
    stages_completed: List[str]
    stage_results: Dict[str, StageResult]
    start_time: datetime
    end_time: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Get pipeline duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def jobs_scraped(self) -> int:
        """Get number of jobs scraped."""
        return self.stage_results.get("scrape", StageResult(
            stage_name="scrape", success=False, data=[], metadata={}, timestamp=datetime.now()
        )).metadata.get("listings_count", 0)

    @property
    def jobs_applied(self) -> int:
        """Get number of jobs applied to."""
        return self.stage_results.get("submit_applications", StageResult(
            stage_name="submit_applications", success=False, data=[], metadata={}, timestamp=datetime.now()
        )).metadata.get("total_applications", 0)


class PipelineOrchestrator:
    """
    Orchestrate the complete job application pipeline.

    Manages execution flow, error handling, and state persistence.
    """

    def __init__(
        self,
        config: PipelineConfig,
        user_profile: UserProfile,
    ):
        """
        Initialize the pipeline orchestrator.

        Args:
            config: Pipeline configuration
            user_profile: User profile for matching
        """
        self.config = config
        self.user_profile = user_profile
        self.logger = get_logger(Components.SCRAPERS)

        # Setup logging
        setup_logging(
            log_level=config.log_level,
            log_dir=Path(config.log_file).parent if config.log_file else None,
        )

        # Create directories
        self.data_dir = Path(config.data_dir)
        self.results_dir = Path(config.results_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Initialize context
        self.storage = JobListingStorage(str(self.data_dir / "listings"))
        self.context = PipelineContext(
            user_profile=user_profile,
            storage=self.storage,
            results_dir=self.results_dir,
            config={
                "dry_run": config.dry_run,
                "scam_threshold": config.scam_threshold,
                "submission_delay": config.submission_delay,
            },
        )

        # Initialize stages
        self.stages = PipelineStages(self.context)

        # Hooks for stage callbacks
        self._before_stage_hooks: Dict[PipelineStage, List[Callable]] = {}
        self._after_stage_hooks: Dict[PipelineStage, List[Callable]] = {}

    def register_before_hook(
        self,
        stage: PipelineStage,
        hook: Callable[[PipelineStage], None],
    ) -> None:
        """Register a callback to run before a stage."""
        if stage not in self._before_stage_hooks:
            self._before_stage_hooks[stage] = []
        self._before_stage_hooks[stage].append(hook)

    def register_after_hook(
        self,
        stage: PipelineStage,
        hook: Callable[[PipelineStage, StageResult], None],
    ) -> None:
        """Register a callback to run after a stage."""
        if stage not in self._after_stage_hooks:
            self._after_stage_hooks[stage] = []
        self._after_stage_hooks[stage].append(hook)

    def run(
        self,
        start_from: PipelineStage = PipelineStage.SCRAPE,
        stop_at: Optional[PipelineStage] = None,
    ) -> PipelineResult:
        """
        Run the complete pipeline.

        Args:
            start_from: Stage to start from (for resuming)
            stop_at: Optional stage to stop at (for testing)

        Returns:
            PipelineResult with execution summary
        """
        start_time = datetime.now()
        self.logger.info("="*60)
        self.logger.info("JOB RAIDER PIPELINE STARTED")
        self.logger.info("="*60)

        # Define stage sequence
        stage_sequence = [
            PipelineStage.SCRAPE,
            PipelineStage.DEDUPLICATE,
            PipelineStage.FILTER_SCAMS,
            PipelineStage.FILTER_PROFILE,
            PipelineStage.SCORE_RANK,
            PipelineStage.RAG_RANK,
            PipelineStage.DETECT_AUTO_SUBMIT,
            PipelineStage.LINKEDIN_AUTH,
            PipelineStage.PRESENT_SELECT,
            PipelineStage.GENERATE_RESUMES,
            PipelineStage.SUBMIT,
        ]

        # Filter to stages we want to run
        start_idx = stage_sequence.index(start_from)
        if stop_at:
            end_idx = stage_sequence.index(stop_at) + 1
            stages_to_run = stage_sequence[start_idx:end_idx]
        else:
            stages_to_run = stage_sequence[start_idx:]

        # Skip submission if configured
        if self.config.skip_submission and PipelineStage.SUBMIT in stages_to_run:
            self.logger.info("Skipping submission stage (skip_submission=True)")
            stages_to_run.remove(PipelineStage.SUBMIT)

        # Execute stages
        stage_results: Dict[str, StageResult] = {}
        stages_completed = []

        for stage in stages_to_run:
            # Run before hooks
            for hook in self._before_stage_hooks.get(stage, []):
                try:
                    hook(stage)
                except Exception as e:
                    self.logger.warning(f"Before hook failed for {stage}: {str(e)}")

            # Execute stage
            result = self._execute_stage(stage, stage_results)
            stage_results[stage.value] = result

            if result.success:
                stages_completed.append(stage.value)
                self.logger.info(f"Stage '{stage.value}' completed successfully")
            else:
                self.logger.error(f"Stage '{stage.value}' failed: {result.error_message}")
                # Stop on failure
                break

            # Run after hooks
            for hook in self._after_stage_hooks.get(stage, []):
                try:
                    hook(stage, result)
                except Exception as e:
                    self.logger.warning(f"After hook failed for {stage}: {str(e)}")

        end_time = datetime.now()

        # Save results
        self._save_pipeline_results(stage_results, start_time, end_time)

        self.logger.info("="*60)
        self.logger.info("JOB RAIDER PIPELINE COMPLETED")
        self.logger.info(f"Duration: {end_time - start_time}")
        self.logger.info(f"Stages completed: {len(stages_completed)}/{len(stages_to_run)}")
        self.logger.info("="*60)

        return PipelineResult(
            success=len(stages_completed) == len(stages_to_run),
            stages_completed=stages_completed,
            stage_results=stage_results,
            start_time=start_time,
            end_time=end_time,
        )

    def _execute_stage(
        self,
        stage: PipelineStage,
        previous_results: Dict[str, StageResult],
    ) -> StageResult:
        """Execute a single pipeline stage."""
        self.logger.info(f"\n--- Executing stage: {stage.value} ---")

        if stage == PipelineStage.SCRAPE:
            return self.stages.stage_scrape(
                keywords=self.config.keywords,
                locations=self.config.locations,
                sources=self.config.sources,
            )

        elif stage == PipelineStage.DEDUPLICATE:
            scrape_result = previous_results.get("scrape")
            listings = scrape_result.data if scrape_result else []
            return self.stages.stage_deduplicate(listings)

        elif stage == PipelineStage.FILTER_SCAMS:
            dedupe_result = previous_results.get("deduplicate")
            listings = dedupe_result.data if dedupe_result else []
            return self.stages.stage_filter_scams(listings)

        elif stage == PipelineStage.FILTER_PROFILE:
            scam_result = previous_results.get("filter_scams")
            listings = scam_result.data if scam_result else []
            return self.stages.stage_filter_by_profile(listings)

        elif stage == PipelineStage.SCORE_RANK:
            profile_result = previous_results.get("filter_by_profile")
            listings = profile_result.data if profile_result else []
            return self.stages.stage_score_and_rank(listings, self.config.min_score)

        elif stage == PipelineStage.RAG_RANK:
            score_result = previous_results.get("score_and_rank")
            scored_listings = score_result.data if score_result else []
            return self.stages.stage_rag_rank(scored_listings)

        elif stage == PipelineStage.DETECT_AUTO_SUBMIT:
            # Try RAG results first, fall back to heuristic results
            rag_result = previous_results.get("rag_rank")
            if rag_result and rag_result.success and rag_result.data:
                ranked_listings = rag_result.data
            else:
                score_result = previous_results.get("score_and_rank")
                ranked_listings = score_result.data if score_result else []
            return self.stages.stage_detect_auto_submit(ranked_listings)

        elif stage == PipelineStage.PRESENT_SELECT:
            # Try RAG results first, fall back to heuristic results
            rag_result = previous_results.get("rag_rank")
            if rag_result and rag_result.success and rag_result.data:
                scored_listings = rag_result.data
            else:
                score_result = previous_results.get("score_and_rank")
                scored_listings = score_result.data if score_result else []
            submit_result = previous_results.get("detect_auto_submit")
            submission_info = submit_result.data if submit_result else []
            return self.stages.stage_present_selection(
                scored_listings, submission_info, self.config.max_jobs_to_present
            )

        elif stage == PipelineStage.GENERATE_RESUMES:
            select_result = previous_results.get("present_selection")
            selected = select_result.data if select_result else []
            return self.stages.stage_generate_resumes(selected)

        elif stage == PipelineStage.SUBMIT:
            resume_result = previous_results.get("generate_resumes")
            resumes = resume_result.data if resume_result else []
            return self.stages.stage_submit_applications(resumes)

        else:
            return StageResult(
                stage_name=stage.value,
                success=False,
                data=None,
                metadata={},
                timestamp=datetime.now(),
                error_message=f"Unknown stage: {stage.value}",
            )

    def _save_pipeline_results(
        self,
        stage_results: Dict[str, StageResult],
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Save pipeline execution results to file."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"pipeline_run_{timestamp_str}.json"

        # Serialize results
        serialized = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "config": {
                "keywords": self.config.keywords,
                "locations": self.config.locations,
                "sources": self.config.sources,
                "dry_run": self.config.dry_run,
                "min_score": self.config.min_score,
            },
            "stages": {},
        }

        for stage_name, result in stage_results.items():
            serialized["stages"][stage_name] = {
                "success": result.success,
                "timestamp": result.timestamp.isoformat(),
                "metadata": result.metadata,
                "error_message": result.error_message,
            }

        with open(results_file, "w") as f:
            json.dump(serialized, f, indent=2, default=str)

        self.logger.info(f"Pipeline results saved to: {results_file}")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of pipeline state."""
        return {
            "config": {
                "keywords": self.config.keywords,
                "locations": self.config.locations,
                "dry_run": self.config.dry_run,
            },
            "context": {
                "raw_listings": len(self.context.raw_listings) if self.context.raw_listings else 0,
                "deduplicated_listings": len(self.context.deduplicated_listings) if self.context.deduplicated_listings else 0,
                "filtered_listings": len(self.context.filtered_listings) if self.context.filtered_listings else 0,
                "scored_listings": len(self.context.scored_listings) if self.context.scored_listings else 0,
                "selected_listings": len(self.context.selected_listings) if self.context.selected_listings else 0,
            },
            "storage": {
                "total_listings": self.storage.count_total(),
            },
        }
