"""
Job Raider - Auto-Submit Detector

This module detects "Easy Apply" and auto-submit opportunities
on job platforms.

Author: Job Raider
Date: 2026-04-21
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..models.job_listing import JobListing, JobSource
from ..utils.logger import Components, get_logger


class ApplyMethod(str, Enum):
    """Types of application methods."""

    EASY_APPLY = "easy_apply"
    EXTERNAL_SITE = "external_site"
    EMAIL = "email"
    MANUAL = "manual"
    ALREADY_APPLIED = "already_applied"


@dataclass
class SubmissionInfo:
    """Information about how to submit an application."""

    job: JobListing
    can_auto_submit: bool
    apply_method: ApplyMethod
    apply_url: Optional[str] = None
    external_url: Optional[str] = None
    requirements: List[str] = None
    estimated_time_minutes: int = 5


class AutoSubmitDetector:
    """
    Detect auto-submit opportunities on job platforms.

    Identifies "Easy Apply" type features and external application
    requirements.
    """

    # Platform-specific easy apply indicators
    PLATFORM_INDICATORS = {
        JobSource.LINKEDIN: {
            "easy_apply_classes": [
                "apply-button",
                "jobs-apply-button",
                "simplified-apply",
            ],
            "easy_apply_text": ["Easy Apply", "Apply now", "Quick apply"],
        },
        JobSource.JSEARCH: {
            "easy_apply_classes": ["apply-btn", "apply-link"],
            "easy_apply_text": ["Apply Now", "Quick Apply"],
        },
    }

    # External application indicators
    EXTERNAL_INDICATORS = [
        "external site",
        "company website",
        "redirect",
        "opens in new window",
    ]

    def __init__(self):
        """Initialize the auto-submit detector."""
        self.logger = get_logger(Components.SCRAPERS)

    def detect_submission_method(
        self,
        job: JobListing,
        html: Optional[str] = None,
    ) -> SubmissionInfo:
        """
        Detect how to submit an application for a job.

        Args:
            job: Job listing to analyze
            html: Optional HTML content for detailed analysis

        Returns:
            SubmissionInfo with submission details
        """
        # Skip jobs the user has already applied to
        if job.already_applied:
            return SubmissionInfo(
                job=job,
                can_auto_submit=False,
                apply_method=ApplyMethod.ALREADY_APPLIED,
                apply_url=str(job.source_url) if job.source_url else None,
                requirements=["Already applied"],
                estimated_time_minutes=0,
            )

        # Check source URL for clues
        if job.source_url:
            if self._is_external_application(str(job.source_url)):
                return SubmissionInfo(
                    job=job,
                    can_auto_submit=False,
                    apply_method=ApplyMethod.EXTERNAL_SITE,
                    apply_url=None,
                    external_url=str(job.source_url),
                    requirements=["Navigate to external site"],
                    estimated_time_minutes=10,
                )

        # Check platform-specific indicators
        platform = job.source
        if platform in self.PLATFORM_INDICATORS:
            return self._detect_platform_apply(job, html)
        else:
            return self._default_submission_info(job)

    def _is_external_application(self, url: str) -> bool:
        """
        Check if URL points to external application.

        Args:
            url: URL to check (string or stringable, e.g. pydantic HttpUrl).

        Returns:
            True if external application detected
        """
        url_lower = str(url).lower()

        # External domain indicators
        if "greenhouse.io" in url_lower or "lever.co" in url_lower:
            return True

        # Common external ATS indicators
        if "myworkdayjobs.com" in url_lower:
            return True

        return False

    def _detect_platform_apply(
        self,
        job: JobListing,
        html: Optional[str],
    ) -> SubmissionInfo:
        """
        Detect apply method for platform-specific jobs.

        Args:
            job: Job listing
            html: Optional HTML content

        Returns:
            SubmissionInfo with detected method
        """
        platform = job.source
        indicators = self.PLATFORM_INDICATORS.get(platform, {})

        if not html:
            # Default to manual without HTML
            return SubmissionInfo(
                job=job,
                can_auto_submit=False,
                apply_method=ApplyMethod.MANUAL,
                apply_url=str(job.source_url) if job.source_url else None,
                estimated_time_minutes=5,
            )

        # Check for easy apply indicators
        if self._has_easy_apply(html, indicators):
            return SubmissionInfo(
                job=job,
                can_auto_submit=True,
                apply_method=ApplyMethod.EASY_APPLY,
                apply_url=str(job.source_url) if job.source_url else None,
                requirements=["Click Easy Apply button"],
                estimated_time_minutes=2,
            )

        # Check for external application
        if self._has_external_indicators(html):
            return SubmissionInfo(
                job=job,
                can_auto_submit=False,
                apply_method=ApplyMethod.EXTERNAL_SITE,
                apply_url=None,
                external_url=self._extract_external_url(html),
                requirements=["Complete external application"],
                estimated_time_minutes=15,
            )

        # Default to manual
        return SubmissionInfo(
            job=job,
            can_auto_submit=False,
            apply_method=ApplyMethod.MANUAL,
            apply_url=str(job.source_url) if job.source_url else None,
            estimated_time_minutes=5,
        )

    def _has_easy_apply(self, html: str, indicators: Dict[str, List[str]]) -> bool:
        """Check if HTML contains easy apply indicators."""
        if not html:
            return False

        html_lower = html.lower()

        # Check classes
        for class_list in indicators.get("easy_apply_classes", []):
            for class_name in class_list:
                if class_name in html_lower:
                    return True

        # Check text
        for text_list in indicators.get("easy_apply_text", []):
            for text in text_list:
                if text in html_lower:
                    return True

        return False

    def _has_external_indicators(self, html: str) -> bool:
        """Check if HTML contains external application indicators."""
        if not html:
            return False

        html_lower = html.lower()

        for indicator in self.EXTERNAL_INDICATORS:
            if indicator in html_lower:
                return True

        return False

    def _extract_external_url(self, html: str) -> Optional[str]:
        """Extract external application URL from HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Look for external application links
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href and "http" in href:
                return href

        return None

    def _default_submission_info(self, job: JobListing) -> SubmissionInfo:
        """Return default submission info when no HTML available."""
        return SubmissionInfo(
            job=job,
            can_auto_submit=False,
            apply_method=ApplyMethod.MANUAL,
            apply_url=str(job.source_url) if job.source_url else None,
            requirements=["Visit job posting", "Submit application"],
            estimated_time_minutes=5,
        )

    def detect_batch(
        self,
        jobs: List[JobListing],
        htmls: Optional[Dict[str, str]] = None,
    ) -> List[SubmissionInfo]:
        """
        Detect submission methods for multiple jobs.

        Args:
            jobs: List of job listings
            htmls: Optional dict mapping job_id to HTML content

        Returns:
            List of SubmissionInfo objects
        """
        results = []

        for job in jobs:
            html = htmls.get(job.job_id) if htmls else None
            info = self.detect_submission_method(job, html)
            results.append(info)

        # Log summary
        auto_submit_count = sum(1 for r in results if r.can_auto_submit)
        self.logger.info(
            f"Submission detection: {auto_submit_count}/{len(jobs)} can be auto-submitted"
        )

        return results

    def get_auto_submit_jobs(
        self,
        jobs: List[JobListing],
        htmls: Optional[Dict[str, str]] = None,
    ) -> List[SubmissionInfo]:
        """
        Get only jobs that can be auto-submitted.

        Args:
            jobs: List of job listings
            htmls: Optional dict mapping job_id to HTML content

        Returns:
            List of SubmissionInfo for auto-submit jobs
        """
        all_info = self.detect_batch(jobs, htmls)
        return [info for info in all_info if info.can_auto_submit]

    def get_manual_apply_jobs(
        self,
        jobs: List[JobListing],
        htmls: Optional[Dict[str, str]] = None,
    ) -> List[SubmissionInfo]:
        """
        Get jobs that require manual application.

        Args:
            jobs: List of job listings
            htmls: Optional dict mapping job_id to HTML content

        Returns:
            List of SubmissionInfo for manual jobs
        """
        all_info = self.detect_batch(jobs, htmls)
        manual = [info for info in all_info if not info.can_auto_submit]

        # Group by submission type
        self.logger.info(f"Manual applications: {len(manual)} total")
        for method in ApplyMethod:
            count = sum(1 for m in manual if m.apply_method == method)
            if count > 0:
                self.logger.info(f"  {method.value}: {count}")

        return manual


class SubmissionAnalyzer:
    """
    Analyze submission patterns and statistics.

    Provides insights into submission success rates, time estimates,
    and automation opportunities.
    """

    def __init__(self):
        """Initialize the submission analyzer."""
        self.logger = get_logger(Components.SCRAPERS)

    def analyze_time_requirements(
        self,
        submission_info: List[SubmissionInfo],
    ) -> Dict[str, Any]:
        """
        Analyze time requirements for submissions.

        Args:
            submission_info: List of submission information

        Returns:
            Dictionary with time analysis
        """
        auto_submit_time = sum(
            info.estimated_time_minutes
            for info in submission_info
            if info.can_auto_submit
        )
        manual_submit_time = sum(
            info.estimated_time_minutes
            for info in submission_info
            if not info.can_auto_submit
        )

        total_time = auto_submit_time + manual_submit_time

        return {
            "auto_submit_count": sum(1 for s in submission_info if s.can_auto_submit),
            "manual_submit_count": sum(
                1 for s in submission_info if not s.can_auto_submit
            ),
            "auto_submit_time_minutes": auto_submit_time,
            "manual_submit_time_minutes": manual_submit_time,
            "total_time_minutes": total_time,
            "time_saved_by_auto_submit": manual_submit_time,
            "automation_percentage": (
                auto_submit_time / total_time * 100 if total_time > 0 else 0
            ),
        }

    def estimate_completion_time(
        self,
        submission_info: List[SubmissionInfo],
        parallel: bool = True,
        concurrent_limit: int = 3,
    ) -> Dict[str, Any]:
        """
        Estimate time to complete all submissions.

        Args:
            submission_info: List of submission information
            parallel: Whether to process in parallel
            concurrent_limit: Max concurrent submissions for parallel

        Returns:
            Dictionary with time estimates
        """
        if not parallel:
            total_minutes = sum(info.estimated_time_minutes for info in submission_info)
            return {
                "total_jobs": len(submission_info),
                "sequential_time_minutes": total_minutes,
                "parallel_time_minutes": total_minutes,
                "hours": total_minutes / 60,
            }

        # Parallel estimation
        auto_jobs = [s for s in submission_info if s.can_auto_submit]
        manual_jobs = [s for s in submission_info if not s.can_auto_submit]

        # Auto-submit can be done in parallel
        auto_time = (
            max((s.estimated_time_minutes for s in auto_jobs), default=0)
            if auto_jobs
            else 0
        )

        # Manual jobs need sequential processing (with some parallelization)
        manual_time = sum(s.estimated_time_minutes for s in manual_jobs)

        total_time = auto_time + manual_time

        return {
            "total_jobs": len(submission_info),
            "auto_submit_jobs": len(auto_jobs),
            "manual_jobs": len(manual_jobs),
            "auto_submit_time_minutes": auto_time,
            "manual_time_minutes": manual_time,
            "total_time_minutes": total_time,
            "hours": total_time / 60,
            "concurrent_limit": concurrent_limit,
        }
