"""
Unit tests for Phase C application-instruction detection helpers.
"""

from __future__ import annotations

from src.generation.cover_letter_instructions import (
    count_length_units,
    detect_application_instructions,
    inclusion_present_in_text,
    length_within_spec,
    resolve_inclusion_urls,
)


def test_detect_why_interest_three_to_four_lines() -> None:
    """
    Detect a classic 3-4 lines mission-interest instruction.
    """
    jd = (
        "Please send your CV plus 3-4 lines on why this mission excites you. "
        "We build document intelligence products in Singapore."
    )
    detected = detect_application_instructions(jd)
    assert detected.why_interest is not None
    assert detected.why_interest.min_n == 3
    assert detected.why_interest.max_n == 4
    assert detected.why_interest.unit == "lines"


def test_detect_why_interest_about_fifty_words() -> None:
    """
    Detect word-count interest asks (not only line counts).

    Approx/bare singles stay exact targets (min=max).
    """
    jd = (
        "In about 50 words, tell us why our company mission interests you "
        "and how you would contribute."
    )
    detected = detect_application_instructions(jd)
    assert detected.why_interest is not None
    assert detected.why_interest.unit == "words"
    assert detected.why_interest.min_n == 50
    assert detected.why_interest.max_n == 50


def test_detect_why_interest_minimum_fifty_words_is_floor_only() -> None:
    """
    ``Minimum N words`` is a floor, not an exact length.

    Real phrasing from Epoch AI Lever EOI-style forms.
    """
    from src.generation.cover_letter_instructions import WhyInterestSpec

    jd = (
        "Why do you want to work at Epoch AI?\n\n"
        "Minimum 50 words. All applications are reviewed by humans, so we're "
        "interested in your genuine response."
    )
    detected = detect_application_instructions(jd)
    assert detected.why_interest is not None
    assert detected.why_interest.unit == "words"
    assert detected.why_interest.min_n == 50
    assert detected.why_interest.max_n is None
    assert "minimum" in detected.why_interest.matched_span.lower()

    over = (
        "I want to work at Epoch AI because the research agenda matches my "
        "background in measuring AI progress and communicating findings to "
        "policymakers. I care about careful evaluation, open methods, and "
        "grounding claims in evidence rather than hype. That is why this "
        "expression of interest is a genuine fit for the skills already on "
        "my resume and the problems I want to keep working on."
    )
    assert count_length_units(over, "words") > 50
    assert length_within_spec(over, detected.why_interest) is True

    short = WhyInterestSpec(
        min_n=50, max_n=None, unit="words", matched_span="Minimum 50 words"
    )
    assert length_within_spec("Too short.", short) is False


def test_detect_why_interest_at_least_two_sentences() -> None:
    """
    ``At least N sentences`` also parses as a min-only floor.
    """
    jd = "In at least 2 sentences, explain why this company mission " "interests you."
    detected = detect_application_instructions(jd)
    assert detected.why_interest is not None
    assert detected.why_interest.min_n == 2
    assert detected.why_interest.max_n is None
    assert detected.why_interest.unit == "sentences"


def test_near_miss_length_without_interest_cue_not_detected() -> None:
    """
    Length phrases alone (e.g. resume bullets) must not trigger why-interest.
    """
    jd = (
        "Responsibilities include writing 3-4 lines of documentation per ticket "
        "and shipping weekly releases."
    )
    detected = detect_application_instructions(jd)
    assert detected.why_interest is None


def test_normal_jd_no_instructions() -> None:
    """
    Ordinary JD without submission format asks stays undetected.
    """
    jd = (
        "We are hiring a software engineer. Requirements: Python, SQL. "
        "Nice to have: cloud experience."
    )
    detected = detect_application_instructions(jd)
    assert detected.why_interest is None
    assert detected.inclusions == []


def test_detect_github_inclusion() -> None:
    """
    Detect an explicit GitHub inclusion ask.
    """
    jd = "Please include a link to your GitHub in the cover letter."
    detected = detect_application_instructions(jd)
    assert len(detected.inclusions) == 1
    assert detected.inclusions[0].kind == "github"


def test_count_and_length_within_spec_lines_via_sentences() -> None:
    """
    Single-paragraph short answers count sentences as lines when no newlines.
    """
    from src.generation.cover_letter_instructions import WhyInterestSpec

    text = (
        "First reason tied to the role. Second reason from the JD. "
        "Third reason grounded in confirmed facts."
    )
    spec = WhyInterestSpec(min_n=3, max_n=4, unit="lines", matched_span="3-4 lines")
    assert count_length_units(text, "lines") == 3
    assert length_within_spec(text, spec) is True


def test_resolve_inclusion_urls_never_invents() -> None:
    """
    Missing profile URLs remain None.
    """
    from src.generation.cover_letter_instructions import InclusionSpec

    mapping = resolve_inclusion_urls(
        [InclusionSpec(kind="github", matched_span="include GitHub")],
        github=None,
    )
    assert mapping["github"] is None


def test_inclusion_present_in_text() -> None:
    """
    URL and host-path forms both count as present.
    """
    url = "https://github.com/example-user"
    assert inclusion_present_in_text(f"See {url}", url) is True
    assert inclusion_present_in_text("See github.com/example-user", url) is True
    assert inclusion_present_in_text("No links here", url) is False


def test_validator_short_answer_length_and_inclusion() -> None:
    """
    Short-answer mode flags length mismatch and missing inclusion softly.
    """
    from src.generation.cover_letter_instructions import (
        DetectedInstructions,
        InclusionSpec,
        WhyInterestSpec,
    )
    from src.generation.cover_letter_validator import (
        CoverLetterIssue,
        CoverLetterValidator,
    )
    from src.generation.cover_letter_writer import GeneratedCoverLetter
    from src.generation.selector import SelectionOutput
    from src.models.job_listing import JobListing, JobSource
    from src.models.user_profile import ContactInfo, UserProfile

    job = JobListing(
        job_id="phase-c-1",
        title="Engineer",
        company="Acme Labs",
        source=JobSource.MANUAL,
        description="Send 3-4 lines on why this mission excites you. Include GitHub.",
    )
    profile = UserProfile(
        name="Test User",
        contact=ContactInfo(
            email="test@example.com",
            location="Singapore",
            github="https://github.com/example-user",
        ),
        summary="Engineer",
    )
    selection = SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="",
    )
    letter = GeneratedCoverLetter(
        content="Only one sentence about Acme Labs.",
        highlighted_experiences=[],
        word_count=6,
        model_used="test",
    )
    detected = DetectedInstructions(
        why_interest=WhyInterestSpec(
            min_n=3, max_n=4, unit="lines", matched_span="3-4 lines"
        ),
        inclusions=[InclusionSpec(kind="github", matched_span="Include GitHub")],
    )
    result = CoverLetterValidator(strict_mode=False).validate(
        letter,
        job,
        profile,
        selection,
        short_answer_mode=True,
        detected_instructions=detected,
        inclusion_urls={"github": "https://github.com/example-user"},
    )
    assert CoverLetterIssue.TOO_SHORT not in result.issues
    assert CoverLetterIssue.FEW_PARAGRAPHS not in result.issues
    assert CoverLetterIssue.NO_CALL_TO_ACTION not in result.issues
    assert CoverLetterIssue.INSTRUCTION_LENGTH_MISMATCH in result.issues
    assert CoverLetterIssue.MISSING_REQUIRED_INCLUSION in result.issues
