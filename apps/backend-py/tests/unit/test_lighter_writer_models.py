"""
Tests for the lighter-writer comparison (lighter-writer task).

The writer and resume suites must accept ``llama3.2:3b``, and the resume suite
must use the model of the run without a change to the saved Settings: the
run's own router gets the model on its ``resume_writing`` route, so the CV
writer and the polish step both use it. Fake routers, no Ollama.
"""

from types import SimpleNamespace
from typing import Any, Optional

import pytest

from src.evaluation.suites.resume import local_resume_writer
from src.evaluation.suites.writer import WRITER_MODELS, check_model
from src.llm.router import TaskType

SAVED_MODEL = "qwen2.5:7b"
RUN_MODEL = "qwen2.5:3b"


def fake_router(installed: bool = True) -> SimpleNamespace:
    """
    A router whose saved ``resume_writing`` route uses ``SAVED_MODEL``.

    Args:
        installed: Whether an override model counts as installed in Ollama.

    Returns:
        The fake router with ``routes`` and ``resolve_primary_model``.
    """
    route = SimpleNamespace(
        primary_provider="ollama",
        primary_model=SAVED_MODEL,
        fallback_provider="ollama",
    )

    def resolve(task: Any, override: Optional[str] = None) -> tuple:
        """
        Resolve like ``LLMRouter.resolve_primary_model``.

        Args:
            task: The task type.
            override: The one-shot model name.

        Returns:
            ``(provider, model)``: the override when it is installed.
        """
        if override and installed:
            return route.primary_provider, override
        return route.primary_provider, route.primary_model

    return SimpleNamespace(
        routes={TaskType.RESUME_WRITING: route}, resolve_primary_model=resolve
    )


def test_llama_3_2_3b_is_on_the_allow_list() -> None:
    """``llama3.2:3b`` passes the model check of both suites."""
    assert "llama3.2:3b" in WRITER_MODELS
    check_model("llama3.2:3b")


def test_a_model_off_the_allow_list_is_still_refused() -> None:
    """A model that is not on the list fails before any call."""
    with pytest.raises(ValueError, match="allow-list"):
        check_model("qwen3.5:9b")


def test_resume_suite_uses_the_run_model_without_a_settings_change() -> None:
    """The run model goes on the run's route; the saved model does not block it."""
    router = fake_router()

    local_resume_writer(router, RUN_MODEL)

    route = router.routes[TaskType.RESUME_WRITING]
    assert route.primary_model == RUN_MODEL
    assert route.fallback_provider == "none"


def test_resume_suite_refuses_a_model_that_is_not_installed() -> None:
    """When Ollama does not have the model, the run stops before any call."""
    router = fake_router(installed=False)

    with pytest.raises(ValueError, match=RUN_MODEL):
        local_resume_writer(router, RUN_MODEL)

    route = router.routes[TaskType.RESUME_WRITING]
    assert route.primary_model == SAVED_MODEL
    assert route.fallback_provider == "ollama"
