"""
In-memory task-result store for the multi-agent system.

Provides bounded, TTL-scoped storage so that completed and failed agent task
results can be retrieved asynchronously by clients without keeping every result
in memory indefinitely.
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass
class TaskRecord:
    """Stored record for a single agent task."""

    task_id: str
    status: str
    agent: Optional[str] = None
    task_type: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the record to a dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "agent": self.agent,
            "task_type": self.task_type,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class TaskStore:
    """
    Thread-safe in-memory store for agent task results.

    The store enforces a maximum entry count and a time-to-live (TTL) so that
    long-running processes do not grow unbounded. When the size limit is
    reached, the oldest entries are evicted. Accessing an expired entry removes
    it and returns ``None``.

    Args:
        max_size: Maximum number of task records to retain.
        ttl_seconds: How long a record remains retrievable after creation.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600.0):
        self.max_size = max(max_size, 1)
        self.ttl = timedelta(seconds=max(ttl_seconds, 1.0))
        self._records: OrderedDict[str, TaskRecord] = OrderedDict()
        self._lock = threading.Lock()

    def save(
        self,
        task_id: str,
        status: str,
        agent: Optional[str] = None,
        task_type: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Persist or update a task record.

        Args:
            task_id: Unique task identifier.
            status: One of ``pending``, ``completed``, or ``failed``.
            agent: Optional agent identifier that owns the task.
            task_type: Optional task type label.
            result: Optional result payload for completed tasks.
            error: Optional error message for failed tasks.
        """
        now = datetime.now()
        with self._lock:
            self._evict_expired(now)

            existing = self._records.get(task_id)
            if existing is not None:
                existing.status = status
                existing.agent = agent or existing.agent
                existing.task_type = task_type or existing.task_type
                existing.result = result if result is not None else existing.result
                existing.error = error if error is not None else existing.error
                existing.updated_at = now
                # Move to the end to mark as recently used.
                self._records.move_to_end(task_id)
                return

            record = TaskRecord(
                task_id=task_id,
                status=status,
                agent=agent,
                task_type=task_type,
                result=result,
                error=error,
                created_at=now,
                updated_at=now,
            )

            if len(self._records) >= self.max_size:
                self._records.popitem(last=False)

            self._records[task_id] = record

    def get(self, task_id: str) -> Optional[TaskRecord]:
        """
        Retrieve a task record by ID.

        Args:
            task_id: Unique task identifier.

        Returns:
            The task record, or ``None`` if it does not exist or has expired.
        """
        now = datetime.now()
        with self._lock:
            self._evict_expired(now)
            record = self._records.get(task_id)
            if record is not None:
                self._records.move_to_end(task_id)
            return record

    def _evict_expired(self, now: datetime) -> None:
        """Remove records older than the configured TTL."""
        cutoff = now - self.ttl
        expired = [
            task_id
            for task_id, record in self._records.items()
            if record.created_at < cutoff
        ]
        for task_id in expired:
            del self._records[task_id]
