"""
Unit tests for application tracker feature.
"""

import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.metrics.outcome_tracker import (
    ApplicationStatus,
    CustomApplicationStatus,
    OutcomeTracker,
)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary directory for test data."""
    data_dir = tmp_path / "applications"
    data_dir.mkdir()
    yield data_dir
    # Cleanup is handled by tmp_path fixture


@pytest.mark.unit
class TestApplicationTracker:
    """Tests for new application tracking features."""

    def test_save_job(self, temp_data_dir):
        """Test saving/bookmarking a job."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        outcome = tracker.save_job(
            job_id="job_123",
            job_title="Software Engineer",
            company="Tech Corp",
            source_url="https://example.com/job",
        )

        assert outcome.application_id == "job_123"
        assert outcome.current_status == ApplicationStatus.SAVED_BOOKMARKED
        assert outcome.is_bookmarked is True
        assert outcome.bookmark_date is not None
        assert outcome.metadata["source_url"] == "https://example.com/job"

    def test_mark_not_interested(self, temp_data_dir):
        """Test marking job as not interested."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        # First create an application
        tracker.track_application("app_1", "Engineer", "Company")

        # Then mark as not interested
        success = tracker.mark_not_interested("app_1", "Not a good fit")

        assert success is True

        outcome = tracker.get_application("app_1")
        assert outcome.current_status == ApplicationStatus.NOT_INTERESTED
        assert outcome.is_hidden is True
        assert outcome.hidden_date is not None
        assert len(outcome.timeline_notes) == 1
        assert "Marked not interested" in outcome.timeline_notes[0]["note"]

    def test_track_external_application(self, temp_data_dir):
        """Test tracking external application."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        outcome = tracker.track_external_application(
            job_id="ext_123",
            job_title="Developer",
            company="Startup",
            application_method="referral",
        )

        assert outcome.current_status == ApplicationStatus.APPLIED_ELSEWHERE
        assert outcome.external_application_details is not None
        assert outcome.external_application_details["application_method"] == "referral"
        assert "tracked_at" in outcome.external_application_details

    def test_create_custom_status(self, temp_data_dir):
        """Test creating custom status."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        status = tracker.create_custom_status(
            name="Waiting for Feedback",
            description="Applied and waiting for response",
            color="#FFA500",
        )

        assert status.status_id.startswith("custom_")
        assert status.name == "Waiting for Feedback"
        assert status.color == "#FFA500"
        assert status.is_active is True

        # Check it's in the list
        statuses = tracker.get_custom_statuses()
        assert len(statuses) == 1
        assert statuses[0].status_id == status.status_id

    def test_set_custom_status(self, temp_data_dir):
        """Test setting custom status on application."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Create application and custom status
        tracker.track_application("app_1", "Engineer", "Company")
        status = tracker.create_custom_status(
            name="Custom Status",
            description="Test",
        )

        # Set custom status
        success = tracker.set_custom_status("app_1", status.status_id)

        assert success is True

        outcome = tracker.get_application("app_1")
        assert outcome.current_status == ApplicationStatus.CUSTOM
        assert outcome.custom_status_id == status.status_id

    def test_get_bookmarked_jobs(self, temp_data_dir):
        """Test retrieving bookmarked jobs."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Save some jobs
        tracker.save_job("job_1", "Engineer", "Company A")
        tracker.save_job("job_2", "Developer", "Company B")
        tracker.track_application("app_1", "Senior", "Company C")

        bookmarked = tracker.get_bookmarked_jobs()

        assert len(bookmarked) == 2
        assert all(j.is_bookmarked for j in bookmarked)

    def test_get_hidden_jobs(self, temp_data_dir):
        """Test retrieving hidden jobs."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Create and hide some jobs
        tracker.track_application("app_1", "Engineer", "Company A")
        tracker.track_application("app_2", "Developer", "Company B")
        tracker.mark_not_interested("app_1", "Not interested")

        hidden = tracker.get_hidden_jobs()

        assert len(hidden) == 1
        assert hidden[0].application_id == "app_1"
        assert hidden[0].is_hidden is True

    def test_get_external_applications(self, temp_data_dir):
        """Test retrieving external applications."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        tracker.track_external_application("ext_1", "Engineer", "Company A")
        tracker.track_application("app_1", "Developer", "Company B")

        external = tracker.get_external_applications()

        assert len(external) == 1
        assert external[0].application_id == "ext_1"
        assert external[0].current_status == ApplicationStatus.APPLIED_ELSEWHERE

    def test_unsave_job(self, temp_data_dir):
        """Test unsaving a job."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Save a job
        tracker.save_job("job_1", "Engineer", "Company")

        # Unsave it
        success = tracker.unsave_job("job_1")

        assert success is True

        outcome = tracker.get_application("job_1")
        assert outcome.is_bookmarked is False
        assert outcome.bookmark_date is None
        assert outcome.current_status == ApplicationStatus.APPLIED

    def test_unhide_job(self, temp_data_dir):
        """Test unhiding a job."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Create and hide a job
        tracker.track_application("app_1", "Engineer", "Company")
        tracker.mark_not_interested("app_1", "Not interested")

        # Unhide it
        success = tracker.unhide_job("app_1")

        assert success is True

        outcome = tracker.get_application("app_1")
        assert outcome.is_hidden is False
        assert outcome.hidden_date is None
        assert outcome.current_status == ApplicationStatus.APPLIED

    def test_custom_status_persistence(self, temp_data_dir):
        """Test that custom statuses persist across tracker instances."""
        # Create custom status with first tracker instance
        tracker1 = OutcomeTracker(storage_dir=str(temp_data_dir))
        status = tracker1.create_custom_status(
            name="Persistent Status",
            description="Should persist",
        )

        # Create new tracker instance
        tracker2 = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Check status was loaded
        statuses = tracker2.get_custom_statuses()
        assert len(statuses) == 1
        assert statuses[0].name == "Persistent Status"
        assert statuses[0].status_id == status.status_id

    def test_outcome_persistence_with_new_fields(self, temp_data_dir):
        """Test that new outcome fields persist correctly."""
        tracker1 = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Create a saved job
        tracker1.save_job(
            "job_1", "Engineer", "Company", source_url="https://example.com"
        )

        # Create new tracker instance
        tracker2 = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Check outcome was loaded with new fields
        outcome = tracker2.get_application("job_1")
        assert outcome.is_bookmarked is True
        assert outcome.bookmark_date is not None
        assert outcome.metadata["source_url"] == "https://example.com"

    def test_delete_custom_status_soft(self, temp_data_dir):
        """Test soft deleting a custom status."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        status = tracker.create_custom_status(
            name="To Delete",
            description="Will be soft deleted",
        )

        success = tracker.delete_custom_status(status.status_id, hard_delete=False)

        assert success is True

        # Status should still exist but be inactive
        statuses = tracker.get_custom_statuses(active_only=False)
        assert len(statuses) == 1
        assert statuses[0].is_active is False

        # Should not appear in active statuses
        active_statuses = tracker.get_custom_statuses(active_only=True)
        assert len(active_statuses) == 0

    def test_get_all_applications_with_new_filters(self, temp_data_dir):
        """Test get_all_applications respects new field filters."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))

        # Create various applications
        tracker.save_job("job_1", "Engineer", "Company A")
        tracker.track_application("app_1", "Developer", "Company B")
        tracker.track_application("app_2", "Designer", "Company C")
        tracker.mark_not_interested("app_2", "Not interested")  # This hides app_2

        # Get all applications
        all_apps = tracker.get_all_applications()
        assert len(all_apps) == 3

        # Filter by status
        bookmarked = [a for a in all_apps if a.is_bookmarked]
        assert len(bookmarked) == 1

        hidden = [a for a in all_apps if a.is_hidden]
        assert len(hidden) == 1
