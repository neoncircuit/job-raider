"""
Job Raider - Experience signals of a job posting

Finds two signals in a job: the years of experience that it asks for, and
whether it says that fresh graduates are welcome (job-card-labels task). The
job card shows both as labels. In fresh graduate mode, a fresh-grad-friendly
posting is not capped for its required years.

The years come from the posting text only, as a range when the text states
one (change F): the MyCareersFuture form field is stored but not used, because
it can differ from what the employer wrote. The labelled set ``tests/fixtures/eval/experience_signals``
checks the text rules.

Author: Job Raider
Date: 2026-11-16
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
}
_NUMBER = r"(\d+(?:\.\d+)?|" + "|".join(NUMBER_WORDS) + r")(?:\s*\(\d+\))?"
# A number of years, then "experience" within a few words: "3+ years of
# experience", "3-5 years of relevant experience", "8 or more years of
# full stack web development experience", "2 yrs experience".
YEARS_RE = re.compile(
    rf"\b{_NUMBER}\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*{_NUMBER}\s*)?(?:\+\s*)?"
    r"(?:or\s+more\s+)?(?:years?|yrs?)\b(?:\W+[\w-]+){0,6}?\W+experience",
    re.IGNORECASE,
)
# Sentences that make the years optional.
OPTIONAL_RE = re.compile(
    r"\b(preferred|advantage|advantageous|a plus|bonus|nice to have|desirable)\b",
    re.IGNORECASE,
)
FRESH_SUBJECT_RE = re.compile(r"\b(?:fresh|recent)\s+grad(?:uate)?s?\b", re.IGNORECASE)
FRESH_CUE_RE = re.compile(
    r"\b(welcome[ds]?|encouraged|may apply|can apply|invited|considered|eligible|"
    r"open to|suitable)\b",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(r"\b(not|never|need not|cannot)\b|n't\b", re.IGNORECASE)
NO_EXPERIENCE_RE = re.compile(
    r"\bno\s+(?:prior\s+|previous\s+|work\s+)?experience\s+(?:is\s+)?"
    r"(?:required|needed|necessary)\b",
    re.IGNORECASE,
)
# "Up to N years" just before a match: the range is 0 to N.
UP_TO_RE = re.compile(r"\bup\s+to\s*$", re.IGNORECASE)
YearsRange = Tuple[float, Optional[float]]
"""Minimum and maximum years (maximum None when the text states only a minimum)."""

# A sentence ends at ".", "!", "?", or ";" before a space or the end, or at a
# new line, so "2.5 years" stays in one sentence.
SENTENCE_END_RE = re.compile(r"[.!?;]+(?=\s|$)|\n+")


def _sentences(text: str) -> List[str]:
    """
    Split a text into sentences.

    Args:
        text: The text.

    Returns:
        The non-empty sentences.
    """
    return [part.strip() for part in SENTENCE_END_RE.split(text) if part.strip()]


def _number(token: str) -> float:
    """
    Read a number token: digits or a number word.

    Args:
        token: For example "3", "2.5", or "three".

    Returns:
        The number.
    """
    word = token.lower()
    return float(NUMBER_WORDS[word]) if word in NUMBER_WORDS else float(token)


def years_range_from_text(text: str) -> Optional[YearsRange]:
    """
    Find the range of years of experience that a posting text states.

    A phrase counts only when "experience" follows the years within a few
    words, and when its sentence does not make it optional ("preferred",
    "advantage", "a plus", "bonus", "nice to have"). "1 to 5 years" gives
    (1, 5), "5+ years" gives (5, None), and "up to 2 years" gives (0, 2).
    When the text states several phrases, the one with the largest minimum
    counts.

    Args:
        text: The posting text.

    Returns:
        The minimum and maximum years, or None when the text states none.
    """
    found: List[YearsRange] = []
    for sentence in _sentences(text or ""):
        if OPTIONAL_RE.search(sentence):
            continue
        for match in YEARS_RE.finditer(sentence):
            low = _number(match.group(1))
            high = _number(match.group(2)) if match.group(2) else None
            if UP_TO_RE.search(sentence[: match.start()]):
                low, high = 0.0, low
            found.append((low, high))
    if not found:
        return None
    return max(found, key=lambda item: (item[0], item[1] or 0.0))


def years_from_text(text: str) -> Optional[float]:
    """
    Find the minimum years of experience that a posting text asks for.

    Args:
        text: The posting text.

    Returns:
        The minimum of ``years_range_from_text``, or None when the text
        states no years.
    """
    found = years_range_from_text(text)
    return found[0] if found else None


def is_fresh_grad_friendly(text: str) -> bool:
    """
    Check whether a posting text says that fresh graduates are welcome.

    A sentence counts when it names fresh or recent graduates together with a
    welcome cue ("welcome", "encouraged", "may apply", "considered", "open
    to", "suitable") and has no negation ("not", "never", "need not",
    "n't"). "No experience required" also counts.

    Args:
        text: The posting text.

    Returns:
        True when the posting welcomes fresh graduates.
    """
    for sentence in _sentences(text or ""):
        if NO_EXPERIENCE_RE.search(sentence):
            return True
        if (
            FRESH_SUBJECT_RE.search(sentence)
            and FRESH_CUE_RE.search(sentence)
            and not NEGATION_RE.search(sentence)
        ):
            return True
    return False


def structured_required_years(job: Any) -> Optional[float]:
    """
    Return the largest structured required years of a job.

    Only ``JobRequirement.years_of_experience`` counts (for example the
    MyCareersFuture minimum years). The job may be any object with a
    ``requirements`` list.

    Args:
        job: The job listing.

    Returns:
        The largest stated years, or None when the job states none.
    """
    years = [
        float(req.years_of_experience)
        for req in getattr(job, "requirements", None) or []
        if getattr(req, "years_of_experience", None) is not None
    ]
    return max(years) if years else None


def job_signal_text(job: Any) -> str:
    """
    Join the text of a job that the signals are read from.

    The full description is used, not the 5000-character API cut.
    Requirements that carry structured ``years_of_experience`` (the
    MyCareersFuture form field) are left out: the years must come from what
    the employer wrote (change F, user decision 2026-11-16).

    Args:
        job: The job listing (title, description, requirements).

    Returns:
        The title, description, and requirement texts, one per line.
    """
    parts = [getattr(job, "title", "") or "", getattr(job, "description", "") or ""]
    parts.extend(
        getattr(req, "text", "") or ""
        for req in getattr(job, "requirements", None) or []
        if getattr(req, "years_of_experience", None) is None
    )
    return "\n".join(parts)


def job_required_years_range(job: Any) -> Optional[YearsRange]:
    """
    Return the range of years that a job's text states, for the job card label.

    Only the text counts; there is no fallback to the form field.

    Args:
        job: The job listing.

    Returns:
        The minimum and maximum years, or None when the text states none.
    """
    return years_range_from_text(job_signal_text(job))


def job_required_years(job: Any) -> Optional[float]:
    """
    Return the minimum years of experience that a job's text asks for.

    The years cap and the run counts read this value. Only the text counts.

    Args:
        job: The job listing.

    Returns:
        The minimum years, or None when the text states none.
    """
    found = job_required_years_range(job)
    return found[0] if found else None


def job_is_fresh_grad_friendly(job: Any) -> bool:
    """
    Check whether a job posting welcomes fresh graduates.

    Args:
        job: The job listing.

    Returns:
        True when the posting text welcomes fresh graduates.
    """
    return is_fresh_grad_friendly(job_signal_text(job))
