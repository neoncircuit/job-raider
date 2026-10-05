"""
Job Raider - In-memory log buffer.

Keeps the most recent log records in a fixed-size ring so the app can show
them without ``docker logs``. Secret-like values are redacted when a record
is stored, so secrets never sit in the buffer.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

DEFAULT_CAPACITY = 2000
REDACTED = "[REDACTED]"

_SECRET_ENV_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "DSN")
_MIN_SECRET_LEN = 8

_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
)
_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b([\w-]*(?:api[_-]?key|token(?!s)|secret|password|passwd|authorization)"
    r"[\w-]*)(\s*[:=]\s*)(['\"]?)[^\s'\",}]+"
)


def _env_secrets() -> List[str]:
    """Collect secret-looking environment values for exact redaction.

    Returns:
        Values of variables whose names suggest a secret, longest first.
    """
    values = {
        value
        for name, value in os.environ.items()
        if any(hint in name.upper() for hint in _SECRET_ENV_HINTS)
        and len(value) >= _MIN_SECRET_LEN
    }
    return sorted(values, key=len, reverse=True)


def redact(text: str, env_secrets: Optional[List[str]] = None) -> str:
    """Replace secret-like values in a log message.

    Args:
        text: Raw log message.
        env_secrets: Exact values to hide; defaults to secret-like env values.

    Returns:
        The message with secrets replaced by ``[REDACTED]``.
    """
    for secret in env_secrets if env_secrets is not None else _env_secrets():
        text = text.replace(secret, REDACTED)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return _KEY_VALUE_PATTERN.sub(rf"\1\2\3{REDACTED}", text)


class RingBufferHandler(logging.Handler):
    """Logging handler that keeps the last N records in memory.

    Attributes:
        capacity: Maximum number of records kept.
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        """Create the handler.

        Args:
            capacity: Maximum number of records kept.
        """
        super().__init__(level=logging.INFO)
        self.capacity = capacity
        self._records: Deque[Dict[str, Any]] = deque(maxlen=capacity)
        self._seq = 0
        self._buffer_lock = threading.Lock()
        self._env_secrets = _env_secrets()

    def emit(self, record: logging.LogRecord) -> None:
        """Store a redacted copy of the record.

        Args:
            record: Record from the logging framework.
        """
        try:
            message = record.getMessage()
            if record.exc_info:
                message = (
                    f"{message}\n{logging.Formatter().formatException(record.exc_info)}"
                )
            entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": redact(message, self._env_secrets),
            }
            with self._buffer_lock:
                self._seq += 1
                entry["seq"] = self._seq
                self._records.append(entry)
        except Exception:  # noqa: BLE001 - logging must never raise
            self.handleError(record)

    def query(
        self,
        min_level: str = "INFO",
        component: str = "",
        search: str = "",
        after: int = 0,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Return filtered records, oldest first.

        Args:
            min_level: Lowest level to include (INFO, WARNING, ERROR, CRITICAL).
            component: Logger-name prefix, for example ``job_raider.pipeline``.
            search: Case-insensitive text to find in the message or logger.
            after: Only records with a sequence number above this value.
            limit: Maximum records returned (newest kept when trimmed).

        Returns:
            Dict with ``records``, ``latest_seq``, and ``capacity``.
        """
        threshold = logging.getLevelName(min_level.upper())
        if not isinstance(threshold, int):
            threshold = logging.INFO
        needle = search.lower()
        with self._buffer_lock:
            snapshot = list(self._records)
            latest = self._seq
        matched = [
            r
            for r in snapshot
            if r["seq"] > after
            and logging.getLevelName(r["level"]) >= threshold
            and r["logger"].startswith(component)
            and (
                not needle
                or needle in r["message"].lower()
                or needle in r["logger"].lower()
            )
        ]
        return {
            "records": matched[-limit:] if limit > 0 else [],
            "latest_seq": latest,
            "capacity": self.capacity,
        }

    def loggers(self) -> List[str]:
        """List distinct logger names currently in the buffer.

        Returns:
            Sorted logger names.
        """
        with self._buffer_lock:
            return sorted({r["logger"] for r in self._records})


_handler: Optional[RingBufferHandler] = None


def get_log_buffer() -> RingBufferHandler:
    """Return the process-wide buffer, creating it on first use.

    Returns:
        The shared ``RingBufferHandler``.
    """
    global _handler
    if _handler is None:
        _handler = RingBufferHandler()
    return _handler


def _reaches_root(logger: logging.Logger) -> bool:
    """Check whether a logger's records propagate up to the root logger.

    Args:
        logger: Logger to check.

    Returns:
        False when the logger or an ancestor has ``propagate`` turned off.
    """
    current: Optional[logging.Logger] = logger
    while current is not None and current.parent is not None:
        if not current.propagate:
            return False
        current = current.parent
    return True


def install_log_buffer() -> RingBufferHandler:
    """Attach the buffer to the root logger, and to ``uvicorn.error`` if needed.

    Uvicorn stops its loggers from propagating, so ``uvicorn.error`` gets its
    own attachment only when its records cannot reach root (no duplicates).
    The root level is lowered to INFO when it is higher. The root logger has
    no other handlers in the API process, so console output does not change.

    Returns:
        The shared ``RingBufferHandler``.
    """
    handler = get_log_buffer()
    root = logging.getLogger()
    if handler not in root.handlers:
        root.addHandler(handler)
    uvicorn_error = logging.getLogger("uvicorn.error")
    if not _reaches_root(uvicorn_error) and handler not in uvicorn_error.handlers:
        uvicorn_error.addHandler(handler)
    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    return handler
