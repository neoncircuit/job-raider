"""Each letter from an LLM records its provider, so the Cloud badge stays true."""

from typing import Any
from unittest.mock import Mock

from src.generation.cover_letter_instructions import WhyInterestSpec
from src.generation.cover_letter_writer import CoverLetterWriter, GeneratedCoverLetter
from src.generation.selector import SelectionOutput
from src.llm.base import LLMResponse
from tests.unit.test_ranking_suite import job_with, profile_with

JOB = job_with("a", "Engineer", "Build Python services.")
PROFILE = profile_with(["Python"])
SELECTION = SelectionOutput(
    selected_projects=[],
    keywords_to_emphasize=[],
    key_achievements=[],
    summary_suggestion="",
    raw_response="",
)
DRAFT = GeneratedCoverLetter(
    content="Draft letter",
    highlighted_experiences=[],
    word_count=2,
    model_used="test-model",
    provider_used="ollama",
)


def writer_for(provider: str) -> CoverLetterWriter:
    """
    A writer whose router answers from one provider.

    Args:
        provider: The provider of each answer.

    Returns:
        The writer.
    """
    router: Any = Mock()
    router.generate.return_value = LLMResponse(
        content="A letter with enough words.",
        model="test-model",
        provider=provider,
        tokens_used=10,
        cost=0.0,
    )
    return CoverLetterWriter(router)


def test_write_records_the_provider() -> None:
    """A first draft names its provider."""
    result = writer_for("anthropic").write(JOB, PROFILE, SELECTION)
    assert result.provider_used == "anthropic"


def test_rewrite_records_the_provider_of_the_rewrite() -> None:
    """A rewrite names the provider that wrote it, not the provider of the draft."""
    result = writer_for("anthropic").rewrite(JOB, PROFILE, SELECTION, DRAFT, "Fix it")
    assert result.provider_used == "anthropic"


def test_why_interest_records_the_provider() -> None:
    """A short why-interest answer names its provider."""
    spec = WhyInterestSpec(min_n=3, max_n=4, unit="lines", matched_span="3-4 lines")
    result = writer_for("anthropic").write_why_interest_block(
        JOB, PROFILE, SELECTION, spec
    )
    assert result.model_used == "test-model"
    assert result.provider_used == "anthropic"


def test_a_template_letter_has_no_provider() -> None:
    """When the LLM fails, the template letter names no provider."""
    writer = writer_for("anthropic")
    writer.llm_router.generate.side_effect = RuntimeError("LLM unavailable")
    assert writer.write(JOB, PROFILE, SELECTION).provider_used is None
