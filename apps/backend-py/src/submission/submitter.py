"""
Job Raider - Auto-Submit Handler

This module handles automated submission of job applications
to platforms that support "Easy Apply" type features.

Author: Job Raider
Date: 2026-04-21
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..models.job_listing import JobListing
from ..utils.logger import Components, get_logger
from .detector import SubmissionInfo


class SubmissionStatus(str, Enum):
    """Status of a submission."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SubmissionResult:
    """Result of a submission attempt."""

    job: JobListing
    status: SubmissionStatus
    success: bool
    timestamp: datetime
    error_message: Optional[str] = None
    submission_id: Optional[str] = None
    notes: str = ""


class AutoSubmitter:
    """
    Handle automated job applications.

    Supports auto-submit for platforms with "Easy Apply" features
    and tracks submission status.
    """

    def __init__(
        self,
        dry_run: bool = True,
        delay_between_submissions: float = 2.0,
        max_submissions_per_hour: int = 30,
    ):
        """
        Initialize the auto-submitter.

        Args:
            dry_run: If True, simulate submissions without actually applying
            delay_between_submissions: Delay in seconds between submissions
            max_submissions_per_hour: Rate limit for submissions
        """
        self.dry_run = dry_run
        self.delay = delay_between_submissions
        self.max_submissions_per_hour = max_submissions_per_hour
        self.logger = get_logger(Components.SCRAPERS)

        # Tracking
        self._submission_history: List[SubmissionResult] = []
        self._last_submission_time: Optional[datetime] = None

    def submit(
        self,
        info: SubmissionInfo,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> SubmissionResult:
        """
        Submit an application for a job.

        Args:
            info: Submission information
            user_profile: Optional user profile data for the application

        Returns:
            SubmissionResult with outcome
        """
        # Check rate limit
        if not self._check_rate_limit():
            return SubmissionResult(
                job=info.job,
                status=SubmissionStatus.FAILED,
                success=False,
                timestamp=datetime.now(),
                error_message="Rate limit exceeded",
            )

        # Check if auto-submit is possible
        if not info.can_auto_submit:
            return SubmissionResult(
                job=info.job,
                status=SubmissionStatus.SKIPPED,
                success=False,
                timestamp=datetime.now(),
                notes=f"Auto-submit not available. Method: {info.apply_method.value}",
            )

        # Simulate submission in dry run mode
        if self.dry_run:
            self.logger.info(
                f"[DRY RUN] Would submit to {info.job.title} at {info.job.company}"
            )
            return SubmissionResult(
                job=info.job,
                status=SubmissionStatus.SUBMITTED,
                success=True,
                timestamp=datetime.now(),
                submission_id=f"dry_run_{info.job.job_id}",
                notes="[DRY RUN] Submission simulated",
            )

        # Actual submission would go here
        # This is platform-specific and would require authentication
        # For now, we'll implement a placeholder

        try:
            result = self._perform_submission(info, user_profile)
            self._submission_history.append(result)
            return result

        except Exception as e:
            self.logger.error(f"Submission failed: {str(e)}")
            return SubmissionResult(
                job=info.job,
                status=SubmissionStatus.FAILED,
                success=False,
                timestamp=datetime.now(),
                error_message=str(e),
            )

        finally:
            self._last_submission_time = datetime.now()

    def _check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits.

        Returns:
            True if submission is allowed
        """
        now = datetime.now()

        # Check if we've hit the hourly limit
        one_hour_ago = now.timestamp() - 3600
        recent_submissions = [
            s
            for s in self._submission_history
            if s.timestamp.timestamp() > one_hour_ago
        ]

        if len(recent_submissions) >= self.max_submissions_per_hour:
            self.logger.warning(
                f"Rate limit reached: {len(recent_submissions)} submissions in last hour"
            )
            return False

        # Check delay between submissions
        if self._last_submission_time:
            elapsed = (now - self._last_submission_time).total_seconds()
            if elapsed < self.delay:
                self.logger.debug(
                    f"Rate limit: waiting {self.delay - elapsed:.1f} seconds"
                )
                time.sleep(self.delay - elapsed)

        return True

    def _perform_submission(
        self,
        info: SubmissionInfo,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> SubmissionResult:
        """
        Perform the actual submission.

        Args:
            info: Submission information
            user_profile: Optional user profile data

        Returns:
            SubmissionResult with outcome
        """
        # Platform-specific submission logic would go here
        # This is a placeholder implementation

        # For LinkedIn Easy Apply
        if info.job.source.value == "linkedin":
            return self._submit_linkedin(info, user_profile)

        # Default — no auto-submit for this source
        return SubmissionResult(
            job=info.job,
            status=SubmissionStatus.SKIPPED,
            success=False,
            timestamp=datetime.now(),
            notes=f"No auto-submit implemented for {info.job.source.value}",
        )

    def _submit_linkedin(
        self,
        info: SubmissionInfo,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> SubmissionResult:
        """
        Submit application via LinkedIn Easy Apply.

        Uses the LinkedIn session manager, form parser, answer engine,
        and form filler to automate the complete application flow.

        Args:
            info: Submission information for the job.
            user_profile: Optional user profile data as dict.

        Returns:
            SubmissionResult with success/failure status.
        """
        try:
            import os

            from ..linkedin.answer_engine import QuestionAnswerEngine
            from ..linkedin.form_filler import EasyApplyFormFiller
            from ..linkedin.safety import SafetyConfig, SafetyController
            from ..linkedin.session import LinkedInSession, LinkedInSessionConfig
            from ..models.user_profile import UserProfile

            email = os.getenv("LINKEDIN_EMAIL", "")
            password = os.getenv("LINKEDIN_PASSWORD", "")

            if not email or not password:
                return SubmissionResult(
                    job=info.job,
                    status=SubmissionStatus.SKIPPED,
                    success=False,
                    timestamp=datetime.now(),
                    notes="LinkedIn credentials not configured (LINKEDIN_EMAIL/LINKEDIN_PASSWORD)",
                )

            # Initialize or reuse session
            if not hasattr(self, "_linkedin_session") or self._linkedin_session is None:
                session_config = LinkedInSessionConfig(
                    email=email,
                    password=password,
                )
                self._linkedin_session = LinkedInSession(session_config)

            session = self._linkedin_session

            if not session.is_authenticated:
                if not session.start():
                    self._linkedin_session = None
                    return SubmissionResult(
                        job=info.job,
                        status=SubmissionStatus.FAILED,
                        success=False,
                        timestamp=datetime.now(),
                        error_message="LinkedIn authentication failed",
                        notes="Check LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env",
                    )

            # Verify session is still active
            if not session.verify_and_reconnect():
                self._linkedin_session = None
                return SubmissionResult(
                    job=info.job,
                    status=SubmissionStatus.FAILED,
                    success=False,
                    timestamp=datetime.now(),
                    error_message="LinkedIn session expired and re-login failed",
                )

            # Build answer engine with user profile
            profile = None
            if user_profile:
                profile = (
                    UserProfile(**user_profile)
                    if isinstance(user_profile, dict)
                    else user_profile
                )

            if not profile:
                return SubmissionResult(
                    job=info.job,
                    status=SubmissionStatus.SKIPPED,
                    success=False,
                    timestamp=datetime.now(),
                    notes="No user profile provided, cannot answer application questions",
                )

            answer_engine = QuestionAnswerEngine(
                user_profile=profile,
                llm_router=getattr(self, "_llm_router", None),
            )

            # Create safety controller
            safety_config = SafetyConfig()
            safety = SafetyController(safety_config)

            # Create form filler
            filler = EasyApplyFormFiller(
                session=session,
                answer_engine=answer_engine,
                safety_controller=safety,
            )

            # Execute application
            result = filler.apply_to_job(
                job_id=info.job.job_id,
                job_title=info.job.title,
                company=info.job.company,
            )

            return SubmissionResult(
                job=info.job,
                status=(
                    SubmissionStatus.SUBMITTED
                    if result.success
                    else SubmissionStatus.FAILED
                ),
                success=result.success,
                timestamp=datetime.now(),
                notes=(
                    f"Answered {result.questions_answered} questions, "
                    f"skipped {result.questions_skipped}, "
                    f"low confidence: {len(result.low_confidence_answers)}, "
                    f"steps: {result.steps_completed}"
                ),
                error_message=result.error_message,
            )

        except Exception as e:
            self.logger.error(f"LinkedIn submission error: {e}")
            return SubmissionResult(
                job=info.job,
                status=SubmissionStatus.FAILED,
                success=False,
                timestamp=datetime.now(),
                error_message=str(e),
            )

    def submit_batch(
        self,
        submission_info: List[SubmissionInfo],
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> List[SubmissionResult]:
        """
        Submit multiple applications in batch.

        Args:
            submission_info: List of submission information
            user_profile: Optional user profile data

        Returns:
            List of SubmissionResults
        """
        results = []

        for info in submission_info:
            result = self.submit(info, user_profile)
            results.append(result)

            # Log progress
            if result.success:
                self.logger.info(
                    f"Submitted: {result.job.title} at {result.job.company}"
                )
            elif result.status == SubmissionStatus.SKIPPED:
                self.logger.info(
                    f"Skipped: {result.job.title} at {result.job.company} - {result.notes}"
                )
            else:
                self.logger.error(
                    f"Failed: {result.job.title} at {result.job.company} - {result.error_message}"
                )

        return results

    def get_submission_stats(self) -> Dict[str, Any]:
        """
        Get statistics about submissions.

        Returns:
            Dictionary with submission statistics
        """
        total = len(self._submission_history)
        successful = sum(1 for s in self._submission_history if s.success)
        failed = sum(
            1
            for s in self._submission_history
            if not s.success and s.status != SubmissionStatus.SKIPPED
        )
        skipped = sum(
            1 for s in self._submission_history if s.status == SubmissionStatus.SKIPPED
        )

        return {
            "total_submissions": total,
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "success_rate": successful / total if total > 0 else 0,
            "dry_run": self.dry_run,
        }

    def save_submission_history(self, filepath: str) -> None:
        """
        Save submission history to file.

        Args:
            filepath: Path to save history
        """
        try:
            history_data = [
                {
                    "job_title": result.job.title,
                    "job_company": result.job.company,
                    "job_id": result.job.job_id,
                    "status": result.status.value,
                    "success": result.success,
                    "timestamp": result.timestamp.isoformat(),
                    "error_message": result.error_message,
                    "submission_id": result.submission_id,
                    "notes": result.notes,
                }
                for result in self._submission_history
            ]

            with open(filepath, "w") as f:
                json.dump(history_data, f, indent=2, default=str)

            self.logger.info(f"Saved submission history to {filepath}")

        except Exception as e:
            self.logger.error(f"Failed to save history: {str(e)}")

    def load_submission_history(self, filepath: str) -> None:
        """
        Load submission history from file.

        Args:
            filepath: Path to load history from
        """
        try:
            with open(filepath, "r") as f:
                history_data = json.load(f)

            self._submission_history = []

            for item in history_data:
                # Recreate job listing (simplified version)
                job = JobListing(
                    title=item.get("job_title", "Unknown"),
                    company=item.get("job_company", "Unknown"),
                    job_id=item.get("job_id", ""),
                    source="manual",  # Placeholder
                )

                result = SubmissionResult(
                    job=job,
                    status=SubmissionStatus(item.get("status", "pending")),
                    success=item.get("success", False),
                    timestamp=datetime.fromisoformat(
                        item.get("timestamp", datetime.now().isoformat())
                    ),
                    error_message=item.get("error_message"),
                    submission_id=item.get("submission_id"),
                    notes=item.get("notes", ""),
                )

                self._submission_history.append(result)

            self.logger.info(
                f"Loaded {len(self._submission_history)} submission records"
            )

        except Exception as e:
            self.logger.error(f"Failed to load history: {str(e)}")

    def reset_history(self) -> None:
        """Clear submission history."""
        self._submission_history = []
        self._last_submission_time = None
        self.logger.info("Submission history reset")


class ApplicationTracker:
    """
    Track job applications and outcomes.

    Maintains records of submitted applications, interview status,
    and offer outcomes.
    """

    def __init__(self, storage_dir: str = "data/applications"):
        """
        Initialize the application tracker.

        Args:
            storage_dir: Directory to store application data
        """
        from pathlib import Path

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(Components.SCRAPERS)

    def track_application(
        self,
        job: JobListing,
        submission_id: Optional[str] = None,
        generated_resume_path: Optional[str] = None,
        cover_letter_path: Optional[str] = None,
    ) -> str:
        """
        Create a new application tracking record.

        Args:
            job: Job listing that was applied to
            submission_id: Optional submission ID
            generated_resume_path: Path to generated resume
            cover_letter_path: Path to generated cover letter

        Returns:
            Application ID
        """
        import hashlib

        app_id = hashlib.md5(
            f"{job.job_id}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        application_data = {
            "application_id": app_id,
            "job_id": job.job_id,
            "job_title": job.title,
            "company": job.company,
            "submission_id": submission_id,
            "generated_resume_path": generated_resume_path,
            "cover_letter_path": cover_letter_path,
            "applied_at": datetime.now().isoformat(),
            "status": "applied",
            "interview_status": None,
            "offer_status": None,
            "notes": [],
        }

        # Save to file
        filepath = self.storage_dir / f"{app_id}.json"
        with open(filepath, "w") as f:
            json.dump(application_data, f, indent=2, default=str)

        self.logger.info(
            f"Tracked application: {app_id} for {job.title} at {job.company}"
        )

        return app_id

    def update_status(
        self,
        app_id: str,
        status: Optional[str] = None,
        interview_status: Optional[str] = None,
        offer_status: Optional[str] = None,
        note: Optional[str] = None,
    ) -> bool:
        """
        Update application status.

        Args:
            app_id: Application ID
            status: New status
            interview_status: Interview status
            offer_status: Offer status
            note: Additional note

        Returns:
            True if update successful
        """
        filepath = self.storage_dir / f"{app_id}.json"

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            if status:
                data["status"] = status
            if interview_status:
                data["interview_status"] = interview_status
            if offer_status:
                data["offer_status"] = offer_status
            if note:
                data["notes"].append(f"{datetime.now().isoformat()}: {note}")

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)

            return True

        except Exception as e:
            self.logger.error(f"Failed to update application {app_id}: {str(e)}")
            return False

    def get_application(self, app_id: str) -> Optional[Dict[str, Any]]:
        """
        Get application tracking data.

        Args:
            app_id: Application ID

        Returns:
            Application data or None if not found
        """
        filepath = self.storage_dir / f"{app_id}.json"

        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            self.logger.error(f"Failed to load application {app_id}: {str(e)}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get application statistics.

        Returns:
            Dictionary with application statistics
        """
        applications = []

        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    applications.append(data)
            except Exception:
                continue

        total = len(applications)

        status_counts = {}
        for app in applications:
            status = app.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        offer_count = sum(
            1 for app in applications if app.get("offer_status") == "received"
        )

        return {
            "total_applications": total,
            "by_status": status_counts,
            "offers_received": offer_count,
            "offer_rate": offer_count / total if total > 0 else 0,
        }
