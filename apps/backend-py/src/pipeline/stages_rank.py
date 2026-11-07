"""
Job Raider - Rank and Select Stages

This module defines the stages that score and rank the jobs, detect the
apply method, and present the selection to the user.
"""

from datetime import datetime
from typing import List, Tuple

from ..models.job_listing import JobListing
from ..rag.ranker import RAGMatchScore
from ..scoring.matcher import MatchScore
from ..submission.applied_guard import AppliedGuard
from ..submission.detector import ApplyMethod, SubmissionInfo
from .stage_base import StageBase, StageResult


class RankStages(StageBase):
    """Stages that rank the jobs and present the selection."""

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
                score = self.job_matcher.score_job(
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
            jobs = AppliedGuard().annotate_listings(jobs)
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
                # ``JobListing`` stores enum values, so ``source`` is a string.
                source = (
                    job.source.value if hasattr(job.source, "value") else job.source
                )
                self.logger.info(f"   Source: {source}")
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
