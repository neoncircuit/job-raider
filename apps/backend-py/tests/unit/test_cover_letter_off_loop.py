"""
Prove cover-letter generation does not block the asyncio event loop.

Step 2.5: ``generate_cover_letter_for_profile`` must await
``asyncio.to_thread(generate_cover_letter_sync, ...)``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any
from unittest.mock import patch

from src.generation import cover_letter_service as svc


def test_cover_letter_runs_in_worker_thread() -> None:
    """Sync body runs on a different thread than the caller."""
    main_thread = threading.get_ident()
    seen: dict[str, Any] = {}

    def fake_sync(*_args: Any, **_kwargs: Any) -> Any:
        """Record the worker thread id and return a stub.

        Returns:
            Stub success payload.
        """
        seen["thread"] = threading.get_ident()
        time.sleep(0.05)
        return {"ok": True}

    async def main() -> Any:
        """Await the async wrapper.

        Returns:
            Result from the patched sync function.
        """
        with patch.object(svc, "generate_cover_letter_sync", side_effect=fake_sync):
            return await svc.generate_cover_letter_for_profile(
                object(),  # type: ignore[arg-type]
                object(),  # type: ignore[arg-type]
            )

    result = asyncio.run(main())
    assert result == {"ok": True}
    assert "thread" in seen
    assert seen["thread"] != main_thread


def test_event_loop_stays_responsive_during_cover_letter() -> None:
    """Other coroutines keep running while cover-letter sync blocks its thread."""

    def fake_sync(*_args: Any, **_kwargs: Any) -> Any:
        """Block the worker thread briefly.

        Returns:
            Stub success payload.
        """
        time.sleep(0.2)
        return {"ok": True}

    ticks = 0

    async def ticker(stop: asyncio.Event) -> None:
        """Count loop turns until generation ends.

        Args:
            stop: Event set when generation finishes.
        """
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    async def main() -> None:
        """Run generation and a ticker together."""
        stop = asyncio.Event()
        tick_task = asyncio.create_task(ticker(stop))
        with patch.object(svc, "generate_cover_letter_sync", side_effect=fake_sync):
            await svc.generate_cover_letter_for_profile(
                object(),  # type: ignore[arg-type]
                object(),  # type: ignore[arg-type]
            )
        stop.set()
        await tick_task

    asyncio.run(main())
    # A blocked event loop would tick about once during 0.2 s of sync sleep.
    assert ticks >= 10
