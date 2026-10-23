"""
Structural tests for the committed grounding evaluation dataset.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

import pytest

from src.evaluation.datasets import load_jsonl
from src.evaluation.suites.grounding import GroundingCase
from src.models.user_profile import UserProfile

DATASET_DIR = Path(__file__).parents[1] / "fixtures" / "eval" / "grounding"
CASES_PATH = DATASET_DIR / "cases.jsonl"
PROFILES_PATH = DATASET_DIR / "profiles.json"

MINIMUM_GROUP_COUNTS = {
    "clean": 15,
    "fabricated_technology": 8,
    "homonym": 5,
    "inflated_duration": 6,
    "inconsistent_metric": 5,
    "fabricated_experience": 6,
    "analogical_claim": 4,
    "scope_inflation": 4,
    "technique_mismatch": 4,
    "unsupported_number": 5,
    "prompt_injection": 3,
}


def _load_profiles(path: Path = PROFILES_PATH) -> Dict[str, UserProfile]:
    """
    Load and validate synthetic profiles.

    Args:
        path: Profile JSON path.

    Returns:
        Profiles keyed by profile ID.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        profile_id: UserProfile.model_validate(profile)
        for profile_id, profile in raw.items()
    }


def _assert_unique_case_ids(cases: List[GroundingCase]) -> None:
    """
    Assert that every case ID is unique.

    Args:
        cases: Validated grounding cases.

    Returns:
        None.
    """
    ids = [case.case_id for case in cases]
    duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    assert not duplicates, f"duplicate case_id values: {duplicates}"


def test_grounding_dataset_structure_and_counts() -> None:
    """
    Validate case schemas, profile references, IDs, counts, and safe emails.

    Returns:
        None.
    """
    cases = load_jsonl(CASES_PATH, GroundingCase)
    profiles = _load_profiles()

    _assert_unique_case_ids(cases)
    assert all(case.profile_id in profiles for case in cases)

    groups = Counter(case.case_id.split("__", 1)[0] for case in cases)
    for group, minimum in MINIMUM_GROUP_COUNTS.items():
        assert (
            groups[group] >= minimum
        ), f"{group}: expected at least {minimum}, got {groups[group]}"

    clean_count = sum(not case.expected_issues for case in cases)
    assert clean_count >= 15, f"expected at least 15 clean labels, got {clean_count}"
    assert all(150 <= len(case.letter.split()) <= 350 for case in cases)
    assert all(case.note.strip() for case in cases)
    assert all(
        str(profile.contact.email).endswith("@example.com")
        for profile in profiles.values()
    )


_WHITESPACE = re.compile(r"\s+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_DIGITS = re.compile(r"\d+")


def normalize_long_sentences(text: str) -> List[str]:
    """
    Normalize a letter and return sentences of 8 or more words.

    Whitespace is joined. The text is split after ``.``, ``!``, or ``?``
    when whitespace follows. Each sentence is lowercased, each run of digits
    becomes ``#``, and the ends are stripped. Shorter sentences are dropped
    so greetings and sign-offs are not limited.

    Args:
        text: Cover letter text.

    Returns:
        Long sentences in order. A sentence can appear more than once.
    """
    collapsed = _WHITESPACE.sub(" ", text).strip()
    long_sentences: List[str] = []
    for part in _SENTENCE_BREAK.split(collapsed):
        sentence = _DIGITS.sub("#", part.lower()).strip()
        if len(sentence.split()) >= 8:
            long_sentences.append(sentence)
    return long_sentences


def normalize_slot_sentences(text: str, job: Dict[str, Any]) -> List[str]:
    """
    Normalize a letter with job slots and return sentences of 8 or more words.

    Company becomes ``<co>``, title becomes ``<title>`` (including ``a/an
    <title>`` as ``a <title>``), and the phrase after "the need to" up to
    the next ``,``, ``.``, ``:``, or ``;`` becomes ``<need>``. Digits then
    become ``#``. Frames that differ only in those slots count as one frame.

    Args:
        text: Cover letter text.
        job: Case job with company and title.

    Returns:
        Slot-normalized long sentences in order.
    """
    joined = " ".join(text.split())
    for key, slot in (("company", "<co>"), ("title", "<title>")):
        value = str(job.get(key) or "")
        if value:
            joined = re.sub(re.escape(value), slot, joined, flags=re.IGNORECASE)
    long_sentences: List[str] = []
    for part in re.split(r"(?<=[.!?])\s+", joined):
        sentence = re.sub(r"\d+", "#", part.lower()).strip()
        sentence = re.sub(r"\b(a|an) <title>", "a <title>", sentence)
        sentence = re.sub(r"the need to [^,.:;]+", "the need to <need>", sentence)
        if len(sentence.split()) >= 8:
            long_sentences.append(sentence)
    return long_sentences


def diversity_violations(
    cases: Sequence[GroundingCase], profile_ids: Sequence[str]
) -> Tuple[List[str], Dict[str, object]]:
    """
    Check diversity limits L1 to L8 for a grounding case list.

    Args:
        cases: Validated cases in dataset order.
        profile_ids: Profile IDs that must each appear in at least 12 cases.

    Returns:
        A list of human-readable violations, and a stats map. The list is
        empty when every limit holds.
    """
    long_by_case: Dict[str, List[str]] = {
        case.case_id: normalize_long_sentences(case.letter) for case in cases
    }
    frames_by_case: Dict[str, List[str]] = {
        case.case_id: normalize_slot_sentences(case.letter, case.job) for case in cases
    }
    all_long = [
        sentence for sentences in long_by_case.values() for sentence in sentences
    ]
    cases_per_sentence: Dict[str, Set[str]] = defaultdict(set)
    for case_id, sentences in long_by_case.items():
        for sentence in set(sentences):
            cases_per_sentence[sentence].add(case_id)
    max_sentence_cases = max(
        (len(ids) for ids in cases_per_sentence.values()), default=0
    )

    max_shared = 0
    case_ids = list(long_by_case)
    for index, left_id in enumerate(case_ids):
        left = set(long_by_case[left_id])
        for right_id in case_ids[index + 1 :]:
            shared = len(left & set(long_by_case[right_id]))
            if shared > max_shared:
                max_shared = shared

    distinct = len(set(all_long))
    total = len(all_long)
    ratio = (distinct / total) if total else 0.0
    companies = [str(case.job["company"]) for case in cases]
    titles = [str(case.job["title"]) for case in cases]
    company_counts = Counter(companies)
    max_company = max(company_counts.values(), default=0)
    word_counts = [len(case.letter.split()) for case in cases]
    long_letters = sum(count > 220 for count in word_counts)
    profile_counts = Counter(case.profile_id for case in cases)

    cases_per_frame: Dict[str, Set[str]] = defaultdict(set)
    for case_id, sentences in frames_by_case.items():
        for sentence in set(sentences):
            cases_per_frame[sentence].add(case_id)
    max_frame_cases = max((len(ids) for ids in cases_per_frame.values()), default=0)
    frames_in_five_or_more = sum(1 for ids in cases_per_frame.values() if len(ids) >= 5)
    all_frames = [
        sentence for sentences in frames_by_case.values() for sentence in sentences
    ]
    distinct_frames = len(set(all_frames))
    frame_ratio = (distinct_frames / total) if total else 0.0

    stats: Dict[str, object] = {
        "l1_max_cases_for_one_sentence": max_sentence_cases,
        "l2_max_shared_long_sentences": max_shared,
        "l3_distinct_long_sentences": distinct,
        "l3_long_sentences": total,
        "l3_ratio": round(ratio, 4),
        "l4_companies": len(set(companies)),
        "l4_titles": len(set(titles)),
        "l4_max_cases_per_company": max_company,
        "l5_min_words": min(word_counts, default=0),
        "l5_max_words": max(word_counts, default=0),
        "l5_letters_over_220": long_letters,
        "l6_cases_per_profile": dict(profile_counts),
        "l7_max_cases_for_one_frame": max_frame_cases,
        "l7_frames_in_5_or_more_cases": frames_in_five_or_more,
        "l8_distinct_frames": distinct_frames,
        "l8_long_sentences": total,
        "l8_ratio": round(frame_ratio, 4),
    }
    violations: List[str] = []
    if max_sentence_cases > 3:
        violations.append(
            f"L1: a long sentence appears in {max_sentence_cases} cases (max 3)"
        )
    if max_shared > 2:
        violations.append(f"L2: two cases share {max_shared} long sentences (max 2)")
    if total == 0 or ratio < 0.80:
        violations.append(f"L3: distinct/all long sentences is {ratio:.4f} (min 0.80)")
    if len(set(companies)) < 20 or len(set(titles)) < 12 or max_company > 5:
        violations.append(
            "L4: need >=20 companies, >=12 titles, and <=5 cases per company; "
            f"got {len(set(companies))} companies, {len(set(titles))} titles, "
            f"max {max_company}"
        )
    if any(count < 150 or count > 350 for count in word_counts) or long_letters < 15:
        violations.append(
            "L5: each letter needs 150-350 words and >=15 letters need >220 words; "
            f"min {stats['l5_min_words']}, max {stats['l5_max_words']}, "
            f"over 220: {long_letters}"
        )
    for profile_id in profile_ids:
        if profile_counts[profile_id] < 12:
            violations.append(
                f"L6: profile {profile_id} is used by {profile_counts[profile_id]} cases (min 12)"
            )
    if max_frame_cases > 5:
        violations.append(
            f"L7: a slot-normalized frame appears in {max_frame_cases} cases (max 5)"
        )
    if total == 0 or frame_ratio < 0.85:
        violations.append(
            f"L8: distinct frames / all long sentences is {frame_ratio:.4f} (min 0.85)"
        )
    return violations, stats


def test_grounding_dataset_diversity() -> None:
    """
    Require measurable letter and job diversity (limits L1 to L8).

    Returns:
        None.
    """
    cases = load_jsonl(CASES_PATH, GroundingCase)
    profiles = _load_profiles()
    violations, stats = diversity_violations(cases, list(profiles))
    assert not violations, {"violations": violations, "stats": stats}


@pytest.mark.xfail(
    strict=True,
    reason="D6b will add ungrounded_sentences to every main-set case",
)
def test_grounding_dataset_has_sentence_labels() -> None:
    """
    Require a sentence-level ungrounded list on every main-set case.

    ``None`` means the case is not labeled at sentence level. D6b replaces
    that with a list on every main-set case.

    Returns:
        None.
    """
    cases = load_jsonl(CASES_PATH, GroundingCase)
    missing = [case.case_id for case in cases if case.ungrounded_sentences is None]
    assert not missing, missing
