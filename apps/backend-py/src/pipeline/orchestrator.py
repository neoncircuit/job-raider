"""
Job Raider - Pipeline Orchestrator

This module manages the complete job application pipeline,
orchestrating all stages from scraping to submission.

Enhanced with multi-agent coordination for intelligent
job matching and career coaching capabilities.

Author: Job Raider
Date: 2026-04-21
Updated: 2026-06-12 - Added multi-agent support
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ..llm.router import create_router
from ..models.pipeline_stage import STAGE_ORDER, PipelineStage
from ..models.user_profile import UserProfile
from ..scrapers.storage import JobListingStorage
from ..utils.logger import Components, get_logger, setup_logging
from .stages import PipelineContext, PipelineStages, StageResult

if TYPE_CHECKING:
    from ..llm.router import LLMRouter

# Multi-agent imports
try:
    from ..agents.career_coach import CareerCoachAgent
    from ..agents.coordinator import AgentCoordinator

    MULTI_AGENT_AVAILABLE = True
except ImportError:
    MULTI_AGENT_AVAILABLE = False
    AgentCoordinator = None  # type: ignore[assignment,misc]
    CareerCoachAgent = None  # type: ignore[assignment,misc]


__all__ = [
    "PipelineConfig",
    "PipelineOrchestrator",
    "PipelineResult",
    "PipelineStage",
    "STAGE_ORDER",
]


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
    # discover = stop after RAG_RANK; full = continue toward apply stages
    mode: str = "discover"

    # Scoring thresholds
    min_score: int = 60
    scam_threshold: float = 0.7
    fresh_grad_mode: bool = False

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

    # Multi-agent configuration
    enable_multi_agent: bool = False
    enable_career_coach: bool = True
    enable_parallel_execution: bool = True
    agent_timeout: float = 300.0  # 5 minutes


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
        return self.stage_results.get(
            "scrape",
            StageResult(
                stage_name="scrape",
                success=False,
                data=[],
                metadata={},
                timestamp=datetime.now(),
            ),
        ).metadata.get("listings_count", 0)

    @property
    def jobs_scored(self) -> int:
        """Get number of jobs kept after scoring (or RAG if present)."""
        rag = self.stage_results.get("rag_rank")
        if rag and rag.success:
            count = rag.metadata.get("output_count")
            if count is None:
                count = rag.metadata.get("input_count")
            if isinstance(count, int):
                return count
        return self.stage_results.get(
            "score_and_rank",
            StageResult(
                stage_name="score_and_rank",
                success=False,
                data=[],
                metadata={},
                timestamp=datetime.now(),
            ),
        ).metadata.get("scored_count", 0)

    @property
    def jobs_applied(self) -> int:
        """Get number of jobs applied to."""
        return self.stage_results.get(
            "submit_applications",
            StageResult(
                stage_name="submit_applications",
                success=False,
                data=[],
                metadata={},
                timestamp=datetime.now(),
            ),
        ).metadata.get("total_applications", 0)


class PipelineOrchestrator:
    """
    Orchestrate the complete job application pipeline.

    Manages execution flow, error handling, and state persistence.
    """

    def __init__(
        self,
        config: PipelineConfig,
        user_profile: UserProfile,
        llm_router: Optional[LLMRouter] = None,
    ):
        """
        Initialize the pipeline orchestrator.

        Args:
            config: Pipeline configuration
            user_profile: User profile for matching
            llm_router: Optional LLM router for agent operations
        """
        self.config = config
        self.user_profile = user_profile
        self.logger = get_logger(Components.SCRAPERS)
        self.llm_router = llm_router or create_router(prefer_local=True)

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
                "fresh_grad_mode": config.fresh_grad_mode,
                "submission_delay": config.submission_delay,
                "max_submissions_per_hour": config.max_submissions_per_hour,
            },
        )

        # Initialize stages
        self.stages = PipelineStages(self.context)

        # Hooks for stage callbacks
        self._before_stage_hooks: Dict[PipelineStage, List[Callable]] = {}
        self._after_stage_hooks: Dict[PipelineStage, List[Callable]] = {}

        # Multi-agent initialization
        self.agent_coordinator: Optional[AgentCoordinator] = None
        self._agents_initialized = False

        if config.enable_multi_agent and MULTI_AGENT_AVAILABLE:
            self._initialize_agents()

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

    def _initialize_agents(self) -> None:
        """Initialize multi-agent system for pipeline enhancement."""
        if not MULTI_AGENT_AVAILABLE or self._agents_initialized:
            return

        try:
            self.logger.info("Initializing multi-agent system...")

            # Create agent coordinator
            self.agent_coordinator = AgentCoordinator()

            # Initialize Career Coach Agent if enabled
            if self.config.enable_career_coach and CareerCoachAgent is not None:
                career_coach = CareerCoachAgent(llm_router=self.llm_router)
                self.agent_coordinator.register_agent(career_coach)
                self.logger.info("Career Coach Agent registered")

            # Start the coordinator
            asyncio.create_task(self.agent_coordinator.start())

            self._agents_initialized = True
            self.logger.info("Multi-agent system initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize multi-agent system: {e}")
            self.agent_coordinator = None
            self._agents_initialized = False

    async def run_with_agents(
        self,
        start_from: PipelineStage = PipelineStage.SCRAPE,
        stop_at: Optional[PipelineStage] = None,
    ) -> PipelineResult:
        """
        Run the pipeline using multi-agent coordination.

        Args:
            start_from: Stage to start from (for resuming)
            stop_at: Optional stage to stop at (for testing)

        Returns:
            PipelineResult with execution summary including agent performance
        """
        if not self._agents_initialized or not self.agent_coordinator:
            self.logger.warning(
                "Multi-agent system not available, falling back to standard execution"
            )
            # Fall back to synchronous execution
            return self.run(start_from, stop_at)

        start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("JOB RAIDER MULTI-AGENT PIPELINE STARTED")
        self.logger.info("=" * 60)

        stages_to_run = self.plan_stages(start_from, stop_at)

        # Execute stages with agents
        stage_results: Dict[str, StageResult] = {}
        stages_completed = []
        agent_tasks = []

        try:
            for stage in stages_to_run:
                # Run before hooks
                for hook in self._before_stage_hooks.get(stage, []):
                    try:
                        hook(stage)
                    except Exception as e:
                        self.logger.warning(f"Before hook failed for {stage}: {str(e)}")

                # Execute stage with agents
                result, agent_task = await self._execute_stage_with_agents(
                    stage, stage_results
                )
                stage_results[stage.value] = result

                if agent_task:
                    agent_tasks.append(agent_task)

                if result.success:
                    stages_completed.append(stage.value)
                    self.logger.info(f"Stage '{stage.value}' completed successfully")
                else:
                    self.logger.error(
                        f"Stage '{stage.value}' failed: {result.error_message}"
                    )
                    # Stop on failure
                    break

                # Run after hooks
                for hook in self._after_stage_hooks.get(stage, []):
                    try:
                        hook(stage, result)
                    except Exception as e:
                        self.logger.warning(f"After hook failed for {stage}: {str(e)}")

            # Get agent performance data
            agent_performance = {}
            if self.agent_coordinator:
                agent_performance = self.agent_coordinator.get_performance_metrics()

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            self.logger.info("=" * 60)
            self.logger.info("MULTI-AGENT PIPELINE COMPLETED")
            self.logger.info(f"Duration: {execution_time:.2f} seconds")
            self.logger.info(
                f"Stages completed: {len(stages_completed)}/{len(stages_to_run)}"
            )
            self.logger.info("=" * 60)

            return PipelineResult(
                success=len(stages_completed) == len(stages_to_run),
                stages_completed=stages_completed,
                stage_results=stage_results,
                start_time=start_time,
                end_time=end_time,
                metadata={
                    "execution_mode": "multi_agent",
                    "agent_performance": agent_performance,
                    "agent_tasks": agent_tasks,
                },
            )

        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {e}")
            end_time = datetime.now()

            return PipelineResult(
                success=False,
                stages_completed=stages_completed,
                stage_results=stage_results,
                start_time=start_time,
                end_time=end_time,
                metadata={"execution_mode": "multi_agent", "error": str(e)},
            )

    async def _execute_stage_with_agents(
        self, stage: PipelineStage, previous_results: Dict[str, StageResult]
    ) -> tuple[StageResult, Optional[Dict]]:
        """
        Execute a single stage using agent coordination.

        Args:
            stage: The stage to execute
            previous_results: Results from previous stages

        Returns:
            Tuple of (stage result, agent task info)
        """
        # For now, fall back to standard stage execution
        # This can be enhanced to use agents for specific stages
        result = self._execute_stage(stage, previous_results)
        return result, None

    def get_agent_status(self) -> Optional[Dict[str, Any]]:
        """
        Get status of registered agents.

        Returns:
            Agent status dictionary or None if agents not initialized
        """
        if not self._agents_initialized or not self.agent_coordinator:
            return None

        return self.agent_coordinator.get_system_status()

    def get_agent_performance(self) -> Optional[Dict[str, Any]]:
        """
        Get performance metrics for agents.

        Returns:
            Agent performance metrics or None if agents not initialized
        """
        if not self._agents_initialized or not self.agent_coordinator:
            return None

        return self.agent_coordinator.get_performance_metrics()

    def run(
        self,
        start_from: PipelineStage = PipelineStage.SCRAPE,
        stop_at: Optional[PipelineStage] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> PipelineResult:
        """
        Run the complete pipeline.

        Args:
            start_from: Stage to start from (for resuming)
            stop_at: Optional stage to stop at (for testing)
            should_stop: Optional check that runs before each stage. When it
                returns True, the run stops before that stage and the result
                is marked cancelled. A stage that is already running is not
                interrupted.

        Returns:
            PipelineResult with execution summary
        """
        start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("JOB RAIDER PIPELINE STARTED")
        self.logger.info("=" * 60)

        stages_to_run = self.plan_stages(start_from, stop_at)
        if self.config.skip_submission:
            self.logger.info("Skipping submission stage (skip_submission=True)")

        # Execute stages
        stage_results: Dict[str, StageResult] = {}
        stages_completed = []
        cancelled = False

        for stage in stages_to_run:
            if should_stop is not None and should_stop():
                cancelled = True
                self.logger.info(f"Run cancelled before stage '{stage.value}'")
                break

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
                self.logger.error(
                    f"Stage '{stage.value}' failed: {result.error_message}"
                )
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

        self.logger.info("=" * 60)
        self.logger.info("JOB RAIDER PIPELINE COMPLETED")
        self.logger.info(f"Duration: {end_time - start_time}")
        self.logger.info(
            f"Stages completed: {len(stages_completed)}/{len(stages_to_run)}"
        )
        self.logger.info("=" * 60)

        return PipelineResult(
            success=not cancelled and len(stages_completed) == len(stages_to_run),
            stages_completed=stages_completed,
            stage_results=stage_results,
            start_time=start_time,
            end_time=end_time,
            metadata={"cancelled": cancelled},
        )

    def plan_stages(
        self,
        start_from: PipelineStage = PipelineStage.SCRAPE,
        stop_at: Optional[PipelineStage] = None,
    ) -> List[PipelineStage]:
        """
        Select the stages for one run from ``STAGE_ORDER``.

        Args:
            start_from: First stage to run.
            stop_at: Last stage to run, or ``None`` to run to the end.

        Returns:
            Stages to run, in order. The submit stage is left out when
            ``skip_submission`` is set.
        """
        start_idx = STAGE_ORDER.index(start_from)
        end_idx = STAGE_ORDER.index(stop_at) + 1 if stop_at else len(STAGE_ORDER)
        stages_to_run = list(STAGE_ORDER[start_idx:end_idx])

        if self.config.skip_submission and PipelineStage.SUBMIT in stages_to_run:
            stages_to_run.remove(PipelineStage.SUBMIT)

        return stages_to_run

    def _stage_handlers(
        self,
        previous_results: Dict[str, StageResult],
    ) -> Dict[PipelineStage, Callable[[], StageResult]]:
        """
        Map every pipeline stage to a call that runs it.

        Each handler reads its input from the results of earlier stages. A
        test checks that every ``PipelineStage`` has a handler.

        Args:
            previous_results: Results of the stages that already ran, keyed
                by stage value.

        Returns:
            Handler for each stage.
        """

        def data_of(stage: PipelineStage) -> Any:
            """
            Read the output of an earlier stage.

            Args:
                stage: Earlier stage.

            Returns:
                The stage data, or an empty list when the stage did not run.
            """
            result = previous_results.get(stage.value)
            return result.data if result else []

        def ranked_listings() -> Any:
            """
            Read the ranked listings for detection and selection.

            Returns:
                RAG-ranked listings when RAG produced data, otherwise the
                heuristic scores.
            """
            rag_result = previous_results.get(PipelineStage.RAG_RANK.value)
            if rag_result and rag_result.success and rag_result.data:
                return rag_result.data
            return data_of(PipelineStage.SCORE_RANK)

        stages = self.stages
        return {
            PipelineStage.SCRAPE: lambda: stages.stage_scrape(
                keywords=self.config.keywords,
                locations=self.config.locations,
                sources=self.config.sources,
            ),
            PipelineStage.DEDUPLICATE: lambda: stages.stage_deduplicate(
                data_of(PipelineStage.SCRAPE)
            ),
            PipelineStage.FILTER_SCAMS: lambda: stages.stage_filter_scams(
                data_of(PipelineStage.DEDUPLICATE)
            ),
            PipelineStage.FILTER_PROFILE: lambda: stages.stage_filter_by_profile(
                data_of(PipelineStage.FILTER_SCAMS)
            ),
            PipelineStage.SCORE_RANK: lambda: stages.stage_score_and_rank(
                data_of(PipelineStage.FILTER_PROFILE), self.config.min_score
            ),
            PipelineStage.RAG_RANK: lambda: stages.stage_rag_rank(
                data_of(PipelineStage.SCORE_RANK)
            ),
            PipelineStage.DETECT_AUTO_SUBMIT: lambda: stages.stage_detect_auto_submit(
                ranked_listings()
            ),
            PipelineStage.LINKEDIN_AUTH: lambda: stages.stage_linkedin_auth(
                data_of(PipelineStage.DETECT_AUTO_SUBMIT)
            ),
            PipelineStage.PRESENT_SELECT: lambda: stages.stage_present_selection(
                ranked_listings(),
                data_of(PipelineStage.DETECT_AUTO_SUBMIT),
                self.config.max_jobs_to_present,
            ),
            PipelineStage.GENERATE_RESUMES: lambda: stages.stage_generate_resumes(
                data_of(PipelineStage.PRESENT_SELECT)
            ),
            PipelineStage.SUBMIT: lambda: stages.stage_submit_applications(
                data_of(PipelineStage.GENERATE_RESUMES)
            ),
        }

    def _execute_stage(
        self,
        stage: PipelineStage,
        previous_results: Dict[str, StageResult],
    ) -> StageResult:
        """
        Execute a single pipeline stage.

        Args:
            stage: Stage to run.
            previous_results: Results of the stages that already ran.

        Returns:
            The stage result.
        """
        self.logger.info(f"\n--- Executing stage: {stage.value} ---")
        return self._stage_handlers(previous_results)[stage]()

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
        serialized: Dict[str, Any] = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "config": {
                "keywords": self.config.keywords,
                "locations": self.config.locations,
                "sources": self.config.sources,
                "dry_run": self.config.dry_run,
                "min_score": self.config.min_score,
                "fresh_grad_mode": self.config.fresh_grad_mode,
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
                "raw_listings": (
                    len(self.context.raw_listings) if self.context.raw_listings else 0
                ),
                "deduplicated_listings": (
                    len(self.context.deduplicated_listings)
                    if self.context.deduplicated_listings
                    else 0
                ),
                "filtered_listings": (
                    len(self.context.filtered_listings)
                    if self.context.filtered_listings
                    else 0
                ),
                "scored_listings": (
                    len(self.context.scored_listings)
                    if self.context.scored_listings
                    else 0
                ),
                "selected_listings": (
                    len(self.context.selected_listings)
                    if self.context.selected_listings
                    else 0
                ),
            },
            "storage": {
                "total_listings": self.storage.get_statistics().get(
                    "total_listings", 0
                ),
            },
        }
