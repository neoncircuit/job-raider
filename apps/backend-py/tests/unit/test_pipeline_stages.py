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
