"""
Job Raider - Generic Phrasing Detector

Finds stock phrases in generated cover letters and CVs, and counts them per
100 words. The check is deterministic (no LLM): each phrase is a whole-word,
case-insensitive match. A space or a hyphen inside a phrase matches either
one ("results-driven" also matches "results driven"), and a straight
apostrophe also matches a curly one.

Overlapping phrases are counted once: at each position the longest phrase
wins, so "in today's fast-paced environment" is one hit, not two.

The phrase groups are a first version, drafted for the generic-phrasing task
(2026-11-12) and checked by the user. Keep each phrase lowercase.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Mapping, Pattern, Tuple

GROUP_OPENING = "opening"
GROUP_SELF_DESCRIPTION = "self_description"
GROUP_FILLER = "filler"
GROUP_CLOSING = "closing"
GROUP_CV_FILLER = "cv_filler"

GENERIC_PHRASES: Mapping[str, Tuple[str, ...]] = {
    GROUP_OPENING: (
        "i am writing to apply",
        "i am writing to express my interest",
        "i am writing in response to",
        "please accept this letter",
        "i would like to express my interest",
        "i am submitting my application",
        "i am excited to apply",
        "i was thrilled to see",
        "it is with great enthusiasm",
    ),
    GROUP_SELF_DESCRIPTION: (
        "team player",
        "fast learner",
        "quick learner",
        "hard worker",
        "hard-working",
        "results-driven",
        "detail-oriented",
        "self-starter",
        "go-getter",
        "proven track record",
        "passionate about",
        "think outside the box",
        "strong work ethic",
        "excellent communication skills",
        "wear many hats",
    ),
    GROUP_FILLER: (
        "delve",
        "delves",
        "delving",
        "furthermore",
        "moreover",
        "in today's fast-paced",
        "fast-paced environment",
        "ever-evolving",
        "ever-changing landscape",
        "leverage my",
        "synergy",
        "cutting-edge",
        "a testament to",
        "unwavering",
        "i am confident that",
        "make a meaningful impact",
        "align perfectly",
        "perfect fit",
        "invaluable",
    ),
    GROUP_CLOSING: (
        "i look forward to hearing from you",
        "thank you for your time and consideration",
        "please do not hesitate to contact me",
        "feel free to contact me",
    ),
    GROUP_CV_FILLER: (
        "responsible for",
        "duties included",
        "tasked with",
        "various tasks",
    ),
}

_SEPARATOR = re.compile(r"[\s-]+")
_WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")


@dataclass(frozen=True)
class PhraseHit:
    """
    One stock phrase found in a text.

    Attributes:
        phrase: The phrase from ``GENERIC_PHRASES`` (lowercase).
        group: The group of the phrase.
        count: How many times the phrase occurs.
    """

    phrase: str
    group: str
    count: int


@dataclass(frozen=True)
class GenericPhrasingResult:
    """
    The stock phrases found in one text.

    Attributes:
        hits: One entry per phrase found, most frequent first, then by phrase.
        total: The number of phrase occurrences.
        word_count: The number of words in the text.
        per_100_words: ``total`` per 100 words, rounded to 2 decimals
            (0.0 for a text with no words).
    """

    hits: Tuple[PhraseHit, ...]
    total: int
    word_count: int
    per_100_words: float


def _words_of(text: str) -> Tuple[str, ...]:
    """
    Split a phrase or a match into lowercase words.

    Args:
        text: A phrase or matched text.

    Returns:
        The words, lowercase, with curly apostrophes made straight.
    """
    cleaned = text.lower().replace("’", "'")
    return tuple(word for word in _SEPARATOR.split(cleaned.strip()) if word)


def _phrase_regex(words: Tuple[str, ...]) -> str:
    """
    Build the regex body for one phrase.

    Args:
        words: The words of the phrase.

    Returns:
        A regex that matches the words with spaces or hyphens between them,
        and with a straight or curly apostrophe.
    """
    escaped = [re.escape(word).replace("'", "['’]") for word in words]
    return r"[\s-]+".join(escaped)


def _build_matcher(
    groups: Mapping[str, Tuple[str, ...]],
) -> Tuple[Pattern[str], Dict[Tuple[str, ...], Tuple[str, str]]]:
    """
    Compile all phrases into one pattern, longest phrase first.

    Args:
        groups: Phrase groups, as in ``GENERIC_PHRASES``.

    Returns:
        The compiled pattern, and a map from the words of each phrase to the
        phrase and its group.

    Raises:
        ValueError: When a phrase is empty or not lowercase, or when two
            phrases have the same words.
    """
    lookup: Dict[Tuple[str, ...], Tuple[str, str]] = {}
    for group, phrases in groups.items():
        for phrase in phrases:
            words = _words_of(phrase)
            if not words or phrase != phrase.lower():
                raise ValueError(f"Phrase must be lowercase and non-empty: {phrase!r}")
            if words in lookup:
                raise ValueError(f"Two phrases have the same words: {phrase!r}")
            lookup[words] = (phrase, group)
    ordered = sorted(lookup, key=lambda words: len(" ".join(words)), reverse=True)
    body = "|".join(f"(?:{_phrase_regex(words)})" for words in ordered)
    return re.compile(rf"\b(?:{body})\b", re.IGNORECASE), lookup


_MATCHER, _LOOKUP = _build_matcher(GENERIC_PHRASES)


def count_words(text: str) -> int:
    """
    Count the words in a text.

    Args:
        text: Any text.

    Returns:
        The number of words. A hyphenated word or a word with an apostrophe
        counts as one word.
    """
    return len(_WORD_PATTERN.findall(text or ""))


def find_generic_phrases(text: str) -> GenericPhrasingResult:
    """
    Find the stock phrases in a text.

    Args:
        text: A cover letter, a CV section, or any other text.

    Returns:
        The phrases found, their total, the word count, and the total per
        100 words.
    """
    counts: Counter[Tuple[str, str]] = Counter(
        _LOOKUP[_words_of(match.group(0))] for match in _MATCHER.finditer(text or "")
    )
    hits = tuple(
        PhraseHit(phrase=phrase, group=group, count=count)
        for (phrase, group), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0][0])
        )
    )
    total = sum(counts.values())
    words = count_words(text)
    per_100 = round(total * 100.0 / words, 2) if words else 0.0
    return GenericPhrasingResult(
        hits=hits, total=total, word_count=words, per_100_words=per_100
    )


def all_phrases() -> List[str]:
    """
    List every phrase, in group order.

    Returns:
        All phrases of ``GENERIC_PHRASES``.
    """
    return [phrase for phrases in GENERIC_PHRASES.values() for phrase in phrases]
