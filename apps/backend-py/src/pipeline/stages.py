"""
Job Raider - Pipeline Stages

This module defines individual pipeline stage functions that
orchestrate the job application workflow.

Author: Job Raider
Date: 2026-04-21

The stage methods live in mixin modules: ``stages_collect``,
``stages_rank``, and ``stages_generate``. This module keeps the class that
joins them, its constructor, and the methods that tests patch through
this module's names. It also re-exports ``StageResult`` and
``PipelineContext``, so existing imports do not change.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..generation.cover_letter_service import generate_cover_letter_sync
from ..generation.cover_letter_validator import (
    CoverLetterIssue,
    collect_hard_fail_issues,
)
from ..generation.formatter import ResumeFormatter
from ..generation.resume_writer import ResumeWriter
from ..generation.selector import ResumeSelector
from ..generation.validator import ResumeValidator
from ..llm.embedding_client import EmbeddingClient
from ..llm.router import create_router
from ..models.job_listing import JobListing
from ..rag.bm25_retriever import BM25Retriever
from ..rag.chunker import TextChunker
from ..rag.config import RAGConfig
from ..rag.cross_encoder import CrossEncoderReranker
from ..rag.ranker import RAGRanker
from ..rag.vector_store import ChromaStore
from ..scoring.filter import JobFilter, QuickFilter
from ..scoring.matcher import JobMatcher
from ..scoring.scam_detector import (
    DEFAULT_SCAM_THRESHOLD,
    JobScamDetector,
)
from ..scrapers.manager import ScraperManager
from ..submission.detector import AutoSubmitDetector
from ..submission.submitter import (
    ApplicationTracker,
    AutoSubmitter,
    SubmissionStatus,
)
from ..utils.logger import Components, get_logger
from .stage_base import PipelineContext, StageResult
from .stages_collect import CollectStages
from .stages_generate import GenerateStages
from .stages_rank import RankStages

__all__ = [
    "PipelineContext",
    "PipelineStages",
    "StageResult",
]


class PipelineStages(CollectStages, RankStages, GenerateStages):
    """
    Individual pipeline stage functions.

    Each stage is a pure function that transforms input data
    and returns a StageResult.
    """

    def __init__(self, context: PipelineContext):
        """
        Initialize pipeline stages.

        Args:
            context: Shared pipeline context
        """
        self.context = context
        self.logger = get_logger(Components.SCRAPERS)

        # Initialize components
        self.scraper_manager = ScraperManager()
        self.job_filter = JobFilter()
        self.quick_filter = QuickFilter()
        self.job_matcher = JobMatcher(
            fresh_grad_mode=self.context.config.get("fresh_grad_mode", False)
        )
        self.scam_detector = JobScamDetector(
            threshold=self.context.config.get("scam_threshold", DEFAULT_SCAM_THRESHOLD)
        )
        self.submit_detector = AutoSubmitDetector()
        llm_router = create_router(prefer_local=True)
        self.resume_selector = ResumeSelector(llm_router=llm_router)
        self.resume_writer = ResumeWriter(llm_router=llm_router)
        self.resume_validator = ResumeValidator()
        self.resume_formatter = ResumeFormatter()
        self.auto_submitter = AutoSubmitter(
            dry_run=self.context.config.get("dry_run", True),
            delay_between_submissions=self.context.config.get("submission_delay", 2.0),
            max_submissions_per_hour=self.context.config.get(
                "max_submissions_per_hour", 30
            ),
        )

        # Initialize RAG components (lazy, graceful degradation)
        self._rag_ranker: Optional[RAGRanker] = None
        self._init_rag_components()

    def _generate_cover_letter(
        self,
        job: JobListing,
        selection: Any,
    ) -> Dict[str, Any]:
        """
        Generate one cover letter through the shared cover-letter service.

        The service writes the letter, validates it, and rewrites it one time
        when validation finds hard-fail grounding issues. A letter that still
        has hard-fail issues after that rewrite is not saved; it is marked
        "needs_review" with the issue names.

        Args:
            job: Target job.
            selection: Selection output that the resume step already made for
                this job. The service reuses it instead of selecting again.

        Returns:
            Dict with ``status`` ("saved", "needs_review", or "error"),
            ``content``, ``validation`` (the response model, or None), and
            ``issues`` (hard-fail issue names, or the error text).
        """
        try:
            response = generate_cover_letter_sync(
                job, self.context.user_profile, selection=selection
            )
        except Exception as e:
            self.logger.error("Cover letter generation failed for %s: %s", job.title, e)
            return {
                "status": "error",
                "content": None,
                "validation": None,
                "issues": [str(e)],
                "provider_used": None,
            }

        known = {issue.value for issue in CoverLetterIssue}
        hard_fails = collect_hard_fail_issues(
            [
                CoverLetterIssue(issue)
                for issue in response.validation.issues
                if issue in known
            ]
        )
        content = response.cover_letter.get("content")
        provider_used = response.cover_letter.get("provider_used")
        if hard_fails:
            names = [issue.value for issue in hard_fails]
            self.logger.warning(
                "Cover letter for %s needs review, not saved: %s", job.title, names
            )
            return {
                "status": "needs_review",
                "content": content,
                "validation": response.validation,
                "issues": names,
                "provider_used": provider_used,
            }

        self.logger.info(
            "Cover letter generated for %s: quality=%d/100",
            job.title,
            response.validation.score,
        )
        return {
            "status": "saved",
            "content": content,
            "validation": response.validation,
            "issues": [],
            "provider_used": provider_used,
        }

    def stage_submit_applications(
        self,
        generated_resumes: List[Dict[str, Any]],
    ) -> StageResult:
        """
        Stage 9: Submit applications (auto-submit where possible).

        Args:
            generated_resumes: List of generated resume data

        Returns:
            StageResult with submission results
        """
        stage_name = "submit_applications"
        start_time = datetime.now()

        try:
            self.logger.info(f"Submitting {len(generated_resumes)} applications")

            # Get submission info for selected jobs
            info_map = {
                info.job.job_id: info for info in self.context.submission_info or []
            }

            # Prepare submissions
            submissions_to_make = []
            for resume_data in generated_resumes:
                job = resume_data["job"]
                info = info_map.get(job.job_id)

                if info and info.can_auto_submit:
                    submissions_to_make.append(info)
                else:
                    self.logger.info(
                        f"Manual application required: {job.title} at {job.company}"
                    )

            # Batch submit
            results = self.auto_submitter.submit_batch(submissions_to_make)
            dry_run = self.auto_submitter.dry_run

            # Track real applications only. Results cover auto-submit jobs
            # only, so pair each result with its resume by job_id, not by
            # position in the list.
            tracker = ApplicationTracker(str(self.context.results_dir / "applications"))
            resumes_by_job_id = {
                resume_data["job"].job_id: resume_data
                for resume_data in generated_resumes
            }

            for result in results:
                if not result.success:
                    continue
                if dry_run:
                    self.logger.info(
                        "[DRY RUN] Not recorded as applied: "
                        f"{result.job.title} at {result.job.company}"
                    )
                    continue

                resume_data = resumes_by_job_id.get(result.job.job_id, {})
                app_id = tracker.track_application(
                    job=result.job,
                    submission_id=result.submission_id,
                    generated_resume_path=resume_data.get("pdf_path"),
                    cover_letter_path=resume_data.get("cover_letter_path"),
                )
                self.logger.info(f"Application tracked: {app_id}")

            # Calculate statistics. Only real submissions count as applied.
            succeeded = sum(1 for r in results if r.success)
            failed = sum(1 for r in results if r.status == SubmissionStatus.FAILED)
            manual = len(generated_resumes) - len(submissions_to_make)
            applied = 0 if dry_run else succeeded
            simulated = succeeded if dry_run else 0

            metadata = {
                "total_applications": applied,
                "dry_run": dry_run,
                "resumes_generated": len(generated_resumes),
                "auto_submitted": len(results),
                "successful": applied,
                "simulated": simulated,
                "failed": failed,
                "manual_required": manual,
                "submission_stats": self.auto_submitter.get_submission_stats(),
            }

            self.logger.info(
                f"Submission complete: {applied} applied, {simulated} simulated, "
                f"{failed} failed, {manual} manual"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=results,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Submission stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def _init_rag_components(self) -> None:
        """Initialize RAG components with graceful degradation.

        Sets up EmbeddingClient, ChromaStore, TextChunker, and RAGRanker.
        If any component fails to initialize, self._rag_ranker stays None
        and the pipeline falls back to heuristic-only scoring.
        """
        try:
            rag_config = RAGConfig.from_yaml("config/rag_config.yaml")

            if not rag_config.re_ranking.enabled:
                self.logger.info("RAG re-ranking disabled in configuration")
                return

            embedding_client = EmbeddingClient(
                model=rag_config.embedding.model,
                batch_size=rag_config.embedding.batch_size,
                cache_enabled=rag_config.embedding.cache_enabled,
                cache_ttl=rag_config.embedding.cache_ttl,
            )

            if not embedding_client.is_model_available():
                self.logger.info(
                    "Embedding model '%s' not available, RAG disabled",
                    rag_config.embedding.model,
                )
                return

            vector_store = ChromaStore(rag_config.vector_store)
            vector_store.initialize()

            chunker = TextChunker(rag_config.chunking.get("job_description"))

            # BM25 retriever for hybrid search
            bm25_retriever = None
            if rag_config.bm25.enabled:
                try:
                    bm25_retriever = BM25Retriever()
                    self.logger.info("BM25 retriever initialized")
                except Exception as e:
                    self.logger.warning("BM25 initialization failed: %s", e)

            # Cross-encoder reranker (optional, off by default)
            cross_encoder = None
            if rag_config.cross_encoder.enabled:
                try:
                    cross_encoder = CrossEncoderReranker(
                        model_name=rag_config.cross_encoder.model_name,
                        enabled=True,
                        max_length=rag_config.cross_encoder.max_length,
                    )
                    if cross_encoder.is_available:
                        self.logger.info("Cross-encoder reranker initialized")
                    else:
                        self.logger.info(
                            "Cross-encoder unavailable, reranking disabled"
                        )
                        cross_encoder = None
                except Exception as e:
                    self.logger.warning("Cross-encoder initialization failed: %s", e)

            self._rag_ranker = RAGRanker(
                config=rag_config,
                embedding_client=embedding_client,
                vector_store=vector_store,
                chunker=chunker,
                bm25_retriever=bm25_retriever,
                cross_encoder=cross_encoder,
            )

            self.logger.info("RAG components initialized successfully")

        except Exception as e:
            self.logger.warning(
                "RAG initialization failed (heuristic-only mode): %s", e
            )
            self._rag_ranker = None
