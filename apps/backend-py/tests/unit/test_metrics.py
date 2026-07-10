# Unit tests for metrics module
# Author: Job Raider
# Date: 2026-04-21

from datetime import datetime, timedelta

import pytest

from src.metrics.cost_tracker import (
    CostTracker,
    ModelCost,
    ModelProvider,
    TaskType,
    TokenUsage,
)
from src.metrics.outcome_tracker import (
    ApplicationStatus,
    InterviewEvent,
    InterviewStage,
    Outcome,
    OutcomeTracker,
)


@pytest.mark.unit
class TestCostTracker:
    """Tests for CostTracker class."""

    def test_initialization(self, temp_data_dir):
        """Test tracker initialization."""
        tracker = CostTracker(storage_dir=str(temp_data_dir / "metrics"))
        assert tracker is not None
        assert tracker.storage_dir.exists()

    def test_start_run(self, temp_data_dir):
        """Test starting a tracking run."""
        tracker = CostTracker(storage_dir=str(temp_data_dir / "metrics"))
        run_id = tracker.start_run()

        assert run_id is not None
        assert tracker._current_run_id == run_id

    def test_track_call(self, temp_data_dir):
        """Test tracking an API call."""
        tracker = CostTracker(storage_dir=str(temp_data_dir / "metrics"))
        tracker.start_run()

        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )

        tracker.track_call(
            task_type=TaskType.SELECTION,
            model_name="qwen2.5:3b",
            token_usage=usage,
            duration_seconds=5.0,
        )

        assert len(tracker._calls) == 1
        assert tracker.get_current_run_cost() == 0.0  # Ollama is free

    def test_track_api_call(self, temp_data_dir):
        """Test tracking paid API call."""
        tracker = CostTracker(storage_dir=str(temp_data_dir / "metrics"))
        tracker.start_run()

        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )

        tracker.track_call(
            task_type=TaskType.WRITING,
            model_name="claude-sonnet-4-6",
            token_usage=usage,
            duration_seconds=3.0,
        )

        assert len(tracker._calls) == 1
        assert tracker.get_current_run_cost() > 0  # Claude costs money

    def test_end_run(self, temp_data_dir):
        """Test ending a tracking run."""
        tracker = CostTracker(storage_dir=str(temp_data_dir / "metrics"))
        tracker.start_run()

        # Add some calls
        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )

        tracker.track_call(
            task_type=TaskType.SELECTION,
            model_name="qwen2.5:3b",
            token_usage=usage,
            duration_seconds=1.0,
        )

        summary = tracker.end_run()

        assert summary.total_calls == 1
        assert summary.total_tokens == 1500
        assert summary.total_cost_usd == 0.0  # Free model

    def test_cost_estimate(self, temp_data_dir):
        """Test cost estimation."""
        tracker = CostTracker(storage_dir=str(temp_data_dir / "metrics"))

        estimate = tracker.get_cost_estimate(
            num_jobs=50,
            use_local_models=True,
        )

        assert estimate["num_applications"] == 50
        assert estimate["total_cost_usd"] == 0.0  # Local models are free
        assert "task_breakdown" in estimate


@pytest.mark.unit
class TestOutcomeTracker:
    """Tests for OutcomeTracker class."""

    def test_initialization(self, temp_data_dir):
        """Test tracker initialization."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir / "applications"))
        assert tracker is not None
        assert tracker.storage_dir.exists()

    def test_track_application(self, temp_data_dir):
        """Test tracking a new application."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir / "applications"))

        outcome = tracker.track_application(
            application_id="app_123",
            job_title="Software Engineer",
            company="Tech Corp",
        )

        assert outcome.application_id == "app_123"
        assert outcome.job_title == "Software Engineer"
        assert outcome.company == "Tech Corp"
        assert outcome.current_status == ApplicationStatus.APPLIED

    def test_update_status(self, temp_data_dir):
        """Test updating application status."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir / "applications"))

        tracker.track_application(
            application_id="app_456",
            job_title="Engineer",
            company="Test Co",
        )

        success = tracker.update_status(
            application_id="app_456",
            status=ApplicationStatus.UNDER_REVIEW,
            note="Application received",
        )

        assert success is True

        outcome = tracker.get_application("app_456")
        assert outcome.current_status == ApplicationStatus.UNDER_REVIEW
        assert len(outcome.timeline_notes) == 1

    def test_add_interview(self, temp_data_dir):
        """Test adding interview event."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir / "applications"))

        tracker.track_application(
            application_id="app_789",
            job_title="Developer",
            company="Startup",
        )

        success = tracker.add_interview(
            application_id="app_789",
            stage=InterviewStage.SCREENING,
            scheduled_date=datetime.now() + timedelta(days=3),
        )

        assert success is True

        outcome = tracker.get_application("app_789")
        assert len(outcome.interviews) == 1
        assert outcome.interviews[0].stage == InterviewStage.SCREENING

    def test_complete_interview(self, temp_data_dir):
        """Test completing an interview."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir / "applications"))

        tracker.track_application(
            application_id="app_101",
            job_title="Engineer",
            company="Corp",
        )

        tracker.add_interview(
            application_id="app_101",
            stage=InterviewStage.SCREENING,
        )

        success = tracker.complete_interview(
            application_id="app_101",
            stage=InterviewStage.SCREENING,
            outcome="passed",
            feedback="Good fit",
        )

        assert success is True

        outcome = tracker.get_application("app_101")
        assert outcome.interviews[0].completed_date is not None
        assert outcome.interviews[0].outcome == "passed"

    def test_add_offer(self, temp_data_dir):
        """Test adding offer details."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir / "applications"))

        tracker.track_application(
            application_id="app_202",
            job_title="Senior Engineer",
            company="Big Tech",
        )

        success = tracker.add_offer(
            application_id="app_202",
            salary_min=150000,
            salary_max=200000,
            benefits=["Health insurance", "401k"],
        )

        assert success is True

        outcome = tracker.get_application("app_202")
        assert outcome.offer is not None
        assert outcome.offer.salary_min == 150000
        assert len(outcome.offer.benefits) == 2
        assert outcome.final_outcome == Outcome.OFFER

    def test_conversion_metrics(self, temp_data_dir):
        """Test conversion metrics calculation."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir / "applications"))

        # Add some applications
        for i in range(10):
            tracker.track_application(
                application_id=f"app_{i}",
                job_title="Engineer",
                company=f"Company {i}",
            )

        # Mark some as having interviews
        tracker.add_interview("app_0", InterviewStage.SCREENING)
        tracker.add_interview("app_1", InterviewStage.SCREENING)

        metrics = tracker.get_conversion_metrics(days=30)

        assert metrics.total_applications == 10
        assert 0 <= metrics.screening_rate <= 1
        assert 0 <= metrics.offer_rate <= 1


@pytest.mark.unit
class TestDataStructures:
    """Tests for data structures."""

    def test_token_usage(self):
        """Test TokenUsage dataclass."""
        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )

        assert usage.total_tokens == 1500
        assert usage.total_thousands == 1.5

    def test_model_cost(self):
        """Test ModelCost calculations."""
        model = ModelCost(
            provider=ModelProvider.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            input_cost_per_million=3.0,
            output_cost_per_million=15.0,
        )

        usage = TokenUsage(
            prompt_tokens=1000000,  # 1M
            completion_tokens=500000,  # 0.5M
            total_tokens=1500000,
        )

        cost = model.calculate_cost(usage)

        # 1M * $3 + 0.5M * $15 = $3 + $7.50 = $10.50
        assert abs(cost - 10.50) < 0.01

    def test_interview_event(self):
        """Test InterviewEvent dataclass."""
        now = datetime.now()
        event = InterviewEvent(
            stage=InterviewStage.TECHNICAL,
            scheduled_date=now,
            completed_date=now + timedelta(hours=1),
            feedback="Good technical skills",
            outcome="passed",
        )

        assert event.stage == InterviewStage.TECHNICAL
        assert event.feedback == "Good technical skills"
