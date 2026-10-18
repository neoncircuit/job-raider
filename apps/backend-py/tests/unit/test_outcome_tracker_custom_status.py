"""
Tests for deleting custom application statuses.

Before 2026-10-18, a hard delete called ``Path.remove()``, which does not
exist. The status left the in-memory cache, then the call raised, so the
JSON file stayed on disk and the status came back after a restart.
"""

from pathlib import Path

from src.metrics.outcome_tracker import OutcomeTracker


def test_hard_delete_removes_the_status_file(tmp_path: Path) -> None:
    """A hard delete removes the status from memory and from disk.

    Args:
        tmp_path: Temporary storage directory.
    """
    tracker = OutcomeTracker(storage_dir=str(tmp_path))
    status = tracker.create_custom_status(name="Take-home", description="Test task")
    status_file = tracker.custom_statuses_dir / f"{status.status_id}.json"
    assert status_file.exists()

    assert tracker.delete_custom_status(status.status_id, hard_delete=True) is True

    assert not status_file.exists()
    reloaded = OutcomeTracker(storage_dir=str(tmp_path))
    assert status.status_id not in {
        s.status_id for s in reloaded.get_custom_statuses(active_only=False)
    }


def test_soft_delete_keeps_the_file_and_deactivates(tmp_path: Path) -> None:
    """A soft delete keeps the file and marks the status inactive.

    Args:
        tmp_path: Temporary storage directory.
    """
    tracker = OutcomeTracker(storage_dir=str(tmp_path))
    status = tracker.create_custom_status(name="On hold", description="Paused")

    assert tracker.delete_custom_status(status.status_id) is True

    reloaded = OutcomeTracker(storage_dir=str(tmp_path))
    statuses = {s.status_id: s for s in reloaded.get_custom_statuses(active_only=False)}
    assert statuses[status.status_id].is_active is False
