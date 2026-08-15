"""
Unit tests for application tracker feature.
"""

import json

import pytest

from src.metrics.outcome_tracker import (
    ApplicationStatus,
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

    def test_long_job_id_saves_without_enametoolong(self, temp_data_dir):
        """JSearch-style ids must not be used as the raw filename."""
        from src.metrics.outcome_tracker import application_filename_stem

        long_id = "b29x" + "A" * 400 + ":colon"
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))
        outcome = tracker.track_external_application(
            job_id=long_id,
            job_title="AI Engineer",
            company="Acme",
            application_method="External site",
        )
        assert outcome.application_id == long_id
        stem = application_filename_stem(long_id)
        assert len(stem) < 80
        assert stem.startswith("id_")
        path = temp_data_dir / f"{stem}.json"
        assert path.exists()
        loaded_on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert loaded_on_disk["application_id"] == long_id

        reloaded = OutcomeTracker(storage_dir=str(temp_data_dir))
        loaded = reloaded.get_application(long_id)
        assert loaded is not None
        assert loaded.job_title == "AI Engineer"
        assert loaded.current_status == ApplicationStatus.APPLIED_ELSEWHERE

        all_apps = reloaded.get_all_applications()
        assert any(o.application_id == long_id for o in all_apps)
        external = reloaded.get_external_applications()
        assert any(o.application_id == long_id for o in external)

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

    def test_external_visible_across_tracker_instances(self, temp_data_dir):
        """Disk-backed state must be visible to a second tracker (multi-worker)."""
        writer = OutcomeTracker(storage_dir=str(temp_data_dir))
        writer.track_external_application(
            "ext_peer",
            "Software Engineer",
            "Peer Co",
            application_method="External site",
        )

        reader = OutcomeTracker(storage_dir=str(temp_data_dir))
        external = reader.get_external_applications()
        assert any(o.application_id == "ext_peer" for o in external)

        apps = reader.get_all_applications()
        assert any(o.application_id == "ext_peer" for o in apps)

    def test_applied_elsewhere_transitions_to_interview(self, temp_data_dir):
        """Applied-elsewhere rows can move to the same interview stage as regular apps."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))
        tracker.track_external_application(
            "ext_interview",
            "Engineer",
            "Acme",
            application_method="External site",
            metadata={"description": "A" * 60},
        )

        success = tracker.update_status(
            "ext_interview",
            ApplicationStatus.SCREENING_SCHEDULED,
        )
        assert success is True
        outcome = tracker.get_application("ext_interview")
        assert outcome is not None
        assert outcome.current_status == ApplicationStatus.SCREENING_SCHEDULED
        assert len(outcome.metadata.get("description", "")) >= 50

    def test_update_status_merges_job_description(self, temp_data_dir):
        """A later JD paste must merge into metadata without dropping the row."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))
        tracker.track_external_application(
            "ext_paste",
            "Engineer",
            "Acme",
            application_method="External site",
        )

        success = tracker.update_status(
            "ext_paste",
            ApplicationStatus.APPLIED_ELSEWHERE,
            metadata={"description": "B" * 80},
        )
        assert success is True
        outcome = tracker.get_application("ext_paste")
        assert outcome is not None
        assert outcome.current_status == ApplicationStatus.APPLIED_ELSEWHERE
        assert outcome.metadata["description"] == "B" * 80

    def test_retrack_does_not_reset_interview_status(self, temp_data_dir):
        """Re-tracking an interview-stage row must keep the interview status."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))
        tracker.track_external_application(
            "ext_keep",
            "Engineer",
            "Acme",
            application_method="External site",
        )
        tracker.update_status("ext_keep", ApplicationStatus.SCREENING_SCHEDULED)

        updated = tracker.track_external_application(
            "ext_keep",
            "Engineer",
            "Acme",
            application_method="External site",
            metadata={"description": "C" * 70},
        )
        assert updated.current_status == ApplicationStatus.SCREENING_SCHEDULED
        assert updated.metadata["description"] == "C" * 70

    def test_external_preserves_bookmark(self, temp_data_dir):
        """Marking applied elsewhere should not drop an existing bookmark."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))
        tracker.save_job("job_saved", "Engineer", "Acme")
        outcome = tracker.track_external_application(
            "job_saved", "Engineer", "Acme", application_method="External site"
        )
        assert outcome.current_status == ApplicationStatus.APPLIED_ELSEWHERE
        assert outcome.is_bookmarked is True

    def test_delete_application_short_id(self, temp_data_dir):
        """Untrack must remove the cache entry and the short-id JSON file."""
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))
        tracker.track_external_application(
            "ext_del_1", "Developer", "Startup", application_method="External site"
        )
        path = temp_data_dir / "ext_del_1.json"
        assert path.exists()

        assert tracker.delete_application("ext_del_1") is True
        assert tracker.get_application("ext_del_1") is None
        assert not path.exists()
        assert tracker.delete_application("ext_del_1") is False

    def test_delete_application_hashed_id(self, temp_data_dir):
        """Untrack must resolve hashed id_*.json stems from the logical job id."""
        from src.metrics.outcome_tracker import application_filename_stem

        long_id = "b29x" + "B" * 400 + ":colon"
        tracker = OutcomeTracker(storage_dir=str(temp_data_dir))
        tracker.track_external_application(
            long_id, "AI Engineer", "Acme", application_method="External site"
        )
        path = temp_data_dir / f"{application_filename_stem(long_id)}.json"
        assert path.exists()
        assert path.name.startswith("id_")

        assert tracker.delete_application(long_id) is True
        assert tracker.get_application(long_id) is None
        assert not path.exists()
        remaining = OutcomeTracker(storage_dir=str(temp_data_dir))
        assert remaining.get_application(long_id) is None
        assert all(
            o.application_id != long_id for o in remaining.get_all_applications()
        )

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
