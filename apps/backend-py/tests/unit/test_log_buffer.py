"""
Job Raider - In-memory log buffer tests.

Covers the ring cap, filters, polling cursor, redaction, survival across
``setup_basic_logging`` (called when a pipeline starts), and ``GET /api/logs``.
"""

import logging
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from src.utils import log_buffer
from src.utils.log_buffer import REDACTED, RingBufferHandler, redact
from src.utils.logger import setup_basic_logging


def _log(handler: RingBufferHandler, name: str, level: int, msg: str) -> None:
    """Send one record straight to a handler.

    Args:
        handler: Target handler.
        name: Logger name for the record.
        level: Log level.
        msg: Message text.
    """
    handler.handle(logging.LogRecord(name, level, __file__, 1, msg, None, None))


@pytest.fixture
def installed() -> Iterator[RingBufferHandler]:
    """Install a fresh shared buffer on the root logger, then remove it.

    Yields:
        The installed handler.
    """
    root = logging.getLogger()
    old_level = root.level
    log_buffer._handler = None
    handler = log_buffer.install_log_buffer()
    yield handler
    for logger in (root, logging.getLogger("uvicorn.error")):
        if handler in logger.handlers:
            logger.removeHandler(handler)
    root.setLevel(old_level)
    log_buffer._handler = None


class TestRingBuffer:
    """Capacity, filters, and cursor."""

    def test_capacity_keeps_newest(self) -> None:
        """Old records fall out when the ring is full."""
        handler = RingBufferHandler(capacity=3)
        for i in range(5):
            _log(handler, "job_raider", logging.INFO, f"m{i}")
        result = handler.query()
        assert [r["message"] for r in result["records"]] == ["m2", "m3", "m4"]
        assert result["latest_seq"] == 5

    def test_debug_is_not_stored(self) -> None:
        """The handler level is INFO."""
        handler = RingBufferHandler()
        _log(handler, "job_raider", logging.DEBUG, "noise")
        assert handler.query()["records"] == []

    def test_filters(self) -> None:
        """Level, component prefix, and text filters combine."""
        handler = RingBufferHandler()
        _log(handler, "job_raider.pipeline", logging.INFO, "stage scrape done")
        _log(handler, "job_raider.pipeline", logging.ERROR, "stage failed")
        _log(handler, "job_raider.llm", logging.ERROR, "ollama timeout")

        assert len(handler.query(min_level="ERROR")["records"]) == 2
        pipeline = handler.query(component="job_raider.pipeline")["records"]
        assert {r["message"] for r in pipeline} == {"stage scrape done", "stage failed"}
        found = handler.query(search="OLLAMA")["records"]
        assert [r["logger"] for r in found] == ["job_raider.llm"]

    def test_after_cursor_and_limit(self) -> None:
        """``after`` returns only newer records; ``limit`` keeps the newest."""
        handler = RingBufferHandler()
        for i in range(4):
            _log(handler, "job_raider", logging.INFO, f"m{i}")
        assert [r["message"] for r in handler.query(after=2)["records"]] == [
            "m2",
            "m3",
        ]
        assert [r["message"] for r in handler.query(limit=1)["records"]] == ["m3"]

    def test_exception_text_included(self) -> None:
        """Tracebacks are part of the stored message."""
        handler = RingBufferHandler()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = logging.LogRecord(
                "job_raider", logging.ERROR, __file__, 1, "failed", None, sys.exc_info()
            )
        handler.handle(record)
        assert "ValueError: boom" in handler.query()["records"][0]["message"]


class TestRedaction:
    """Secret-like values never reach the buffer."""

    @pytest.mark.parametrize(
        "raw",
        [
            "using key sk-ant-api03-abcdefghijklmnop",
            "openai sk-abcdefghijklmnopqrstuv",
            "gemini AIzaSyA1234567890abcdefghijk",
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload",
            "github ghp_abcdefghijklmnopqrstuvwxyz12",
        ],
    )
    def test_known_formats(self, raw: str) -> None:
        """Common provider key formats are hidden."""
        out = redact(raw, env_secrets=[])
        assert REDACTED in out
        assert "abcdefghijklmnop" not in out and "1234567890" not in out

    def test_key_value_pairs(self) -> None:
        """``name=value`` pairs for secret-like names hide the value only."""
        out = redact("api_key=hunter2xyz password: 'pa55word' X-API-Key=abc123", [])
        assert "hunter2xyz" not in out and "pa55word" not in out
        assert "abc123" not in out
        assert "api_key=" in out

    def test_token_counts_are_kept(self) -> None:
        """Token usage counters are not secrets."""
        text = "max_tokens=4096 tokens: 12+3=15"
        assert redact(text, []) == text

    def test_env_values(self) -> None:
        """Exact values of secret env vars are hidden anywhere in the text."""
        out = redact("connecting with myS3cretValue!", ["myS3cretValue!"])
        assert out == f"connecting with {REDACTED}"

    def test_handler_redacts_env_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The handler reads secret env values at creation."""
        monkeypatch.setenv("RAPIDAPI_KEY", "rapid-secret-0001")
        handler = RingBufferHandler()
        _log(handler, "job_raider", logging.WARNING, "header rapid-secret-0001 sent")
        assert "rapid-secret-0001" not in handler.query()["records"][0]["message"]


class TestInstall:
    """Attachment to the logging tree."""

    def test_records_from_app_loggers(self, installed: RingBufferHandler) -> None:
        """INFO from an app logger reaches the buffer after install."""
        logging.getLogger("job_raider.pipeline").info("hello buffer")
        messages = [r["message"] for r in installed.query()["records"]]
        assert "hello buffer" in messages

    def test_survives_pipeline_logging_setup(
        self, installed: RingBufferHandler
    ) -> None:
        """``setup_basic_logging`` (run by the orchestrator) keeps the buffer."""
        setup_basic_logging(console_output=False)
        assert installed in logging.getLogger().handlers
        logging.getLogger("job_raider").warning("after setup")
        assert "after setup" in [r["message"] for r in installed.query()["records"]]

    def test_install_is_idempotent(self, installed: RingBufferHandler) -> None:
        """A second install does not add a second handler."""
        log_buffer.install_log_buffer()
        assert logging.getLogger().handlers.count(installed) == 1


class TestLogsRoute:
    """``GET /api/logs``."""

    def test_returns_filtered_records(
        self, client: TestClient, installed: RingBufferHandler
    ) -> None:
        """The route applies filters and lists logger names."""
        logging.getLogger("job_raider.pipeline").error("route check failed")
        logging.getLogger("job_raider.llm").info("route check info")

        data = client.get(
            "/api/logs", params={"level": "ERROR", "q": "route check"}
        ).json()
        assert [r["message"] for r in data["records"]] == ["route check failed"]
        assert "job_raider.llm" in data["loggers"]
        assert data["capacity"] == log_buffer.DEFAULT_CAPACITY

    def test_rejects_bad_level(self, client: TestClient) -> None:
        """Unknown levels are a validation error."""
        assert client.get("/api/logs", params={"level": "TRACE"}).status_code == 422
