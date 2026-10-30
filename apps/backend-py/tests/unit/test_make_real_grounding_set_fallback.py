"""Tests for the fallback guards of the real-letter generator (Step 3.2, MH-A3)."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import make_real_grounding_set as gen
from src.generation.selector import SelectionOutput
from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile


def selection(raw_response: str) -> SelectionOutput:
    """Build a selection with a given raw model answer.

    Args:
        raw_response: The raw answer; empty means the rule-based fallback.

    Returns:
        A selection.
    """
    return SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response=raw_response,
    )


class FakeSelector:
    """Selector stand-in that returns the class attribute ``result``."""

    result = selection("{}")

    def __init__(self, llm_router: Any) -> None:
        """Accept the router.

        Args:
            llm_router: Not used.
        """

    def select(self, job: JobListing, profile: UserProfile) -> SelectionOutput:
        """Return the fixed selection.

        Args:
            job: Not used.
            profile: Not used.

        Returns:
            ``FakeSelector.result``.
        """
        return FakeSelector.result


@pytest.fixture
def fake_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the app's selector and router with stand-ins.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr("src.generation.selector.ResumeSelector", FakeSelector)
    monkeypatch.setattr("src.llm.router.create_router", lambda prefer_local: None)


def test_a_fallback_selection_stops_the_run(
    fake_selector: None,
    monkeypatch: pytest.MonkeyPatch,
    sample_job_listing: JobListing,
    sample_user_profile: UserProfile,
) -> None:
    """An empty raw answer means the rule-based fallback; the run stops."""
    monkeypatch.setattr(FakeSelector, "result", selection(""))

    with pytest.raises(RuntimeError, match="rule-based fallback"):
        gen.select_with_app(sample_job_listing, sample_user_profile)


def test_a_model_selection_is_returned(
    fake_selector: None,
    monkeypatch: pytest.MonkeyPatch,
    sample_job_listing: JobListing,
    sample_user_profile: UserProfile,
) -> None:
    """A selection with a model answer is returned unchanged."""
    answer = selection('{"selected_projects": []}')
    monkeypatch.setattr(FakeSelector, "result", answer)

    assert gen.select_with_app(sample_job_listing, sample_user_profile) is answer


@pytest.mark.parametrize("model", ["template_fallback", "fallback"])
def test_a_fallback_letter_stops_the_run(
    monkeypatch: pytest.MonkeyPatch,
    sample_job_listing: JobListing,
    sample_user_profile: UserProfile,
    model: str,
) -> None:
    """A letter from the writer's fallback stops the run."""
    response = SimpleNamespace(
        cover_letter={"content": "Dear team, thank you.", "model_used": model}
    )
    monkeypatch.setattr(
        "src.generation.cover_letter_service.generate_cover_letter_sync",
        lambda job, profile, selection: response,
    )

    with pytest.raises(RuntimeError, match="template fallback"):
        gen.write_with_app(sample_job_listing, sample_user_profile, selection("{}"))


def test_a_model_letter_is_returned(
    monkeypatch: pytest.MonkeyPatch,
    sample_job_listing: JobListing,
    sample_user_profile: UserProfile,
) -> None:
    """A letter that a model wrote is returned."""
    response = SimpleNamespace(
        cover_letter={"content": "Dear team, thank you.", "model_used": "qwen2.5:7b"}
    )
    monkeypatch.setattr(
        "src.generation.cover_letter_service.generate_cover_letter_sync",
        lambda job, profile, selection: response,
    )

    letter = gen.write_with_app(
        sample_job_listing, sample_user_profile, selection("{}")
    )

    assert letter == "Dear team, thank you."


def test_main_writes_nothing_after_a_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sample_job_listing: JobListing,
    sample_user_profile: UserProfile,
) -> None:
    """main stops with exit code 1 and writes no letters after a fallback."""
    item = dict(
        sample_job_listing.model_dump(mode="json"),
        description="We build payment services in Python. " * 10,
    )
    shortlist = tmp_path / "shortlist.json"
    shortlist.write_text(json.dumps({"jobs": [item]}), encoding="utf-8")
    monkeypatch.setattr(gen, "loaded_models", lambda url: [])
    monkeypatch.setattr(gen, "unload_models", lambda url: None)
    monkeypatch.setattr(gen, "quiet_app_logs", lambda: {})
    monkeypatch.setattr(gen, "load_active_profile", lambda path: sample_user_profile)

    def fail(job: JobListing, profile: UserProfile) -> SelectionOutput:
        """Fail like a fallback selection.

        Args:
            job: Not used.
            profile: Not used.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("the selector used its rule-based fallback")

    monkeypatch.setattr(gen, "select_with_app", fail)
    out = tmp_path / "grounding_real"

    code = gen.main(["--out", str(out), "--shortlist", str(shortlist)])

    assert code == 1
    assert not (out / "letters.jsonl").exists()
