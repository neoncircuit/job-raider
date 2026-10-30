"""
Unit tests for the agent task-result store.

Covers saving, retrieving, updating, TTL expiration, and bounded-size eviction
behaviour of ``TaskStore``.
"""

import time
from datetime import datetime, timedelta

import pytest

import src.agents.task_store as task_store_module
from src.agents.task_store import TaskRecord, TaskStore


class FakeClock:
    """A monotonic clock that the test sets by hand."""

    def __init__(self, now: float = 1000.0) -> None:
        """Start the clock at a fixed time.

        Args:
            now: The starting value of the clock, in seconds.
        """
        self.now = now

    def __call__(self) -> float:
        """Return the current fake time.

        Returns:
            The current fake time, in seconds.
        """
        return self.now


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Replace ``time.monotonic`` with a clock that the test controls.

    Args:
        monkeypatch: Pytest fixture that restores the patch after the test.

    Returns:
        The fake clock, starting at 1000.0 seconds.
    """
    clock = FakeClock()
    monkeypatch.setattr(time, "monotonic", clock)
    return clock


class TestTaskRecord:
    """Tests for the ``TaskRecord`` dataclass."""

    def test_to_dict_serializes_datetimes(self):
        """``to_dict`` should ISO-format datetime fields."""
        created = datetime(2026, 7, 10, 12, 0, 0)
        updated = datetime(2026, 7, 10, 12, 5, 0)
        record = TaskRecord(
            task_id="task-1",
            status="completed",
            agent="career_coach",
            task_type="career_path_analysis",
            result={"paths": ["backend", "full-stack"]},
            created_at=created,
            updated_at=updated,
        )

        data = record.to_dict()

        assert data["task_id"] == "task-1"
        assert data["status"] == "completed"
        assert data["agent"] == "career_coach"
        assert data["task_type"] == "career_path_analysis"
        assert data["result"] == {"paths": ["backend", "full-stack"]}
        assert data["error"] is None
        assert data["created_at"] == created.isoformat()
        assert data["updated_at"] == updated.isoformat()

    def test_to_dict_has_only_the_public_fields(self):
        """``to_dict`` returns the eight public keys and no clock field."""
        record = TaskRecord(task_id="task-1", status="pending")

        assert set(record.to_dict()) == {
            "task_id",
            "status",
            "agent",
            "task_type",
            "result",
            "error",
            "created_at",
            "updated_at",
        }


class TestTaskStore:
    """Tests for the ``TaskStore`` class."""

    def test_save_and_get_record(self):
        """A saved record should be retrievable by task ID."""
        store = TaskStore()
        store.save(
            "task-1",
            status="completed",
            agent="career_coach",
            task_type="career_path_analysis",
            result={"analysis": "test"},
        )

        record = store.get("task-1")

        assert record is not None
        assert record.task_id == "task-1"
        assert record.status == "completed"
        assert record.agent == "career_coach"
        assert record.task_type == "career_path_analysis"
        assert record.result == {"analysis": "test"}
        assert record.error is None

    def test_get_unknown_record_returns_none(self):
        """Retrieving an unknown task ID should return ``None``."""
        store = TaskStore()
        assert store.get("missing-task") is None

    def test_save_updates_existing_record(self):
        """Saving the same task ID again should update the record in place."""
        store = TaskStore()
        store.save("task-1", status="pending", agent="career_coach")
        store.save(
            "task-1",
            status="completed",
            result={"analysis": "done"},
            error="old error should be replaced only when provided",
        )

        record = store.get("task-1")

        assert record is not None
        assert record.status == "completed"
        assert record.agent == "career_coach"
        assert record.result == {"analysis": "done"}
        # Existing error should be preserved because the second save did not pass error.
        assert record.error == "old error should be replaced only when provided"
        assert record.updated_at >= record.created_at

    def test_save_preserves_existing_error_when_not_provided(self):
        """When ``error`` is omitted on update, the previous error is kept."""
        store = TaskStore()
        store.save("task-1", status="failed", error="boom")
        store.save("task-1", status="completed", result={"ok": True})

        record = store.get("task-1")
        assert record is not None
        assert record.status == "completed"
        # Error was not supplied, so the existing value is retained.
        assert record.error == "boom"

    def test_record_lives_until_the_ttl(self, fake_clock: FakeClock):
        """A record is kept at the TTL and removed just after it."""
        store = TaskStore(ttl_seconds=10)
        fake_clock.now = 1000.0
        store.save("task-1", status="completed", result={"ok": True})

        fake_clock.now = 1009.9
        assert store.get("task-1") is not None

        fake_clock.now = 1010.0
        assert store.get("task-1") is not None

        fake_clock.now = 1010.1
        assert store.get("task-1") is None

    def test_update_does_not_extend_the_ttl(self, fake_clock: FakeClock):
        """Saving the same task again does not restart its TTL."""
        store = TaskStore(ttl_seconds=10)
        fake_clock.now = 1000.0
        store.save("task-1", status="pending")

        fake_clock.now = 1009.0
        store.save("task-1", status="completed")

        fake_clock.now = 1010.1
        assert store.get("task-1") is None

    def test_wall_clock_jump_does_not_expire_records(
        self, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
    ):
        """A change of the wall clock does not expire a record."""
        store = TaskStore(ttl_seconds=10)
        fake_clock.now = 1000.0
        store.save("task-1", status="completed")

        real_now = datetime.now()

        class JumpedDatetime(datetime):
            """A datetime whose ``now`` is one day ahead."""

            @classmethod
            def now(cls, tz=None):
                """Return the real time plus one day.

                Args:
                    tz: Ignored, as in ``datetime.now``.

                Returns:
                    The shifted time.
                """
                return real_now + timedelta(days=1)

        monkeypatch.setattr(task_store_module, "datetime", JumpedDatetime)

        assert store.get("task-1") is not None

    def test_bounded_size_evicts_oldest(self):
        """When the size limit is reached, the oldest entry is evicted."""
        store = TaskStore(max_size=2)
        store.save("task-1", status="completed")
        store.save("task-2", status="completed")
        store.save("task-3", status="completed")

        assert store.get("task-1") is None
        assert store.get("task-2") is not None
        assert store.get("task-3") is not None

    def test_get_refreshes_recency(self):
        """Accessing a record should mark it as recently used."""
        store = TaskStore(max_size=2)
        store.save("task-1", status="completed")
        store.save("task-2", status="completed")

        # Access task-1 so it becomes the most recently used.
        store.get("task-1")

        # Adding a third record should now evict task-2, not task-1.
        store.save("task-3", status="completed")

        assert store.get("task-1") is not None
        assert store.get("task-2") is None
        assert store.get("task-3") is not None

    def test_save_with_zero_max_size_uses_minimum_of_one(self):
        """An invalid ``max_size`` should be clamped to one."""
        store = TaskStore(max_size=0)
        store.save("task-1", status="completed")
        store.save("task-2", status="completed")

        # Only one record should be retained.
        assert store.get("task-1") is None
        assert store.get("task-2") is not None

    def test_save_with_zero_ttl_uses_minimum_of_one_second(self):
        """An invalid ``ttl_seconds`` should be clamped to one second."""
        store = TaskStore(ttl_seconds=0)
        store.save("task-1", status="completed")

        # Should still exist immediately.
        assert store.get("task-1") is not None

    def test_negative_ttl_clamped(self):
        """A negative TTL should be clamped to a positive minimum."""
        store = TaskStore(ttl_seconds=-5)
        store.save("task-1", status="completed")
        assert store.get("task-1") is not None

    def test_store_is_thread_safe(self):
        """Concurrent saves and gets should not corrupt the store."""
        import threading

        store = TaskStore(max_size=50)
        errors = []

        def worker(start: int):
            try:
                for i in range(start, start + 100):
                    store.save(f"task-{i}", status="completed")
                    store.get(f"task-{i}")
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i * 100,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # The store should be at its bounded size after concurrent writes.
        assert len(store._records) == 50
