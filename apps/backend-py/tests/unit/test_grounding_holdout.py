"""
Format and diversity checks for the grounding holdout set (Step 3.2, decision 1).

The holdout set shows whether the validator fixes generalize beyond the 65
cases they were measured on. This test checks only the format, the
diversity limits, and that the holdout does not overlap the main set. It
never runs the validator: the holdout runs one time, after fix F7.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.evaluation.datasets import load_jsonl
from src.evaluation.suites.grounding import (
    DEFAULT_DATASET_DIR,
    GROUNDING_LABELS,
    GroundingCase,
)
from src.models.user_profile import UserProfile

HOLDOUT_DIR = DEFAULT_DATASET_DIR.parent / "grounding_holdout"


def _long_sentences(
    text: str, job: Optional[Dict[str, Any]] = None, slots: bool = False
) -> List[str]:
    """
    Normalize a letter into sentences of 8 or more words.

    Digits become ``#``. With ``slots``, the job company and title and the
    phrase after "the need to" are also replaced, so sentence frames that
    differ only in names count as the same frame.

    Args:
        text: Letter text.
        job: The case job, used for slot replacement.
        slots: Replace company, title, and the need phrase.

    Returns:
        Normalized long sentences.
    """
    joined = " ".join(text.split())
    if slots and job:
        for key, slot in (("company", "<co>"), ("title", "<title>")):
            value = str(job.get(key) or "")
            if value:
                joined = re.sub(re.escape(value), slot, joined, flags=re.IGNORECASE)
    sentences = []
    for part in re.split(r"(?<=[.!?])\s+", joined):
        sentence = re.sub(r"\d+", "#", part.lower()).strip()
        if slots:
            sentence = re.sub(r"\b(a|an) <title>", "a <title>", sentence)
            sentence = re.sub(r"the need to [^,.:;]+", "the need to <need>", sentence)
        if len(sentence.split()) >= 8:
            sentences.append(sentence)
    return sentences


def _cases(directory: Path) -> List[GroundingCase]:
    """
    Load the cases of a grounding dataset folder.

    Args:
        directory: Folder with ``cases.jsonl``.

    Returns:
        Validated cases.
    """
    return load_jsonl(directory / "cases.jsonl", GroundingCase)


def test_holdout_structure() -> None:
    """Cases and profiles load, IDs are unique, and every label is present."""
    cases = _cases(HOLDOUT_DIR)
    raw_profiles = json.loads((HOLDOUT_DIR / "profiles.json").read_text("utf-8"))
    profiles = {pid: UserProfile.model_validate(p) for pid, p in raw_profiles.items()}

    assert len(cases) >= 20
    ids = [case.case_id for case in cases]
    assert len(ids) == len(set(ids))
    assert {case.profile_id for case in cases} <= set(profiles)
    for profile in profiles.values():
        assert str(profile.contact.email).endswith("@example.com")
    per_profile = Counter(case.profile_id for case in cases)
    assert min(per_profile.values()) >= 8, per_profile
    assert sum(1 for case in cases if not case.expected_issues) >= 8
    present = {label for case in cases for label in case.expected_issues}
    assert set(GROUNDING_LABELS) <= present, set(GROUNDING_LABELS) - present
    for case in cases:
        words = len(case.letter.split())
        assert 150 <= words <= 350, (case.case_id, words)


def test_holdout_diversity() -> None:
    """Sentences and sentence frames are not reused across holdout letters."""
    cases = _cases(HOLDOUT_DIR)
    plain = {c.case_id: _long_sentences(c.letter) for c in cases}
    frames = {c.case_id: _long_sentences(c.letter, c.job, slots=True) for c in cases}
    total = sum(len(s) for s in plain.values())
    plain_counts = Counter(s for sents in plain.values() for s in set(sents))
    frame_counts = Counter(s for sents in frames.values() for s in set(sents))
    pair_max = max(
        len(set(plain[a]) & set(plain[b])) for a, b in combinations(plain, 2)
    )
    companies = Counter(str(c.job.get("company")) for c in cases)

    assert max(plain_counts.values()) <= 3, plain_counts.most_common(1)
    assert pair_max <= 2
    assert len(plain_counts) / total >= 0.80
    assert max(frame_counts.values()) <= 5, frame_counts.most_common(1)
    assert len(frame_counts) / total >= 0.85
    assert max(companies.values()) <= 2, companies.most_common(1)


def test_holdout_does_not_overlap_the_main_set() -> None:
    """No case ID, company, or long sentence is shared with the main set."""
    holdout = _cases(HOLDOUT_DIR)
    main = _cases(DEFAULT_DATASET_DIR)

    assert not {c.case_id for c in holdout} & {c.case_id for c in main}
    shared_companies = {str(c.job.get("company")) for c in holdout} & {
        str(c.job.get("company")) for c in main
    }
    assert not shared_companies, shared_companies
    main_sentences = {s for c in main for s in _long_sentences(c.letter)}
    shared = [
        s for c in holdout for s in _long_sentences(c.letter) if s in main_sentences
    ]
    assert not shared, shared[:3]
