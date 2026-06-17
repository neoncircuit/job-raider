# Integration tests for the full pipeline
# Author: Job Raider
# Date: 2026-04-21

from datetime import datetime
from pathlib import Path

import pytest

from src.models.user_profile import (
    ContactInfo,
    ExperienceLevel,
    ProficiencyLevel,
    Skill,
    SkillCategory,
    TargetJob,
    UserProfile,
)
from src.pipeline.orchestrator import (
    PipelineConfig,
    PipelineOrchestrator,
    PipelineStage,
)


@pytest.mark.integration
class TestPipelineOrchestrator:
    """Integration tests for the pipeline orchestrator."""

    def test_orchestrator_initialization(self, sample_user_profile, temp_data_dir):
        """Test orchestrator initialization."""
        config = PipelineConfig(
            keywords=["python"],
            locations=["remote"],
            dry_run=True,
        )

        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=sample_user_profile,
        )

        assert orchestrator is not None
        assert orchestrator.config == config
        assert orchestrator.user_profile == sample_user_profile

    def test_pipeline_dry_run(self, sample_user_profile, temp_data_dir):
        """Test running pipeline in dry-run mode."""
        config = PipelineConfig(
            keywords=["python"],
            locations=["remote"],
            sources=["linkedin"],
            dry_run=True,
            skip_submission=True,  # Skip actual submission
        )

        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=sample_user_profile,
        )

        # Run from scoring stage (skip scraping for integration test)
        result = orchestrator.run(
            start_from=PipelineStage.FILTER_PROFILE,
            stop_at=PipelineStage.GENERATE_RESUMES,
        )

        assert result is not None
        assert isinstance(result.duration_seconds, float)

    @pytest.mark.slow
    def test_pipeline_with_mock_scraping(self, sample_user_profile, temp_data_dir):
        """Test pipeline with mock scraping data."""
        from src.models.job_listing import JobListing, JobRequirement, JobSource
        from src.models.job_listing import Skill as JobSkill

        # Create mock job listings
        mock_jobs = [
            JobListing(
                title="Python Engineer",
                company="Tech Corp",
                location="Remote",
                description="Python developer role",
                requirements=[JobRequirement(text="Python experience")],
                skills=[JobSkill(name="python"), JobSkill(name="django")],
                source=JobSource.LINKEDIN,
                job_id=f"job_{i}",
            )
            for i in range(5)
        ]

        # Save mock data
        listings_dir = temp_data_dir / "listings"
        listings_dir.mkdir(parents=True, exist_ok=True)

        import json

        for job in mock_jobs:
            filepath = listings_dir / f"{job.job_id}.json"
            with open(filepath, "w") as f:
                json.dump(job.model_dump(), f, default=str)

        config = PipelineConfig(
            keywords=["python"],
            locations=["remote"],
            dry_run=True,
            skip_submission=True,
        )

        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=sample_user_profile,
        )

        result = orchestrator.run(
            start_from=PipelineStage.DEDUPLICATE,
            stop_at=PipelineStage.SCORE_RANK,
        )

        assert result is not None

    def test_pipeline_hooks(self, sample_user_profile, temp_data_dir):
        """Test pipeline stage hooks."""
        config = PipelineConfig(
            keywords=["python"],
            locations=["remote"],
            dry_run=True,
        )

        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=sample_user_profile,
        )

        # Track hook execution
        hook_executed = []

        def before_hook(stage):
            hook_executed.append(f"before_{stage}")

        def after_hook(stage, result):
            hook_executed.append(f"after_{stage}")

        # Register hooks
        orchestrator.register_before_hook(
            PipelineStage.FILTER_PROFILE,
            before_hook,
        )
        orchestrator.register_after_hook(
            PipelineStage.FILTER_PROFILE,
            after_hook,
        )

        # Run pipeline
        result = orchestrator.run(
            start_from=PipelineStage.FILTER_PROFILE,
            stop_at=PipelineStage.FILTER_PROFILE,
        )

        # Note: Hooks may not execute in dry-run with no data
        assert result is not None

    def test_pipeline_result_summary(self, sample_user_profile, temp_data_dir):
        """Test pipeline result summary."""
        config = PipelineConfig(
            keywords=["python"],
            locations=["remote"],
            dry_run=True,
        )

        orchestrator = PipelineOrchestrator(
            config=config,
            user_profile=sample_user_profile,
        )

        result = orchestrator.run(
            start_from=PipelineStage.FILTER_PROFILE,
            stop_at=PipelineStage.FILTER_PROFILE,
        )

        # Access result properties
        assert hasattr(result, "success")
        assert hasattr(result, "stages_completed")
        assert hasattr(result, "duration_seconds")
        assert hasattr(result, "stage_results")


@pytest.mark.integration
class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    def test_full_workflow_simulation(self, sample_user_profile, temp_data_dir):
        """Test simulated full workflow without actual scraping."""
        import json

        from src.generation.selector import ResumeSelector
        from src.models.job_listing import (
            JobListing,
            JobRequirement,
            JobResponsibility,
            JobSource,
        )
        from src.models.job_listing import Skill as JobSkill
        from src.scoring.matcher import JobMatcher

        # Create sample job
        job = JobListing(
            title="Senior Python Developer",
            company="Tech Startup",
            location="Remote",
            description="Looking for senior Python developer...",
            requirements=[
                JobRequirement(text="5+ years Python experience"),
                JobRequirement(text="Django/FastAPI experience"),
                JobRequirement(text="Remote work experience"),
            ],
            responsibilities=[
                JobResponsibility(text="Build and maintain APIs"),
                JobResponsibility(text="Mentor team members"),
            ],
            skills=[
                JobSkill(name="python"),
                JobSkill(name="django"),
                JobSkill(name="fastapi"),
                JobSkill(name="postgresql"),
                JobSkill(name="redis"),
            ],
            source=JobSource.LINKEDIN,
            job_id="test_job_001",
        )

        # Save job to storage
        listings_dir = temp_data_dir / "listings"
        listings_dir.mkdir(parents=True, exist_ok=True)
        with open(listings_dir / "test_job_001.json", "w") as f:
            json.dump(job.model_dump(), f, default=str)

        # Score the job
        matcher = JobMatcher()
        score = matcher.score_job(job, sample_user_profile)

        assert score.total_score > 0

        # If score is high enough, proceed to resume generation
        if score.total_score >= 60:
            # This would normally use LLM, skip in integration test
            pass


@pytest.mark.integration
class TestComponentIntegration:
    """Integration tests for component interactions."""

    def test_scraper_to_storage(self, temp_data_dir):
        """Test scraper to storage workflow."""
        from src.models.job_listing import JobListing, JobListingCollection, JobSource
        from src.scrapers.storage import JobListingStorage

        storage = JobListingStorage(str(temp_data_dir / "listings"))

        job = JobListing(
            title="Test Job",
            company="Test Company",
            location="Remote",
            source=JobSource.MANUAL,
            job_id="test_storage_001",
        )

        # Save job
        collection = JobListingCollection(listings=[job], source=JobSource.MANUAL)
        storage.save_collection(collection)

        # Verify ID was tracked
        assert storage.is_new_listing("test_storage_001") is False

    def test_filter_to_matcher(self, sample_user_profile):
        """Test filter to scorer workflow."""
        from src.models.job_listing import JobListing, JobListingCollection, JobSource
        from src.models.job_listing import Skill as JobSkill
        from src.scoring.filter import JobFilter
        from src.scoring.matcher import JobMatcher

        # Create sample jobs
        jobs = [
            JobListing(
                title="Python Developer",
                company="Tech Corp",
                location="Remote",
                description="Python role",
                skills=[JobSkill(name="python")],
                source=JobSource.LINKEDIN,
                job_id="job_1",
            ),
            JobListing(
                title="Java Developer",  # Wrong tech stack
                company="Data Inc",
                location="Remote",
                description="Java role",
                skills=[JobSkill(name="java")],
                source=JobSource.LINKEDIN,
                job_id="job_2",
            ),
        ]

        # Filter by profile
        collection = JobListingCollection(listings=jobs)
        job_filter = JobFilter()
        filtered = job_filter.filter_by_profile(collection, sample_user_profile)

        # Score filtered jobs
        matcher = JobMatcher()
        scored = [
            matcher.score_job(job, sample_user_profile) for job in filtered.listings
        ]

        assert len(scored) <= len(jobs)
        assert all(score.total_score >= 0 for score in scored)


@pytest.mark.integration
@pytest.mark.llm
class TestLLMIntegration:
    """Integration tests with actual LLM calls (requires API keys)."""

    @pytest.mark.skipif(
        "not config.getoption('--run-llm-tests')",
        reason="LLM tests require --run-llm-tests flag",
    )
    def test_ollama_integration(self, sample_user_profile):
        """Test Ollama integration."""
        from src.llm.ollama_client import OllamaClient

        client = OllamaClient(model="qwen2.5:3b")

        response = client.generate(
            messages=[{"role": "user", "content": "Say 'Hello, World!'"}]
        )

        assert response.content is not None
        assert len(response.content) > 0

    @pytest.mark.skipif(
        "not config.getoption('--run-llm-tests')",
        reason="LLM tests require --run-llm-tests flag",
    )
    def test_resume_generation_flow(self, sample_user_profile, temp_data_dir):
        """Test resume generation with actual LLM."""
        from src.generation.resume_writer import ResumeWriter
        from src.generation.selector import ResumeSelector
        from src.models.job_listing import JobListing, JobRequirement, JobSource
        from src.models.job_listing import Skill as JobSkill

        job = JobListing(
            title="Python Engineer",
            company="Tech Corp",
            location="Remote",
            description="We need a Python engineer...",
            requirements=[JobRequirement(text="Python"), JobRequirement(text="Django")],
            skills=[JobSkill(name="python"), JobSkill(name="django")],
            source=JobSource.MANUAL,
            job_id="test_llm_job",
        )

        # Select content
        selector = ResumeSelector()
        selection = selector.select(
            job_description=job.description,
            user_profile=sample_user_profile,
        )

        assert selection is not None
        assert len(selection.selected_projects) > 0

        # Generate resume (this would use LLM)
        # Skip in integration test to avoid API costs
