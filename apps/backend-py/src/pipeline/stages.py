"""
Job Raider - Pipeline Stages

This module defines individual pipeline stage functions that
orchestrate the job application workflow.

Author: Job Raider
Date: 2026-04-21
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..generation.cover_letter_validator import (
    CoverLetterValidator,
)
from ..generation.cover_letter_writer import CoverLetterWriter
from ..generation.formatter import ResumeFormatter
from ..generation.resume_writer import ResumeWriter
from ..generation.selector import ResumeSelector
from ..generation.validator import ResumeValidator
from ..llm.embedding_client import EmbeddingClient
from ..llm.router import LLMRouter
from ..models.job_listing import JobListing, JobListingCollection
from ..models.user_profile import UserProfile
from ..rag.bm25_retriever import BM25Retriever
from ..rag.chunker import TextChunker
from ..rag.config import RAGConfig
from ..rag.cross_encoder import CrossEncoderReranker
from ..rag.ranker import RAGMatchScore, RAGRanker
from ..rag.vector_store import ChromaStore
from ..scoring.filter import JobFilter, QuickFilter
from ..scoring.matcher import JobMatcher, MatchScore
from ..scoring.scam_detector import JobScamDetector, ScamFilter
from ..scrapers.manager import ScraperManager
from ..scrapers.storage import JobListingStorage
from ..submission.applied_tracker import AppliedJobsTracker
from ..submission.detector import ApplyMethod, AutoSubmitDetector, SubmissionInfo
from ..submission.submitter import ApplicationTracker, AutoSubmitter
from ..utils.logger import Components, get_logger


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


class PipelineStages:
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
        self.job_matcher = JobMatcher()
        self.scam_detector = JobScamDetector(
            threshold=self.context.config.get("scam_threshold", 0.7)
        )
        self.submit_detector = AutoSubmitDetector()
        llm_router = LLMRouter()
        self.resume_selector = ResumeSelector(llm_router=llm_router)
        self.resume_writer = ResumeWriter(llm_router=llm_router)
        self.cover_letter_writer = CoverLetterWriter(llm_router=llm_router)
        self.cover_letter_validator = CoverLetterValidator()
        self.resume_validator = ResumeValidator()
        self.resume_formatter = ResumeFormatter()
        self.auto_submitter = AutoSubmitter(
            dry_run=self.context.config.get("dry_run", True),
            delay_between_submissions=self.context.config.get("submission_delay", 2.0),
        )

        # Initialize RAG components (lazy, graceful degradation)
        self._rag_ranker: Optional[RAGRanker] = None
        self._init_rag_components()

    def stage_scrape(
        self,
        keywords: List[str],
        locations: List[str],
        sources: Optional[List[str]] = None,
    ) -> StageResult:
        """
        Stage 1: Scrape job listings from platforms.

        Args:
            keywords: Job keywords to search
            locations: Job locations
            sources: Optional list of sources (default: all)

        Returns:
            StageResult with scraped listings
        """
        stage_name = "scrape"
        start_time = datetime.now()

        try:
            self.logger.info(
                f"Starting scraping stage: keywords={keywords}, locations={locations}"
            )

            # Perform scraping
            listings = self.scraper_manager.search_all(
                keywords=keywords,
                locations=locations,
                sources=sources,
            )

            # Store raw results
            self.context.raw_listings = listings

            metadata = {
                "listings_count": len(listings),
                "keywords": keywords,
                "locations": locations,
                "sources": sources,
            }

            self.logger.info(f"Scraping complete: {len(listings)} listings found")

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=listings,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Scraping stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_deduplicate(
        self,
        listings: List[JobListing],
    ) -> StageResult:
        """
        Stage 2: Deduplicate listings across sources.

        Args:
            listings: Raw job listings

        Returns:
            StageResult with deduplicated listings
        """
        stage_name = "deduplicate"
        start_time = datetime.now()

        try:
            self.logger.info(f"Deduplicating {len(listings)} listings")

            # Use collection's deduplicate method
            collection = JobListingCollection(listings=listings)
            deduplicated_collection = collection.deduplicate()
            deduplicated = deduplicated_collection.listings

            # Store in context and persistent storage
            self.context.deduplicated_listings = deduplicated
            self.context.storage.save_listings(deduplicated)

            # Persist scraper-detected applied status to tracker
            applied_tracker = AppliedJobsTracker()
            for job in deduplicated:
                if job.already_applied and not applied_tracker.is_applied(job.job_id):
                    applied_tracker.mark_applied(
                        job_id=job.job_id,
                        job_title=job.title,
                        company=job.company,
                        source=(
                            str(job.source.value)
                            if hasattr(job.source, "value")
                            else str(job.source)
                        ),
                    )

            # Filter out already-applied jobs
            before_filter = len(deduplicated)
            deduplicated = [
                job
                for job in deduplicated
                if not job.already_applied
                and not applied_tracker.is_applied(job.job_id)
            ]
            applied_removed = before_filter - len(deduplicated)

            metadata = {
                "original_count": len(listings),
                "deduplicated_count": len(deduplicated),
                "removed_count": len(listings) - len(deduplicated),
                "already_applied_removed": applied_removed,
            }

            self.logger.info(
                f"Deduplication complete: {metadata['removed_count']} duplicates removed"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=deduplicated,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Deduplication stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=listings,
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_filter_scams(
        self,
        listings: List[JobListing],
        use_quick_filter: bool = True,
    ) -> StageResult:
        """
        Stage 3: Filter out scam listings.

        Args:
            listings: Job listings to filter
            use_quick_filter: Use quick pre-filter first

        Returns:
            StageResult with legitimate listings
        """
        stage_name = "filter_scams"
        start_time = datetime.now()

        try:
            self.logger.info(f"Filtering scams from {len(listings)} listings")

            if use_quick_filter:
                # Quick filter for obvious scams
                legitimate, scams = ScamFilter.filter_collection(listings)
                self.logger.info(f"Quick filter: {len(scams)} obvious scams removed")
                listings = legitimate

            # Detailed scam detection
            filtered = []
            scam_reports = []

            for job in listings:
                report = self.scam_detector.detect(job)
                if not report.is_scam:
                    filtered.append(job)
                else:
                    scam_reports.append((job, report))
                    self.logger.warning(
                        f"Filtered scam: {job.title} at {job.company} "
                        f"(confidence: {report.confidence:.2f})"
                    )

            metadata = {
                "original_count": len(listings),
                "filtered_count": len(filtered),
                "scam_count": len(scam_reports),
                "scam_reports": [
                    {
                        "title": job.title,
                        "company": job.company,
                        "confidence": report.confidence,
                        "indicators": [i.value for i in report.indicators],
                    }
                    for job, report in scam_reports[:10]  # First 10
                ],
            }

            self.logger.info(
                f"Scam filtering complete: {metadata['scam_count']} scams removed"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=filtered,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Scam filtering stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=listings,
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_filter_by_profile(
        self,
        listings: List[JobListing],
    ) -> StageResult:
        """
        Stage 4: Filter listings by user profile preferences.

        Args:
            listings: Job listings to filter

        Returns:
            StageResult with filtered listings
        """
        stage_name = "filter_by_profile"
        start_time = datetime.now()

        try:
            self.logger.info(f"Filtering {len(listings)} listings by user profile")

            # Filter by user profile
            collection = JobListingCollection(listings=listings)
            filtered_collection = self.job_filter.filter_by_profile(
                collection=collection,
                profile=self.context.user_profile,
            )
            filtered = filtered_collection.listings

            self.context.filtered_listings = filtered

            metadata = {
                "original_count": len(listings),
                "filtered_count": len(filtered),
                "removed_count": len(listings) - len(filtered),
                "target_keywords": self.context.user_profile.targets.keywords,
                "target_locations": self.context.user_profile.targets.locations,
            }

            self.logger.info(
                f"Profile filtering complete: {len(filtered)} listings match profile"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=filtered,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Profile filtering stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=listings,
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_score_and_rank(
        self,
        listings: List[JobListing],
        min_score: int = 60,
    ) -> StageResult:
        """
        Stage 5: Score and rank listings by relevance.

        Args:
            listings: Job listings to score
            min_score: Minimum score threshold (0-100)

        Returns:
            StageResult with scored and ranked listings
        """
        stage_name = "score_and_rank"
        start_time = datetime.now()

        try:
            self.logger.info(f"Scoring {len(listings)} listings")

            scored = []
            for job in listings:
                score = self.job_matcher.match_and_score(
                    job=job,
                    profile=self.context.user_profile,
                )
                if score.total_score >= min_score:
                    scored.append((job, score))

            # Sort by score (descending)
            scored.sort(key=lambda x: x[1].total_score, reverse=True)

            self.context.scored_listings = scored

            # Get score statistics
            scores = [s.total_score for _, s in scored]
            metadata = {
                "original_count": len(listings),
                "scored_count": len(scored),
                "below_threshold": len(listings) - len(scored),
                "min_score": min_score,
                "avg_score": sum(scores) / len(scores) if scores else 0,
                "max_score": max(scores) if scores else 0,
            }

            self.logger.info(
                f"Scoring complete: {len(scored)} listings above threshold "
                f"(avg: {metadata['avg_score']:.1f}, max: {metadata['max_score']})"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=scored,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Scoring stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_detect_auto_submit(
        self,
        scored_listings,
    ) -> StageResult:
        """
        Stage 6: Detect auto-submit opportunities.

        Accepts both heuristic (List[Tuple[JobListing, MatchScore]]) and
        RAG-ranked (List[RAGMatchScore]) listings.

        Args:
            scored_listings: Scored listings from Stage 5 or Stage 5.5

        Returns:
            StageResult with submission info
        """
        stage_name = "detect_auto_submit"
        start_time = datetime.now()

        try:
            jobs = self._extract_jobs_from_scored(scored_listings)
            self.logger.info(
                f"Detecting auto-submit opportunities for {len(jobs)} jobs"
            )

            # Detect submission methods
            submission_info = self.submit_detector.detect_batch(jobs)

            self.context.submission_info = submission_info

            # Count by method
            auto_submit_count = sum(
                1 for info in submission_info if info.can_auto_submit
            )

            metadata = {
                "total_jobs": len(submission_info),
                "auto_submit_available": auto_submit_count,
                "manual_only": len(submission_info) - auto_submit_count,
            }

            self.logger.info(
                f"Auto-submit detection: {auto_submit_count}/{len(jobs)} can be auto-submitted"
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=submission_info,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Auto-submit detection failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_linkedin_auth(
        self,
        submission_info: List[SubmissionInfo],
    ) -> StageResult:
        """
        Stage 7: Validate LinkedIn credentials and optionally pre-authenticate.

        If LinkedIn credentials are not configured, this stage succeeds but
        marks LinkedIn auto-submit as unavailable. This stage does not fail
        the pipeline -- it only gates LinkedIn Easy Apply functionality.

        Args:
            submission_info: Submission information from the detect stage.

        Returns:
            StageResult with LinkedIn auth status.
        """
        stage_name = "linkedin_auth"
        start_time = datetime.now()

        try:
            import os

            email = os.getenv("LINKEDIN_EMAIL", "")
            password = os.getenv("LINKEDIN_PASSWORD", "")

            linkedin_available = bool(email and password)
            easy_apply_count = sum(
                1
                for info in submission_info
                if info.apply_method == ApplyMethod.EASY_APPLY
            )

            if not linkedin_available:
                self.logger.info(
                    "LinkedIn credentials not configured. "
                    "Easy Apply auto-submit will be skipped. "
                    "Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env to enable."
                )
            else:
                self.logger.info(
                    f"LinkedIn credentials found. {easy_apply_count} Easy Apply jobs available."
                )

            metadata = {
                "linkedin_credentials_available": linkedin_available,
                "easy_apply_jobs_count": easy_apply_count,
            }

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=submission_info,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.warning(f"LinkedIn auth check failed: {e}")
            return StageResult(
                stage_name=stage_name,
                success=True,  # Non-fatal
                data=submission_info,
                metadata={"linkedin_credentials_available": False},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_present_selection(
        self,
        scored_listings,
        submission_info: List[SubmissionInfo],
        top_n: int = 20,
    ) -> StageResult:
        """
        Stage 7: Present ranked list for user selection.

        Accepts both heuristic and RAG-ranked listings.

        Args:
            scored_listings: Scored listings from Stage 5 or Stage 5.5
            submission_info: Submission information for each job
            top_n: Number of top jobs to present

        Returns:
            StageResult with user-selected listings
        """
        stage_name = "present_selection"
        start_time = datetime.now()

        try:
            # Create mapping
            info_map = {info.job.job_id: info for info in submission_info}

            # Present top N
            to_present = scored_listings[:top_n]

            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"TOP {len(to_present)} JOB OPPORTUNITIES")
            self.logger.info(f"{'='*60}\n")

            for idx, item in enumerate(to_present, 1):
                job = self._extract_job_from_item(item)
                score_display = self._format_score_display(item)
                info = info_map.get(job.job_id)
                auto_submit_flag = (
                    "[AUTO]" if info and info.can_auto_submit else "[MANUAL]"
                )

                self.logger.info(
                    f"{idx}. {auto_submit_flag} {job.title} at {job.company}"
                )
                self.logger.info(f"   {score_display}")
                self.logger.info(f"   Location: {job.location}")
                if job.salary_range:
                    self.logger.info(f"   Salary: {job.salary_range}")
                self.logger.info(f"   Source: {job.source.value}")
                if info and info.apply_method:
                    self.logger.info(f"   Apply: {info.apply_method.value}")
                self.logger.info("")

            # For now, select all top jobs (in real CLI, user would select)
            selected = [self._extract_job_from_item(item) for item in to_present]
            self.context.selected_listings = selected

            metadata = {
                "presented_count": len(to_present),
                "selected_count": len(selected),
                "auto_submit_available": sum(
                    1
                    for job in selected
                    if info_map.get(job.job_id) and info_map[job.job_id].can_auto_submit
                ),
            }

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=selected,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Selection stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

    def stage_generate_resumes(
        self,
        selected_listings: List[JobListing],
    ) -> StageResult:
        """
        Stage 8: Generate tailored resumes for selected jobs.

        Args:
            selected_listings: User-selected job listings

        Returns:
            StageResult with generated resumes
        """
        stage_name = "generate_resumes"
        start_time = datetime.now()

        try:
            self.logger.info(f"Generating resumes for {len(selected_listings)} jobs")

            generated = []
            validation_results = []

            for job in selected_listings:
                self.logger.info(f"Generating resume for {job.title} at {job.company}")

                try:
                    # Stage 1: Selection (small model)
                    selection_output = self.resume_selector.select(
                        job_description=job.description or "",
                        user_profile=self.context.user_profile,
                    )

                    # Stage 2: Write resume (large model)
                    generated_resume = self.resume_writer.write(
                        job=job,
                        user_profile=self.context.user_profile,
                        selection_output=selection_output,
                    )

                    # Stage 3: Validate
                    validation = self.resume_validator.validate(
                        generated_resume=generated_resume,
                        selection_output=selection_output,
                        user_profile=self.context.user_profile,
                    )

                    validation_results.append((job, validation))

                    if not validation.is_valid:
                        self.logger.warning(
                            f"Validation failed for {job.title}: {validation.issues}"
                        )
                        continue

                    # Stage 2b: Generate cover letter (large model)
                    cover_letter = self.cover_letter_writer.write(
                        job=job,
                        profile=self.context.user_profile,
                        selection=selection_output,
                    )

                    # Stage 3b: Validate cover letter
                    cl_validation = self.cover_letter_validator.validate(
                        cover_letter=cover_letter,
                        job=job,
                        profile=self.context.user_profile,
                        selection=selection_output,
                    )

                    if cl_validation.score < 60:
                        self.logger.warning(
                            "Cover letter quality low for %s: score=%d, issues=%s",
                            job.title,
                            cl_validation.score,
                            [i.value for i in cl_validation.issues],
                        )

                    self.logger.info(
                        "Cover letter generated for %s: %d words, quality=%d/100",
                        job.title,
                        cover_letter.word_count,
                        cl_validation.score,
                    )

                    # Stage 4: Format and save
                    resume_dir = self.context.results_dir / "resumes"
                    resume_dir.mkdir(parents=True, exist_ok=True)

                    pdf_path = self.resume_formatter.format_pdf(
                        resume=generated_resume,
                        output_path=resume_dir / f"{job.job_id}.pdf",
                    )

                    docx_path = self.resume_formatter.format_docx(
                        resume=generated_resume,
                        output_path=resume_dir / f"{job.job_id}.docx",
                    )

                    # Save cover letter to disk
                    cover_letter_dir = self.context.results_dir / "cover_letters"
                    cover_letter_dir.mkdir(parents=True, exist_ok=True)
                    cover_letter_path = cover_letter_dir / f"{job.job_id}.txt"
                    cover_letter_path.write_text(cover_letter.content)

                    generated.append(
                        {
                            "job": job,
                            "resume": generated_resume,
                            "cover_letter": cover_letter,
                            "pdf_path": str(pdf_path),
                            "docx_path": str(docx_path),
                            "cover_letter_path": str(cover_letter_path),
                            "validation": validation,
                            "cover_letter_validation": cl_validation,
                        }
                    )

                    self.logger.info(
                        f"Resume generated: {pdf_path} (validation: {validation.score}/100)"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Failed to generate resume for {job.title}: {str(e)}"
                    )
                    continue

            # Calculate validation statistics
            scores = [r["validation"].score for r in generated]
            metadata = {
                "attempted_count": len(selected_listings),
                "generated_count": len(generated),
                "validation_failed": len(selected_listings) - len(generated),
                "avg_validation_score": sum(scores) / len(scores) if scores else 0,
                "all_valid": all(r["validation"].is_valid for r in generated),
            }

            self.logger.info(
                f"Resume generation complete: {len(generated)}/{len(selected_listings)} successful"
            )

            return StageResult(
                stage_name=stage_name,
                success=len(generated) > 0,
                data=generated,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error(f"Resume generation stage failed: {str(e)}")
            return StageResult(
                stage_name=stage_name,
                success=False,
                data=[],
                metadata={},
                timestamp=start_time,
                error_message=str(e),
            )

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
            info_map = {info.job.job_id: info for info in self.context.submission_info}

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

            # Track applications
            tracker = ApplicationTracker(str(self.context.results_dir / "applications"))

            for i, result in enumerate(results):
                job = result.job
                resume_data = generated_resumes[i] if i < len(generated_resumes) else {}
                resume_path = resume_data.get("pdf_path")
                cover_letter_path = resume_data.get("cover_letter_path")

                if result.success:
                    app_id = tracker.track_application(
                        job=job,
                        submission_id=result.submission_id,
                        generated_resume_path=resume_path,
                        cover_letter_path=cover_letter_path,
                    )
                    self.logger.info(f"Application tracked: {app_id}")

            # Calculate statistics
            successful = sum(1 for r in results if r.success)
            failed = sum(1 for r in results if r.status.value == "failed")
            skipped = len(generated_resumes) - len(results)

            metadata = {
                "total_applications": len(generated_resumes),
                "auto_submitted": len(results),
                "successful": successful,
                "failed": failed,
                "manual_required": skipped,
                "submission_stats": self.auto_submitter.get_submission_stats(),
            }

            self.logger.info(
                f"Submission complete: {successful} successful, {failed} failed, {skipped} manual"
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

    def stage_rag_rank(
        self,
        scored_listings: List[Tuple[JobListing, MatchScore]],
    ) -> StageResult:
        """Stage 5.5: Re-rank scored listings using RAG semantic similarity.

        Takes jobs that passed heuristic threshold and re-ranks them
        using semantic similarity against the user profile embeddings.
        Gracefully degrades to heuristic-only when embedding model unavailable.

        Args:
            scored_listings: List of (job, heuristic_score) tuples from Stage 5.

        Returns:
            StageResult with RAGMatchScore list.
        """
        stage_name = "rag_rank"
        start_time = datetime.now()

        try:
            if not self._rag_ranker:
                self.logger.info(
                    "RAG ranker not available, passing through heuristic scores"
                )
                return StageResult(
                    stage_name=stage_name,
                    success=True,
                    data=scored_listings,
                    metadata={
                        "rag_enabled": False,
                        "passed_through": len(scored_listings),
                    },
                    timestamp=start_time,
                )

            self.logger.info("RAG re-ranking %d scored listings", len(scored_listings))

            rag_scores = self._rag_ranker.re_rank(
                scored_listings=scored_listings,
                profile=self.context.user_profile,
            )

            self.context.rag_ranked_listings = rag_scores

            # Compute stats
            semantic_scores = [s.semantic_score for s in rag_scores]
            combined_scores = [s.combined_score for s in rag_scores]

            metadata = {
                "rag_enabled": True,
                "input_count": len(scored_listings),
                "output_count": len(rag_scores),
                "avg_semantic": (
                    sum(semantic_scores) / len(semantic_scores)
                    if semantic_scores
                    else 0.0
                ),
                "avg_combined": (
                    sum(combined_scores) / len(combined_scores)
                    if combined_scores
                    else 0.0
                ),
            }

            self.logger.info(
                "RAG re-ranking complete: %d jobs ranked "
                "(avg semantic: %.3f, avg combined: %.3f)",
                len(rag_scores),
                metadata["avg_semantic"],
                metadata["avg_combined"],
            )

            return StageResult(
                stage_name=stage_name,
                success=True,
                data=rag_scores,
                metadata=metadata,
                timestamp=start_time,
            )

        except Exception as e:
            self.logger.error("RAG ranking stage failed: %s", e)
            # Graceful degradation: pass through heuristic results
            return StageResult(
                stage_name=stage_name,
                success=True,
                data=scored_listings,
                metadata={"rag_enabled": False, "error": str(e)},
                timestamp=start_time,
            )

    def _extract_jobs_from_scored(self, scored_listings: list) -> list:
        """Extract JobListing objects from either heuristic or RAG-ranked listings.

        Args:
            scored_listings: Either List[Tuple[JobListing, MatchScore]] or List[RAGMatchScore].

        Returns:
            List of JobListing objects.
        """
        jobs = []
        for item in scored_listings:
            if isinstance(item, tuple):
                jobs.append(item[0])
            elif isinstance(item, RAGMatchScore):
                jobs.append(item.job)
            elif hasattr(item, "job"):
                jobs.append(item.job)
            else:
                jobs.append(item)
        return jobs

    def _extract_job_from_item(self, item) -> JobListing:
        """Extract a single JobListing from a scored item.

        Args:
            item: Either a (JobListing, MatchScore) tuple or RAGMatchScore.

        Returns:
            JobListing object.
        """
        if isinstance(item, tuple):
            return item[0]
        elif isinstance(item, RAGMatchScore):
            return item.job
        elif hasattr(item, "job"):
            return item.job
        return item

    def _format_score_display(self, item) -> str:
        """Format score display for logging.

        Args:
            item: Either a (JobListing, MatchScore) tuple or RAGMatchScore.

        Returns:
            Formatted score string for display.
        """
        if isinstance(item, RAGMatchScore):
            return (
                f"Score: {item.heuristic_score}/100 "
                f"| Semantic: {item.semantic_score:.1%} "
                f"| Combined: {item.combined_score:.1%}"
            )
        elif isinstance(item, tuple):
            _, score = item
            return f"Score: {score.total_score}/100"
        return "Score: N/A"
