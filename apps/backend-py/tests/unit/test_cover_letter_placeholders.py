"""Tests for the unfilled-placeholder check of cover letters."""

from typing import List

import pytest

from src.evaluation.suites.writer import LetterRow, pair_counts, summarize
from src.generation.cover_letter_grounding import flag_unfilled_placeholders
from src.generation.cover_letter_validator import (
    CoverLetterIssue,
    CoverLetterValidationResult,
    CoverLetterValidator,
    build_grounding_rewrite_critique,
    collect_hard_fail_issues,
)
from src.generation.cover_letter_writer import GeneratedCoverLetter
from src.generation.selector import SelectionOutput
from tests.unit.test_ranking_suite import job_with, profile_with

CLEAN = (
    "At Test Co, the Engineer role needs Python services, and I built them.\n\n"
    "I look forward to discussing how I can contribute to the team."
)


def validate(content: str) -> CoverLetterValidationResult:
    """
    Validate a letter for a small job and profile.

    Args:
        content: The letter.

    Returns:
        The validation result.
    """
    letter = GeneratedCoverLetter(
        content=content,
        highlighted_experiences=[],
        word_count=len(content.split()),
        model_used="test-model",
    )
    selection = SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="",
    )
    validator = CoverLetterValidator(llm_router=None, strict_mode=False)
    return validator.validate(
        letter,
        job_with("a", "Engineer", "Build Python services."),
        profile_with(["Python"]),
        selection,
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I admire [Company].", ["[Company]"]),
        ("In [Plant Disease Classifier] I trained", ["[Plant Disease Classifier]"]),
        (
            "[Research Engineer, Machine Learning]",
            ["[Research Engineer, Machine Learning]"],
        ),
        ("[Company] and [Role]", ["[Company]", "[Role]"]),
        ("[Company] and [Role] at [Company]", ["[Company]", "[Role]"]),
        ("[Role] at [Company]", ["[Role]", "[Company]"]),
        ("No brackets in this letter.", []),
        ("", []),
        ("A note [1] with one digit.", []),
        ("[]", []),
        ("[ab]", ["[ab]"]),
        ("[" + "a" * 80 + "]", ["[" + "a" * 80 + "]"]),
        ("[" + "a" * 81 + "]", []),
        ("[line one\nline two]", []),
        ("[[Company]]", ["[Company]"]),
    ],
)
def test_flag_unfilled_placeholders(text: str, expected: List[str]) -> None:
    """A token is one bracket pair around 2 to 80 characters on one line."""
    assert flag_unfilled_placeholders(text) == expected


def test_a_placeholder_is_a_hard_failure() -> None:
    """The letter is not valid, so the one rewrite runs."""
    result = validate(CLEAN + "\n\nI am eager to join [Company].")

    assert CoverLetterIssue.UNFILLED_PLACEHOLDER in result.issues
    assert CoverLetterIssue.UNFILLED_PLACEHOLDER in collect_hard_fail_issues(
        result.issues
    )
    assert result.is_valid is False
    assert result.recommendation == "reject"
    assert result.details["unfilled_placeholders"] == ["[Company]"]


def test_a_letter_without_placeholders_has_no_issue() -> None:
    """A clean letter gets no finding."""
    result = validate(CLEAN)

    assert CoverLetterIssue.UNFILLED_PLACEHOLDER not in result.issues
    assert result.details["unfilled_placeholders"] == []


def test_the_rewrite_critique_names_the_tokens() -> None:
    """The writer learns which tokens to replace."""
    result = validate(CLEAN + "\n\nJoin [Company] as [Role].")

    critique = build_grounding_rewrite_critique(result)

    assert "[Company], [Role]" in critique
    assert "plain text" in critique


def test_a_critique_without_tokens_has_no_placeholder_line() -> None:
    """Other hard failures do not get the placeholder instruction."""
    assert "placeholders" not in build_grounding_rewrite_critique(validate(CLEAN))


def test_the_writer_suite_counts_the_issue() -> None:
    """The first-draft rate reaches the report and each pair."""
    flagged = LetterRow(case_id="c", profile_id="p", sample=0, outcome="written")
    flagged.issues = ["unfilled_placeholder"]
    clean = LetterRow(case_id="c", profile_id="p", sample=1, outcome="written")
    rows = [flagged, clean]

    assert summarize(rows)["unfilled_placeholder_rate"] == 0.5
    assert pair_counts(rows)["c"]["flagged"]["unfilled_placeholder"] == 1
