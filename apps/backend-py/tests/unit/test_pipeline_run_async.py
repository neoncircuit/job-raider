"""
Tests for background pipeline runs in ``src/api/routes/pipeline.py``.

Before 2026-10-19, ``run_pipeline_async`` called the synchronous
``orchestrator.run()`` on the event loop. The API, status polls, and
WebSockets froze for the whole run, and only start and end events were
sent. A failed run was reported as "completed", and cancel did not stop the
run. These tests use a fake orchestrator, so they run no stages.
"""

import asyncio
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

from src.api.routes import pipeline as route
from src.models.pipeline_stage import PipelineStage
from src.pipeline.orchestrator import PipelineConfig, PipelineResult
from src.pipeline.stages import StageResult

PLANNED = [PipelineStage.SCRAPE, PipelineStage.DEDUPLICATE]
RUN_ID = "run_test"


def stage_result(stage: PipelineStage, success: bool = True) -> StageResult:
    """Build a stage result.

    Args:
        stage: Stage that produced the result.
        success: Whether the stage succeeded.

    Returns:
        A ``StageResult``.
    """
    return StageResult(
        stage_name=stage.value,
        success=success,
        data=[],
        metadata={},
        timestamp=datetime.now(),
        error_message=None if success else "scraper timed out",
    )


class FakeOrchestrator:
    """Stand-in for ``PipelineOrchestrator`` that runs hooks, not stages."""

    behavior: Dict[str, Any] = {}

    def __init__(self, config: Any, user_profile: Any) -> None:
        """Set up hook storage and an empty context.

        Args:
            config: Pipeline configuration.
            user_profile: User profile.
        """
        self.before: Dict[PipelineStage, List[Callable]] = {}
        self.after: Dict[PipelineStage, List[Callable]] = {}
        self.context = type(
            "Context", (), {"rag_ranked_listings": [], "scored_listings": []}
        )()

    def plan_stages(
        self, start_from: PipelineStage, stop_at: Optional[PipelineStage]
    ) -> List[PipelineStage]:
        """Return the fixed test plan.

        Args:
            start_from: First stage.
            stop_at: Last stage.

        Returns:
            The planned stages.
        """
        return list(PLANNED)

    def register_before_hook(self, stage: PipelineStage, hook: Callable) -> None:
        """Store a before-stage hook.

        Args:
            stage: Stage for the hook.
            hook: Hook to call.
        """
        self.before.setdefault(stage, []).append(hook)

    def register_after_hook(self, stage: PipelineStage, hook: Callable) -> None:
        """Store an after-stage hook.

        Args:
            stage: Stage for the hook.
            hook: Hook to call.
        """
        self.after.setdefault(stage, []).append(hook)

    def run(
        self,
        stop_at: Optional[PipelineStage] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        run_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> PipelineResult:
        """Call the hooks for each planned stage like the real orchestrator.

        Args:
            stop_at: Last stage.
            should_stop: Cancel check before each stage.

        Returns:
            Result driven by ``FakeOrchestrator.behavior``.
        """
        self.behavior["thread"] = threading.get_ident()
        fail_stage = self.behavior.get("fail_stage")
        results: Dict[str, StageResult] = {}
        completed: List[str] = []
        cancelled = False
        for stage in PLANNED:
            if should_stop is not None and should_stop():
                cancelled = True
                break
            for hook in self.before.get(stage, []):
                hook(stage)
            time.sleep(self.behavior.get("stage_seconds", 0))
            result = stage_result(stage, success=stage != fail_stage)
            results[stage.value] = result
            if not result.success:
                break
            completed.append(stage.value)
            for hook in self.after.get(stage, []):
                hook(stage, result)
        now = datetime.now()
        return PipelineResult(
            success=not cancelled and len(completed) == len(PLANNED),
            stages_completed=completed,
            stage_results=results,
            start_time=now,
            end_time=now,
            metadata={"cancelled": cancelled},
        )


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> List[Tuple[str, Tuple[Any, ...]]]:
    """Replace the orchestrator, shortlist I/O, and broadcasts with fakes.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        List that collects each broadcast as (name, arguments).
    """
    recorded: List[Tuple[str, Tuple[Any, ...]]] = []

    def recorder(name: str) -> Callable[..., Any]:
        """Build an async recorder for one broadcast method.

        Args:
            name: Broadcast method name.

        Returns:
            Async function that records its arguments.
        """

        async def record(*args: Any) -> None:
            """Record one broadcast.

            Args:
                *args: Broadcast arguments.
            """
            recorded.append((name, args))

        return record

    for name in [
        "send_message",
        "broadcast_stage_started",
        "broadcast_stage_completed",
        "broadcast_stage_progress",
        "broadcast_pipeline_complete",
        "broadcast_pipeline_failed",
    ]:
        monkeypatch.setattr(route.manager, name, recorder(name))

    FakeOrchestrator.behavior = {}
    monkeypatch.setattr(route, "PipelineOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(route, "enrich_shortlist_descriptions", lambda _src: 0)
    monkeypatch.setattr(route, "save_latest_shortlist", lambda **_kw: None)
    monkeypatch.setattr(
        route,
        "pipeline_runs",
        {RUN_ID: {"run_id": RUN_ID, "status": "pending", "created_at": datetime.now()}},
    )
    return recorded


def run_pipeline() -> None:
    """Run ``run_pipeline_async`` for the test run on a new event loop."""
    config = PipelineConfig(keywords=["python"], locations=["Singapore"])
    asyncio.run(route.run_pipeline_async(RUN_ID, config, profile=None))


def test_stages_run_in_a_worker_thread_and_report_in_order(
    events: List[Tuple[str, Tuple[Any, ...]]],
) -> None:
    """Stage events arrive in order, and progress reaches 100.

    Args:
        events: Recorded broadcasts.
    """
    run_pipeline()

    assert FakeOrchestrator.behavior["thread"] != threading.get_ident()
    summary = [
        (name, args[1] if name.startswith("broadcast_stage") else None)
        for name, args in events
        if name != "send_message"
    ]
    assert summary == [
        ("broadcast_stage_started", "scrape"),
        ("broadcast_stage_completed", "scrape"),
        ("broadcast_stage_progress", "scrape"),
        ("broadcast_stage_started", "deduplicate"),
        ("broadcast_stage_completed", "deduplicate"),
        ("broadcast_stage_progress", "deduplicate"),
        ("broadcast_pipeline_complete", None),
    ]
    progress = [args[2] for name, args in events if name == "broadcast_stage_progress"]
    assert progress == [50, 100]

    run = route.pipeline_runs[RUN_ID]
    assert run["status"] == "completed"
    assert run["stages_planned"] == ["scrape", "deduplicate"]
    assert run["stages_completed"] == ["scrape", "deduplicate"]
    assert run["stage_progress"] == 100


def test_event_loop_stays_responsive_during_a_run(
    events: List[Tuple[str, Tuple[Any, ...]]],
) -> None:
    """Other coroutines keep running while a stage blocks its thread.

    Args:
        events: Recorded broadcasts.
    """
    FakeOrchestrator.behavior["stage_seconds"] = 0.15
    ticks = 0

    async def ticker(stop: asyncio.Event) -> None:
        """Count loop turns until the run ends.

        Args:
            stop: Event set when the run ends.
        """
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    async def main() -> None:
        """Run the pipeline and the ticker together."""
        stop = asyncio.Event()
        config = PipelineConfig(keywords=["python"], locations=["Singapore"])
        tick_task = asyncio.create_task(ticker(stop))
        await route.run_pipeline_async(RUN_ID, config, profile=None)
        stop.set()
        await tick_task

    asyncio.run(main())

    # Two stages block for 0.3 s in total. A blocked loop would tick about once.
    assert ticks >= 10


def test_failed_result_marks_the_run_failed_with_the_stage_error(
    events: List[Tuple[str, Tuple[Any, ...]]],
) -> None:
    """A run with success=False is "failed", not "completed".

    Args:
        events: Recorded broadcasts.
    """
    FakeOrchestrator.behavior["fail_stage"] = PipelineStage.DEDUPLICATE

    run_pipeline()

    run = route.pipeline_runs[RUN_ID]
    assert run["status"] == "failed"
    assert run["error"] == "Stage 'deduplicate' failed: scraper timed out"
    failed = [args for name, args in events if name == "broadcast_pipeline_failed"]
    assert failed == [(RUN_ID, run["error"], "deduplicate")]
    assert not [name for name, _ in events if name == "broadcast_pipeline_complete"]


def test_cancel_during_a_stage_stops_before_the_next_stage(
    events: List[Tuple[str, Tuple[Any, ...]]],
) -> None:
    """A cancel during the first stage stops the run before the second.

    Args:
        events: Recorded broadcasts.
    """
    original_before = route._attach_stage_events

    def attach_and_cancel(orchestrator: Any, *args: Any) -> None:
        """Attach the real hooks, then cancel the run when scrape starts.

        Args:
            orchestrator: Orchestrator for the run.
            *args: Remaining ``_attach_stage_events`` arguments.
        """
        original_before(orchestrator, *args)

        def cancel(_stage: PipelineStage) -> None:
            """Simulate DELETE /api/pipeline/<run_id> during the stage.

            Args:
                _stage: Stage that is starting.
            """
            route.pipeline_runs[RUN_ID]["status"] = "cancelled"

        orchestrator.register_before_hook(PipelineStage.SCRAPE, cancel)

    route._attach_stage_events = attach_and_cancel
    try:
        run_pipeline()
    finally:
        route._attach_stage_events = original_before

    run = route.pipeline_runs[RUN_ID]
    assert run["status"] == "cancelled"
    assert run["stages_completed"] == ["scrape"]
    started = [args[1] for name, args in events if name == "broadcast_stage_started"]
    assert started == ["scrape"]
    assert not [name for name, _ in events if name == "broadcast_pipeline_complete"]
