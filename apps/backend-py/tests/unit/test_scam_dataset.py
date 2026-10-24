"""
Structural and diversity tests for the committed scam evaluation set.

These tests load ``cases.jsonl``. They do not run the scam detector.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

from src.evaluation.datasets import load_jsonl
from src.evaluation.suites.scam import (
    CASE_GROUPS,
    LEGIT_CASE_GROUPS,
    SCAM_CASE_GROUPS,
    ScamCase,
)
from src.models.job_listing import JobListing

DATASET_DIR = Path(__file__).parents[1] / "fixtures" / "eval" / "scam"
CASES_PATH = DATASET_DIR / "cases.jsonl"
BACKEND_DIR = Path(__file__).resolve().parents[2]

MINIMUM_TOTAL = 40
MINIMUM_LEGIT = 20
MINIMUM_SCAM = 20
MINIMUM_HARD_NEGATIVES = 6
MINIMUM_PER_INDICATOR = 4
MINIMUM_COMPANIES = 25
MINIMUM_LONG_WRITTEN = 6
MAX_CASES_PER_COMPANY = 2

WRITTEN_GROUPS = frozenset({"legit_written", "hard_negative"} | set(SCAM_CASE_GROUPS))
VOICE_FORBIDDEN = (
    r"\blabel\b",
    r"\btest case\b",
    r"\bindicator\b",
    r"\bdataset\b",
    r"this posting is",
)
VOICE_SCAM_FRAUD = re.compile(r"\b(scam|fraud)\b", re.IGNORECASE)
HARD_NEGATIVE_ANTIFRAUD_ID = "hard_negative__antifraud_notice"

_WHITESPACE = re.compile(r"\s+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_DIGITS = re.compile(r"\d+")


def _load_cases() -> List[ScamCase]:
    """
    Load the committed scam cases.

    Returns:
        Validated cases in file order.
    """
    return load_jsonl(CASES_PATH, ScamCase)


def _case_group(case_id: str) -> str:
    """
    Return the group prefix of a case ID.

    Args:
        case_id: ``<group>__<short_name>``.

    Returns:
        The group prefix.
    """
    return case_id.split("__", 1)[0]


def _is_written(case: ScamCase) -> bool:
    """
    Return whether a case is a written posting.

    Args:
        case: Validated case.

    Returns:
        True when the source is ``written``.
    """
    return case.source == "written"


def _long_sentences(text: str) -> List[str]:
    """
    Normalize text and return sentences of 8 or more words.

    Whitespace is joined. The text is split after ``.``, ``!``, or ``?``
    when whitespace follows. Each sentence is lowercased, each run of
    digits becomes ``#``, and the ends are stripped.

    Args:
        text: Posting description.

    Returns:
        Long sentences in order.
    """
    collapsed = _WHITESPACE.sub(" ", text or "").strip()
    long_sentences: List[str] = []
    for part in _SENTENCE_BREAK.split(collapsed):
        sentence = _DIGITS.sub("#", part.lower()).strip()
        if len(sentence.split()) >= 8:
            long_sentences.append(sentence)
    return long_sentences


def _slot_sentences(text: str, job: Dict[str, Any]) -> List[str]:
    """
    Normalize a description with company and title slots.

    Args:
        text: Posting description.
        job: Case job with company and title.

    Returns:
        Slot-normalized long sentences.
    """
    joined = " ".join((text or "").split())
    for key, slot in (("company", "<co>"), ("title", "<title>")):
        value = str(job.get(key) or "")
        if value:
            joined = re.sub(re.escape(value), slot, joined, flags=re.IGNORECASE)
    long_sentences: List[str] = []
    for part in re.split(r"(?<=[.!?])\s+", joined):
        sentence = re.sub(r"\d+", "#", part.lower()).strip()
        sentence = re.sub(r"\b(a|an) <title>", "a <title>", sentence)
        if len(sentence.split()) >= 8:
            long_sentences.append(sentence)
    return long_sentences


def _opening_key(text: str, company: str) -> str:
    """
    Return the first four words of a description, with the company slotted.

    Args:
        text: Posting description.
        company: Company name.

    Returns:
        Four-word opening, or a shorter leftover.
    """
    joined = " ".join((text or "").split())
    if company:
        joined = re.sub(re.escape(company), "<co>", joined, flags=re.IGNORECASE)
    words = joined.lower().split()
    return " ".join(words[:4])


def _fixture_text(source: str) -> str:
    """
    Read the description text that a ``fixture:`` source points to.

    Args:
        source: ``fixture:<path>#<index or id>`` or ``fixture:<path>``.

    Returns:
        The fixture description, teaser, or file text.

    Raises:
        AssertionError: When the pointer does not resolve.
    """
    assert source.startswith("fixture:"), source
    rest = source[len("fixture:") :]
    if "#" in rest:
        rel, ref = rest.split("#", 1)
    else:
        rel, ref = rest, ""
    path = BACKEND_DIR / rel
    assert path.is_file(), f"fixture path does not exist: {rel}"
    if path.suffix == ".txt":
        return path.read_text(encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))
    item = _select_fixture_item(payload, ref)
    if "jobDescription" in item:
        return str(item["jobDescription"])
    if "teaser" in item:
        return str(item["teaser"])
    if "description" in item:
        return str(item["description"])
    raise AssertionError(f"no description field in fixture item: {source}")


def _select_fixture_item(payload: Any, ref: str) -> Dict[str, Any]:
    """
    Select one object from a JSON fixture.

    Args:
        payload: Parsed JSON.
        ref: Index or identifier. Empty means the only object, or index 0.

    Returns:
        The selected object.

    Raises:
        AssertionError: When the reference does not match.
    """
    items: List[Dict[str, Any]]
    if isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
        items = [item for item in payload["data"] if isinstance(item, dict)]
    elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
        items = [item for item in payload["results"] if isinstance(item, dict)]
    elif isinstance(payload, dict):
        items = [payload]
    else:
        raise AssertionError("fixture JSON is not a list or object")
    if not ref:
        assert items, "fixture JSON has no items"
        return items[0]
    if ref.isdigit():
        index = int(ref)
        assert 0 <= index < len(items), f"fixture index out of range: {ref}"
        return items[index]
    for item in items:
        for key in ("jobId", "id", "uuid"):
            if str(item.get(key, "")) == ref:
                return item
        posted = item.get("metadata") or {}
        if isinstance(posted, dict) and str(posted.get("jobPostId", "")) == ref:
            return item
    raise AssertionError(f"fixture id not found: {ref}")


def _diversity_stats(
    cases: Sequence[ScamCase],
) -> Tuple[List[str], Dict[str, object]]:
    """
    Check diversity limits S1 to S8 on written cases.

    Args:
        cases: Validated cases.

    Returns:
        Violations and a stats map. The list is empty when every limit holds.
    """
    written = [case for case in cases if _is_written(case)]
    long_by_case: Dict[str, List[str]] = {
        case.case_id: _long_sentences(str(case.job.get("description") or ""))
        for case in written
    }
    frames_by_case: Dict[str, List[str]] = {
        case.case_id: _slot_sentences(str(case.job.get("description") or ""), case.job)
        for case in written
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
    cases_per_frame: Dict[str, Set[str]] = defaultdict(set)
    for case_id, sentences in frames_by_case.items():
        for sentence in set(sentences):
            cases_per_frame[sentence].add(case_id)
    max_frame_cases = max((len(ids) for ids in cases_per_frame.values()), default=0)
    openings: Dict[str, Set[str]] = defaultdict(set)
    for case in written:
        key = _opening_key(
            str(case.job.get("description") or ""), str(case.job.get("company") or "")
        )
        if key:
            openings[key].add(case.case_id)
    max_opening_cases = max((len(ids) for ids in openings.values()), default=0)
    companies = [str(case.job.get("company") or "") for case in cases]
    company_counts = Counter(companies)
    word_counts = [
        len(str(case.job.get("description") or "").split()) for case in written
    ]
    long_written = sum(count > 200 for count in word_counts)

    stats: Dict[str, object] = {
        "s1_max_cases_for_one_sentence": max_sentence_cases,
        "s2_max_shared_long_sentences": max_shared,
        "s3_distinct_long_sentences": distinct,
        "s3_long_sentences": total,
        "s3_ratio": round(ratio, 4),
        "s4_max_cases_for_one_frame": max_frame_cases,
        "s5_max_cases_for_one_opening": max_opening_cases,
        "s6_companies": len(set(companies)),
        "s6_max_cases_per_company": max(company_counts.values(), default=0),
        "s8_min_words": min(word_counts, default=0),
        "s8_max_words": max(word_counts, default=0),
        "s8_written_over_200": long_written,
        "written_count": len(written),
    }
    violations: List[str] = []
    if max_sentence_cases > 2:
        violations.append(
            f"S1: a long sentence appears in {max_sentence_cases} cases (max 2)"
        )
    if max_shared > 1:
        violations.append(f"S2: two cases share {max_shared} long sentences (max 1)")
    if total == 0 or ratio < 0.90:
        violations.append(f"S3: distinct/all long sentences is {ratio:.4f} (min 0.90)")
    if max_frame_cases > 3:
        violations.append(
            f"S4: a slot-normalized frame appears in {max_frame_cases} cases (max 3)"
        )
    if max_opening_cases > 4:
        violations.append(
            f"S5: a 4-word opening appears in {max_opening_cases} cases (max 4)"
        )
    if len(set(companies)) < MINIMUM_COMPANIES:
        violations.append(
            f"S6: {len(set(companies))} distinct companies (min {MINIMUM_COMPANIES})"
        )
    if max(company_counts.values(), default=0) > MAX_CASES_PER_COMPANY:
        over = [
            f"{name}={count}"
            for name, count in company_counts.items()
            if count > MAX_CASES_PER_COMPANY
        ]
        violations.append(f"S6: a company is in more than 2 cases: {over}")
    if any(count < 30 or count > 450 for count in word_counts):
        violations.append(
            "S8: a written posting is outside 30 to 450 words; "
            f"min {min(word_counts, default=0)}, max {max(word_counts, default=0)}"
        )
    if long_written < MINIMUM_LONG_WRITTEN:
        violations.append(
            f"S8: {long_written} written postings over 200 words "
            f"(min {MINIMUM_LONG_WRITTEN})"
        )
    return violations, stats


def _voice_violations(cases: Sequence[ScamCase]) -> List[str]:
    """
    Find postings that name the dataset, a label, or the test.

    Args:
        cases: Validated cases.

    Returns:
        One message per violating case.
    """
    violations: List[str] = []
    for case in cases:
        text = f"{case.job.get('title') or ''} {case.job.get('description') or ''}"
        for pattern in VOICE_FORBIDDEN:
            if re.search(pattern, text, flags=re.IGNORECASE):
                violations.append(f"S7: {case.case_id} contains {pattern!r}")
        if VOICE_SCAM_FRAUD.search(text) and case.case_id != HARD_NEGATIVE_ANTIFRAUD_ID:
            violations.append(
                f"S7: {case.case_id} uses scam or fraud outside the anti-fraud notice"
            )
    return violations


def test_scam_dataset_structure_and_counts() -> None:
    """
    Validate schemas, IDs, labels, sources, and group counts.

    Returns:
        None.
    """
    cases = _load_cases()
    ids = [case.case_id for case in cases]
    duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    assert not duplicates, f"duplicate case_id values: {duplicates}"

    for case in cases:
        JobListing.model_validate(case.job)
        group = _case_group(case.case_id)
        assert group in CASE_GROUPS
        if group in SCAM_CASE_GROUPS:
            assert case.expected == "scam"
            assert case.indicator_groups
        if group in LEGIT_CASE_GROUPS:
            assert case.expected == "legit"
            assert case.indicator_groups == []
        assert case.note.strip(), f"{case.case_id}: empty note"
        if case.source.startswith("fixture:"):
            fixture_text = _fixture_text(case.source)
            assert (
                case.job.get("description") == fixture_text
            ), f"{case.case_id}: description is not the fixture text"
        else:
            assert case.source == "written", case.source

    legit = [case for case in cases if case.expected == "legit"]
    scam = [case for case in cases if case.expected == "scam"]
    hard = [case for case in cases if _case_group(case.case_id) == "hard_negative"]
    assert (
        len(cases) >= MINIMUM_TOTAL
    ), f"expected at least {MINIMUM_TOTAL}, got {len(cases)}"
    assert len(legit) >= MINIMUM_LEGIT, f"legit {len(legit)} (min {MINIMUM_LEGIT})"
    assert len(scam) >= MINIMUM_SCAM, f"scam {len(scam)} (min {MINIMUM_SCAM})"
    assert (
        len(hard) >= MINIMUM_HARD_NEGATIVES
    ), f"hard_negative {len(hard)} (min {MINIMUM_HARD_NEGATIVES})"
    for group in ("payment", "contact", "urgency", "compensation", "listing_quality"):
        count = sum(1 for case in scam if group in case.indicator_groups)
        assert (
            count >= MINIMUM_PER_INDICATOR
        ), f"{group}: expected at least {MINIMUM_PER_INDICATOR} scams, got {count}"


def test_scam_dataset_diversity() -> None:
    """
    Require measurable diversity on written postings (limits S1 to S8).

    Returns:
        None.
    """
    cases = _load_cases()
    violations, stats = _diversity_stats(cases)
    violations.extend(_voice_violations(cases))
    assert not violations, {"violations": violations, "stats": stats}
