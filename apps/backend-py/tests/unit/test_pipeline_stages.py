"""
Regression tests for PipelineStages.

Exercises stage_scrape, stage_deduplicate, stage_score_and_rank, and
stage_generate_resumes end to end with mocked collaborators. These stages
had no prior test coverage and, before this fix, called methods with
signatures that did not match their real implementations (e.g.
ScraperManager.search_all, ResumeSelector.select, ResumeWriter.write,
ResumeValidator.validate, ResumeFormatter) -- bugs that mypy caught but
that a real pipeline run (main.py CLI or POST /api/pipeline/run with
dry_run=False) would only have discovered by crashing.

Author: Job Raider
Date: 2026-07-23
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.generation.cover_letter_validator import CoverLetterValidationResult
from src.generation.cover_letter_writer import GeneratedCoverLetter
from src.generation.formatter import FormattedResume
from src.generation.resume_writer import GeneratedResume
from src.generation.selector import SelectionOutput
from src.generation.validator import ValidationResult
from src.models.job_listing import JobListingCollection, JobSource
from src.pipeline.stages import PipelineContext, PipelineStages
from src.scrapers.base import SearchParams
from src.scrapers.storage import JobListingStorage


@pytest.fixture
def stages(sample_user_profile, temp_data_dir: Path) -> PipelineStages:
    """A PipelineStages instance backed by a temp storage/results dir."""
    context = PipelineContext(
        user_profile=sample_user_profile,
        storage=JobListingStorage(storage_dir=str(temp_data_dir / "listings")),
        results_dir=temp_data_dir / "results",
        config={"dry_run": True},
    )
    return PipelineStages(context)


class TestStageScrape:
    """stage_scrape must call ScraperManager.search_all with a SearchParams."""

    def test_calls_search_all_with_search_params(
        self, stages: PipelineStages, sample_job_listing
    ):
        collection = JobListingCollection(
            listings=[sample_job_listing], source=JobSource.LINKEDIN
        )
        stages.scraper_manager.search_all = MagicMock(return_value=collection)

        result = stages.stage_scrape(
            keywords=["python"],
            locations=["Remote"],
            sources=["linkedin"],
        )

        assert result.success
        assert result.data == [sample_job_listing]

        call_args = stages.scraper_manager.search_all.call_args
        params = call_args.args[0]
        assert isinstance(params, SearchParams)
        assert params.keywords == ["python"]
        assert params.location == "Remote"
        assert call_args.kwargs["sources"] == [JobSource.LINKEDIN]


class TestStageDeduplicate:
    """stage_deduplicate must persist via the real JobListingStorage API."""

    def test_saves_via_save_collection(
        self, stages: PipelineStages, sample_job_listing
    ):
        stages.context.storage.save_collection = MagicMock(return_value="path.json")

        result = stages.stage_deduplicate([sample_job_listing])

        assert result.success
        stages.context.storage.save_collection.assert_called_once()
        saved = stages.context.storage.save_collection.call_args.args[0]
        assert isinstance(saved, JobListingCollection)


class TestStageScoreAndRank:
    """stage_score_and_rank must call JobMatcher.score_job (not match_and_score)."""

    def test_scores_via_score_job(self, stages: PipelineStages, sample_job_listing):
        fake_score = MagicMock(total_score=75)
        stages.job_matcher.score_job = MagicMock(return_value=fake_score)

        result = stages.stage_score_and_rank([sample_job_listing], min_score=60)

        assert result.success
        stages.job_matcher.score_job.assert_called_once_with(
            job=sample_job_listing, profile=stages.context.user_profile
        )
        assert result.data == [(sample_job_listing, fake_score)]


class TestStageGenerateResumes:
    """stage_generate_resumes must call the real selector/writer/validator/
    formatter signatures and read ValidationResult.overall_score."""

    def test_generates_and_formats_resume(
        self, stages: PipelineStages, sample_job_listing
    ):
        selection = SelectionOutput(
            selected_projects=[],
            keywords_to_emphasize=["python"],
            key_achievements=[],
            summary_suggestion="Experienced engineer.",
            raw_response="{}",
        )
        resume = GeneratedResume(
            summary="Experienced engineer.",
            skills=["python"],
            experience=[],
            projects=[],
            education=[],
            raw_response="{}",
            model_used="mock-model",
        )
        validation = ValidationResult(
            is_valid=True,
            missing_projects=[],
            missing_keywords=[],
            fabricated_content=[],
            date_inconsistencies=[],
            overall_score=88,
            recommendation="approve",
            issues=[],
        )
        cover_letter = GeneratedCoverLetter(
            content="Dear hiring manager...",
            highlighted_experiences=[],
            word_count=250,
            model_used="mock-model",
        )
        cl_validation = CoverLetterValidationResult(
            is_valid=True,
            score=80,
            issues=[],
            word_count=250,
            structure_score=80,
            content_score=80,
            tone_score=80,
            recommendation="approve",
            details={},
        )
        formatted = FormattedResume(
            pdf_path="resumes/job.pdf",
            docx_path="resumes/job.docx",
            success=True,
        )

        stages.resume_selector.select = MagicMock(return_value=selection)
        stages.resume_writer.write = MagicMock(return_value=resume)
        stages.resume_validator.validate = MagicMock(return_value=validation)
        stages.cover_letter_writer.write = MagicMock(return_value=cover_letter)
        stages.cover_letter_validator.validate = MagicMock(return_value=cl_validation)
        stages.resume_formatter.format_resume = MagicMock(return_value=formatted)

        result = stages.stage_generate_resumes([sample_job_listing])

        assert result.success, result.error_message
        assert result.metadata["generated_count"] == 1
        assert result.metadata["avg_validation_score"] == 88

        stages.resume_selector.select.assert_called_once_with(
            job=sample_job_listing, profile=stages.context.user_profile
        )
        stages.resume_writer.write.assert_called_once_with(
            job=sample_job_listing,
            profile=stages.context.user_profile,
            selection=selection,
        )
        stages.resume_validator.validate.assert_called_once_with(
            resume=resume,
            job=sample_job_listing,
            profile=stages.context.user_profile,
            selection=selection,
        )
        stages.resume_formatter.format_resume.assert_called_once_with(
            resume=resume,
            filename=str(sample_job_listing.job_id),
            formats=["pdf", "docx"],
        )


class TestStageGenerateResumesOutcome:
    """stage_generate_resumes reports success and failure honestly."""

    def test_no_selected_jobs_is_a_success(self, stages: PipelineStages):
        """An empty selection is not an error, so a full run can finish."""
        result = stages.stage_generate_resumes([])

        assert result.success
        assert result.error_message is None
        assert result.metadata["generated_count"] == 0

    def test_all_selected_jobs_failing_is_a_failure_with_a_message(
        self, stages: PipelineStages, sample_job_listing
    ):
        """When every selected job fails, the stage fails and says why."""
        stages.resume_selector.select = MagicMock(side_effect=RuntimeError("down"))

        result = stages.stage_generate_resumes([sample_job_listing])

        assert not result.success
        assert result.error_message == (
            "No resume was generated for the 1 selected jobs"
        )


def _submission_info(job, can_auto_submit: bool):
    """Build submission info for one job.

    Args:
        job: Job listing.
        can_auto_submit: Whether the job supports auto-submit.

    Returns:
        A ``SubmissionInfo`` for the job.
    """
    from src.submission.detector import ApplyMethod, SubmissionInfo

    method = ApplyMethod.EASY_APPLY if can_auto_submit else ApplyMethod.MANUAL
    return SubmissionInfo(job=job, can_auto_submit=can_auto_submit, apply_method=method)


def _manual_and_auto_jobs(sample_job_listing):
    """Build two jobs: A needs a manual application, B supports auto-submit.

    Args:
        sample_job_listing: Job listing fixture used as a template.

    Returns:
        Tuple of (job A, job B, generated resume data for A then B).
    """
    job_a = sample_job_listing.model_copy(update={"job_id": "job-a", "title": "A"})
    job_b = sample_job_listing.model_copy(update={"job_id": "job-b", "title": "B"})
    generated = [
        {"job": job_a, "pdf_path": "a.pdf", "cover_letter_path": "a_cl.pdf"},
        {"job": job_b, "pdf_path": "b.pdf", "cover_letter_path": "b_cl.pdf"},
    ]
    return job_a, job_b, generated


class TestStageSubmitApplications:
    """stage_submit_applications records only real submissions, by job_id."""

    def test_dry_run_records_nothing_and_counts_zero_applied(
        self, stages: PipelineStages, sample_job_listing, monkeypatch
    ):
        """A simulated submission is not saved as an applied record."""
        job_a, job_b, generated = _manual_and_auto_jobs(sample_job_listing)
        stages.context.submission_info = [
            _submission_info(job_a, False),
            _submission_info(job_b, True),
        ]
        tracker_cls = MagicMock()
        monkeypatch.setattr("src.pipeline.stages.ApplicationTracker", tracker_cls)

        result = stages.stage_submit_applications(generated)

        assert result.success, result.error_message
        assert stages.auto_submitter.dry_run is True
        tracker_cls.return_value.track_application.assert_not_called()
        assert result.metadata["total_applications"] == 0
        assert result.metadata["simulated"] == 1
        assert result.metadata["manual_required"] == 1
        assert result.metadata["resumes_generated"] == 2

    def test_real_run_tracks_each_result_with_its_own_resume(
        self, stages: PipelineStages, sample_job_listing, monkeypatch
    ):
        """Results are paired with resumes by job_id, not by list position."""
        from datetime import datetime

        from src.submission.submitter import SubmissionResult, SubmissionStatus

        job_a, job_b, generated = _manual_and_auto_jobs(sample_job_listing)
        stages.context.submission_info = [
            _submission_info(job_a, False),
            _submission_info(job_b, True),
        ]
        stages.auto_submitter.dry_run = False
        stages.auto_submitter.submit_batch = MagicMock(
            return_value=[
                SubmissionResult(
                    job=job_b,
                    status=SubmissionStatus.SUBMITTED,
                    success=True,
                    timestamp=datetime.now(),
                    submission_id="sub-b",
                )
            ]
        )
        tracker_cls = MagicMock()
        monkeypatch.setattr("src.pipeline.stages.ApplicationTracker", tracker_cls)

        result = stages.stage_submit_applications(generated)

        assert result.success, result.error_message
        submitted = stages.auto_submitter.submit_batch.call_args.args[0]
        assert [info.job.job_id for info in submitted] == ["job-b"]
        tracker_cls.return_value.track_application.assert_called_once_with(
            job=job_b,
            submission_id="sub-b",
            generated_resume_path="b.pdf",
            cover_letter_path="b_cl.pdf",
        )
        assert result.metadata["total_applications"] == 1
        assert result.metadata["successful"] == 1
        assert result.metadata["manual_required"] == 1

    def test_only_manual_jobs_count_zero_applied(
        self, stages: PipelineStages, sample_job_listing
    ):
        """Generated resumes alone never count as applications."""
        job_a, _job_b, generated = _manual_and_auto_jobs(sample_job_listing)
        stages.context.submission_info = [_submission_info(job_a, False)]

        result = stages.stage_submit_applications(generated[:1])

        assert result.success, result.error_message
        assert result.metadata["total_applications"] == 0
        assert result.metadata["manual_required"] == 1


class TestStageLinkedInAuth:
    """stage_linkedin_auth checks credentials and never opens a browser."""

    def test_reports_credentials_without_launching_a_browser(
        self, stages: PipelineStages, sample_job_listing, monkeypatch
    ):
        """With credentials set, the stage only reports them."""
        import playwright.sync_api

        def no_browser(*_args, **_kwargs):
            """Fail the test if the stage starts Playwright."""
            raise AssertionError("stage_linkedin_auth must not start a browser")

        monkeypatch.setattr(playwright.sync_api, "sync_playwright", no_browser)
        monkeypatch.setenv("LINKEDIN_EMAIL", "user@example.com")
        monkeypatch.setenv("LINKEDIN_PASSWORD", "placeholder")
        infos = [_submission_info(sample_job_listing, True)]

        result = stages.stage_linkedin_auth(infos)

        assert result.success
        assert result.data == infos
        assert result.metadata["linkedin_credentials_available"] is True
        assert result.metadata["easy_apply_jobs_count"] == 1

    def test_missing_credentials_do_not_fail_the_run(
        self, stages: PipelineStages, monkeypatch
    ):
        """Without credentials the stage still succeeds."""
        monkeypatch.delenv("LINKEDIN_EMAIL", raising=False)
        monkeypatch.delenv("LINKEDIN_PASSWORD", raising=False)

        result = stages.stage_linkedin_auth([])

        assert result.success
        assert result.metadata["linkedin_credentials_available"] is False
