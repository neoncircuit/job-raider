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
MINIMUM_LONG_SCAMS = 2
MINIMUM_SCAM_OVER_150 = 4
MINIMUM_SHORT_WRITTEN_LEGIT = 3
MINIMUM_SHORT_LISTING = 2
MINIMUM_LISTING_WORDS = 8
MINIMUM_OTHER_WRITTEN_WORDS = 30
MAXIMUM_WRITTEN_WORDS = 450
MINIMUM_LEGIT_WITH_BREAKS = 6
MINIMUM_SCAM_WITH_BREAKS = 8
MINIMUM_HARD_WITH_BREAKS = 2
MINIMUM_HARD_ONE_LINE = 2
MAX_ANTI_SCAM_LEGIT = 3
MAX_CASES_PER_COMPANY = 2
MAX_OPENING_CASES = 4

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
NARRATOR_PHRASES = (
    "the listing",
    "this listing",
    "the text says",
    "the page",
    "the vacancy is",
    "does not fit",
    "cannot fit",
    "a recruiter can",
    "public register",
    "the purpose is",
    "the real step",
    "is not named",
    "names no",
    "nothing here",
    "is a shell",
    "the rush is",
)
ANTI_SCAM_PATTERNS = (
    r"never ask(s)?\b",
    r"does not (ask|charge|hire|request)",
    r"do(es)? not (buy|purchase|pay|move|complete)",
    r"no (applicant|application|placement|training) fee",
    r"\bno kit\b",
    r"not a (paid|work-from-home|trading)",
)
FORBIDDEN_COMPANY_WORDS = frozenset(
    {
        "generic",
        "blank",
        "vague",
        "hollow",
        "shadow",
        "quiet",
        "instant",
        "sameday",
        "flash",
        "rapid",
        "quick",
        "empty",
        "fake",
        "shell",
        "secret",
        "mystery",
    }
)

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


def _sentence_opening_keys(text: str, company: str) -> List[str]:
    """
    Return the first four words of each sentence, with the company slotted.

    Args:
        text: Posting description.
        company: Company name.

    Returns:
        One opening per sentence that has words.
    """
    joined = " ".join((text or "").split())
    if company:
        joined = re.sub(re.escape(company), "<co>", joined, flags=re.IGNORECASE)
    keys: List[str] = []
    for part in _SENTENCE_BREAK.split(joined):
        words = part.lower().split()
        if words:
            keys.append(" ".join(words[:4]))
    return keys


def _has_line_break(text: str) -> bool:
    """
    Return whether a description contains a line break.

    Args:
        text: Posting description.

    Returns:
        True when the text contains ``\\n``.
    """
    return "\n" in (text or "")


def _matches_any(text: str, patterns: Sequence[str]) -> bool:
    """
    Return whether any regex matches the text.

    Args:
        text: Title and description.
        patterns: Regular expressions.

    Returns:
        True when a pattern matches.
    """
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


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
        description = str(case.job.get("description") or "")
        company = str(case.job.get("company") or "")
        posting_open = _opening_key(description, company)
        if posting_open:
            openings[posting_open].add(case.case_id)
        for key in _sentence_opening_keys(description, company):
            openings[key].add(case.case_id)
    max_opening_cases = max((len(ids) for ids in openings.values()), default=0)
    companies = [str(case.job.get("company") or "") for case in cases]
    company_counts = Counter(companies)
    word_by_case = {
        case.case_id: len(str(case.job.get("description") or "").split())
        for case in written
    }
    word_counts = list(word_by_case.values())
    long_written = sum(count > 200 for count in word_counts)
    long_scams = sum(
        word_by_case[case.case_id] > 200 for case in written if case.expected == "scam"
    )
    listing_words = [
        word_by_case[case.case_id]
        for case in written
        if _case_group(case.case_id) == "scam_listing"
    ]
    other_words = [
        word_by_case[case.case_id]
        for case in written
        if _case_group(case.case_id) != "scam_listing"
    ]
    written_legit = [
        case
        for case in written
        if _case_group(case.case_id) in {"legit_written", "hard_negative"}
    ]
    hard = [case for case in written if _case_group(case.case_id) == "hard_negative"]
    scams = [case for case in written if case.expected == "scam"]
    legit_breaks = sum(
        1
        for case in written_legit
        if _has_line_break(str(case.job.get("description") or ""))
    )
    scam_breaks = sum(
        1 for case in scams if _has_line_break(str(case.job.get("description") or ""))
    )
    hard_breaks = sum(
        1 for case in hard if _has_line_break(str(case.job.get("description") or ""))
    )
    hard_one_line = len(hard) - hard_breaks
    narrator = [
        case.case_id
        for case in written
        if any(
            phrase
            in f"{case.job.get('title') or ''} {case.job.get('description') or ''}".lower()
            for phrase in NARRATOR_PHRASES
        )
    ]
    anti_scam = [
        case.case_id
        for case in written_legit
        if _matches_any(
            f"{case.job.get('title') or ''} {case.job.get('description') or ''}",
            ANTI_SCAM_PATTERNS,
        )
    ]
    company_word_hits = [
        f"{case.case_id}:{case.job.get('company')}"
        for case in written
        if any(
            word.lower() in FORBIDDEN_COMPANY_WORDS
            for word in re.findall(r"[A-Za-z]+", str(case.job.get("company") or ""))
        )
    ]
    scams_over_150 = sum(1 for case in scams if word_by_case[case.case_id] > 150)
    short_legit = sum(1 for case in written_legit if word_by_case[case.case_id] < 100)
    short_listing = sum(1 for count in listing_words if count < 20)

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
        "s8_listing_min_words": min(listing_words, default=0),
        "s8_other_min_words": min(other_words, default=0),
        "s8_max_words": max(word_counts, default=0),
        "s8_written_over_200": long_written,
        "s8_scams_over_200": long_scams,
        "s9_narrator_cases": narrator,
        "s10_anti_scam_cases": anti_scam,
        "s11_company_word_hits": company_word_hits,
        "s12_legit_with_breaks": legit_breaks,
        "s12_scam_with_breaks": scam_breaks,
        "s12_hard_with_breaks": hard_breaks,
        "s12_hard_one_line": hard_one_line,
        "s13_scams_over_150": scams_over_150,
        "s13_short_written_legit": short_legit,
        "s13_short_listing": short_listing,
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
    if max_opening_cases > MAX_OPENING_CASES:
        violations.append(
            f"S5: a 4-word opening appears in {max_opening_cases} cases "
            f"(max {MAX_OPENING_CASES})"
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
    if any(
        count < MINIMUM_LISTING_WORDS or count > MAXIMUM_WRITTEN_WORDS
        for count in listing_words
    ):
        violations.append(
            "S8: a scam_listing posting is outside 8 to 450 words; "
            f"min {min(listing_words, default=0)}, max {max(listing_words, default=0)}"
        )
    if any(
        count < MINIMUM_OTHER_WRITTEN_WORDS or count > MAXIMUM_WRITTEN_WORDS
        for count in other_words
    ):
        violations.append(
            "S8: a non-listing written posting is outside 30 to 450 words; "
            f"min {min(other_words, default=0)}, max {max(other_words, default=0)}"
        )
    if long_written < MINIMUM_LONG_WRITTEN:
        violations.append(
            f"S8: {long_written} written postings over 200 words "
            f"(min {MINIMUM_LONG_WRITTEN})"
        )
    if long_scams < MINIMUM_LONG_SCAMS:
        violations.append(
            f"S8: {long_scams} written scams over 200 words "
            f"(min {MINIMUM_LONG_SCAMS})"
        )
    if narrator:
        violations.append(f"S9: narrator phrases in {narrator}")
    if len(anti_scam) > MAX_ANTI_SCAM_LEGIT:
        violations.append(
            f"S10: {len(anti_scam)} written legitimate postings have an "
            f"anti-scam sentence (max {MAX_ANTI_SCAM_LEGIT}): {anti_scam}"
        )
    if HARD_NEGATIVE_ANTIFRAUD_ID not in anti_scam:
        violations.append(
            f"S10: {HARD_NEGATIVE_ANTIFRAUD_ID} must match an anti-scam sentence"
        )
    if company_word_hits:
        violations.append(f"S11: company names use banned words: {company_word_hits}")
    if legit_breaks < MINIMUM_LEGIT_WITH_BREAKS:
        violations.append(
            f"S12: {legit_breaks} written legitimate postings have line breaks "
            f"(min {MINIMUM_LEGIT_WITH_BREAKS})"
        )
    if scam_breaks < MINIMUM_SCAM_WITH_BREAKS:
        violations.append(
            f"S12: {scam_breaks} scams have line breaks "
            f"(min {MINIMUM_SCAM_WITH_BREAKS})"
        )
    if hard_breaks < MINIMUM_HARD_WITH_BREAKS:
        violations.append(
            f"S12: {hard_breaks} hard negatives have line breaks "
            f"(min {MINIMUM_HARD_WITH_BREAKS})"
        )
    if hard_one_line < MINIMUM_HARD_ONE_LINE:
        violations.append(
            f"S12: {hard_one_line} hard negatives stay on one line "
            f"(min {MINIMUM_HARD_ONE_LINE})"
        )
    if scams_over_150 < MINIMUM_SCAM_OVER_150:
        violations.append(
            f"S13: {scams_over_150} scams over 150 words "
            f"(min {MINIMUM_SCAM_OVER_150})"
        )
    if short_legit < MINIMUM_SHORT_WRITTEN_LEGIT:
        violations.append(
            f"S13: {short_legit} written legitimate postings under 100 words "
            f"(min {MINIMUM_SHORT_WRITTEN_LEGIT})"
        )
    if short_listing < MINIMUM_SHORT_LISTING:
        violations.append(
            f"S13: {short_listing} scam_listing postings under 20 words "
            f"(min {MINIMUM_SHORT_LISTING})"
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
    Require measurable diversity on written postings (limits S1 to S13).

    Returns:
        None.
    """
    cases = _load_cases()
    violations, stats = _diversity_stats(cases)
    violations.extend(_voice_violations(cases))
    assert not violations, {"violations": violations, "stats": stats}
