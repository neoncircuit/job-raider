"""
Structural and diversity tests for the committed dedupe evaluation set.

These tests load ``cases.jsonl``. They do not import the dedupe suite
model, and they do not run ``deduplicate``.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple
from urllib.parse import urlparse

from src.models.job_listing import JobListing

DATASET_DIR = Path(__file__).parents[1] / "fixtures" / "eval" / "dedupe"
CASES_PATH = DATASET_DIR / "cases.jsonl"

MINIMUM_TOTAL = 30
MINIMUM_PER_CLASS = 3
C0_COUNT = 2
LABEL_SHARE_LOW = 0.40
LABEL_SHARE_HIGH = 0.60
MINIMUM_COMPANIES = 10
MAX_CASES_PER_COMPANY = 4
MAX_CASES_PER_TITLE = 3
MINIMUM_C1_DIFFERENCE_TYPES = 4

SAME_CLASSES = frozenset({"C0", "C1", "C2", "C3", "C4"})
DIFFERENT_CLASSES = frozenset({"H1", "H2", "H3", "H4", "H5"})
ALL_CLASSES = SAME_CLASSES | DIFFERENT_CLASSES
REQUIRED_FIELDS = frozenset(
    {
        "case_id",
        "class",
        "expected",
        "a",
        "b",
        "source",
        "note",
    }
)
FORBIDDEN_PHRASES = (
    "duplicate",
    "repost",
    "same job",
    "same role",
    "copy of",
    "different job",
)


def _load_rows() -> List[Dict[str, Any]]:
    """
    Load the committed dedupe cases as JSON objects.

    Returns:
        One dictionary per non-blank line, in file order.

    Raises:
        AssertionError: When a line is not a JSON object.
    """
    rows: List[Dict[str, Any]] = []
    text = CASES_PATH.read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        assert isinstance(payload, dict), f"line {number} is not an object"
        rows.append(payload)
    return rows


def _listing_text(listing: Dict[str, Any]) -> str:
    """
    Join the listing fields that a reader sees.

    Args:
        listing: One side of a pair.

    Returns:
        Lowercased title, company, location, and description.
    """
    parts = [
        listing.get("title") or "",
        listing.get("company") or "",
        listing.get("location") or "",
        listing.get("description") or "",
    ]
    return " ".join(str(part) for part in parts).lower()


def _has_sentence(text: str) -> bool:
    """
    Return whether a description has at least one full sentence.

    Args:
        text: Listing description.

    Returns:
        True when the text has a sentence-ending mark and more than one word.
    """
    stripped = " ".join((text or "").split())
    return len(stripped.split()) >= 2 and any(mark in stripped for mark in ".!?")


def _c1_difference_types(row: Dict[str, Any]) -> Set[str]:
    """
    Name the C1 differences that one pair shows.

    Args:
        row: One C1 case.

    Returns:
        Difference type names from the realism list.
    """
    left = row["a"]
    right = row["b"]
    found: Set[str] = set()
    if left.get("company") != right.get("company"):
        found.add("company_suffix_or_punctuation")
    if left.get("title") != right.get("title"):
        found.add("title_case_or_punctuation")
    if left.get("location") != right.get("location"):
        found.add("location_format")
    descriptions = (
        str(left.get("description") or ""),
        str(right.get("description") or ""),
    )
    if any("<" in item and ">" in item for item in descriptions):
        found.add("html_in_one_description")
    if descriptions[0] != descriptions[1]:
        shorter, longer = sorted(descriptions, key=len)
        if shorter and longer.startswith(shorter):
            found.add("shortened_description")
    left_host = urlparse(str(left.get("source_url") or "")).netloc.lower()
    right_host = urlparse(str(right.get("source_url") or "")).netloc.lower()
    if left_host and right_host and left_host != right_host:
        found.add("url_domain")
    return found


def _c3_variant(row: Dict[str, Any]) -> str:
    """
    Name the C3 URL variant that one pair shows.

    Args:
        row: One C3 case.

    Returns:
        ``slash``, ``case``, ``utm``, ``fragment``, or ``unknown``.
    """
    left = str(row["a"].get("source_url") or "")
    right = str(row["b"].get("source_url") or "")
    if left.rstrip("/") == right.rstrip("/") and left != right:
        return "slash"
    if left.lower() == right.lower() and left != right:
        return "case"
    if "utm_" in left.lower() or "utm_" in right.lower():
        return "utm"
    if "#" in left or "#" in right:
        return "fragment"
    return "unknown"


def _diversity_stats(
    rows: Sequence[Dict[str, Any]],
) -> Tuple[List[str], Dict[str, object]]:
    """
    Check company and title diversity limits.

    Args:
        rows: Loaded cases.

    Returns:
        Violations and a stats map. The list is empty when every limit holds.
    """
    companies_per_case: List[Set[str]] = []
    titles_per_case: List[Set[str]] = []
    for row in rows:
        companies_per_case.append(
            {
                str(row["a"].get("company") or ""),
                str(row["b"].get("company") or ""),
            }
        )
        titles_per_case.append(
            {
                str(row["a"].get("title") or ""),
                str(row["b"].get("title") or ""),
            }
        )
    company_cases: Dict[str, Set[str]] = defaultdict(set)
    title_cases: Dict[str, Set[str]] = defaultdict(set)
    for row, companies, titles in zip(rows, companies_per_case, titles_per_case):
        case_id = str(row["case_id"])
        for company in companies:
            company_cases[company].add(case_id)
        for title in titles:
            title_cases[title].add(case_id)
    company_counts = {name: len(ids) for name, ids in company_cases.items()}
    title_counts = {name: len(ids) for name, ids in title_cases.items()}
    stats: Dict[str, object] = {
        "companies": len(company_counts),
        "max_cases_per_company": max(company_counts.values(), default=0),
        "max_cases_per_title": max(title_counts.values(), default=0),
        "company_counts": dict(sorted(company_counts.items())),
        "title_counts": dict(sorted(title_counts.items())),
    }
    violations: List[str] = []
    if len(company_counts) < MINIMUM_COMPANIES:
        violations.append(
            f"{len(company_counts)} distinct companies (min {MINIMUM_COMPANIES})"
        )
    over_company = [
        f"{name}={count}"
        for name, count in company_counts.items()
        if count > MAX_CASES_PER_COMPANY
    ]
    if over_company:
        violations.append(
            f"a company is in more than {MAX_CASES_PER_COMPANY} cases: {over_company}"
        )
    over_title = [
        f"{name}={count}"
        for name, count in title_counts.items()
        if count > MAX_CASES_PER_TITLE
    ]
    if over_title:
        violations.append(
            f"a title is in more than {MAX_CASES_PER_TITLE} cases: {over_title}"
        )
    return violations, stats


def test_dedupe_dataset_structure_and_counts() -> None:
    """
    Validate schemas, IDs, labels, listings, and class counts.

    Returns:
        None.
    """
    rows = _load_rows()
    ids = [str(row["case_id"]) for row in rows]
    duplicates = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    assert not duplicates, f"duplicate case_id values: {duplicates}"

    class_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    for row in rows:
        missing = REQUIRED_FIELDS - set(row)
        assert not missing, f"{row.get('case_id')}: missing {sorted(missing)}"
        case_id = str(row["case_id"])
        pair_class = str(row["class"])
        expected = str(row["expected"])
        assert pair_class in ALL_CLASSES, f"{case_id}: unknown class {pair_class}"
        assert case_id.startswith(f"{pair_class.lower()}__"), case_id
        if pair_class in SAME_CLASSES:
            assert expected == "same", case_id
        else:
            assert expected == "different", case_id
        assert row["source"] in {"constructed"} or str(row["source"]).startswith(
            "fixture:"
        ), f"{case_id}: bad source"
        assert str(row["note"]).strip(), f"{case_id}: empty note"
        for side in ("a", "b"):
            listing = row[side]
            assert isinstance(listing, dict), f"{case_id}: {side} is not an object"
            JobListing.model_validate(listing)
            assert _has_sentence(
                str(listing.get("description") or "")
            ), f"{case_id}: {side} description has no sentence"
        if pair_class == "C0":
            assert row["a"]["job_id"] == row["b"]["job_id"], case_id
        else:
            assert row["a"]["job_id"] != row["b"]["job_id"], case_id
        class_counts[pair_class] += 1
        label_counts[expected] += 1

    assert (
        len(rows) >= MINIMUM_TOTAL
    ), f"expected at least {MINIMUM_TOTAL}, got {len(rows)}"
    assert class_counts["C0"] == C0_COUNT, f"C0 count {class_counts['C0']}"
    for pair_class in sorted(ALL_CLASSES - {"C0"}):
        count = class_counts[pair_class]
        assert (
            count >= MINIMUM_PER_CLASS
        ), f"{pair_class}: expected at least {MINIMUM_PER_CLASS}, got {count}"
    same_share = label_counts["same"] / len(rows)
    different_share = label_counts["different"] / len(rows)
    assert (
        LABEL_SHARE_LOW <= same_share <= LABEL_SHARE_HIGH
    ), f"same share {same_share:.3f} is outside 0.40 to 0.60"
    assert (
        LABEL_SHARE_LOW <= different_share <= LABEL_SHARE_HIGH
    ), f"different share {different_share:.3f} is outside 0.40 to 0.60"


def test_dedupe_dataset_listing_voice() -> None:
    """
    Reject listing text that states the label or the class.

    Returns:
        None.
    """
    hits: List[str] = []
    for row in _load_rows():
        for side in ("a", "b"):
            text = _listing_text(row[side])
            for phrase in FORBIDDEN_PHRASES:
                if phrase in text:
                    hits.append(f"{row['case_id']} {side} contains {phrase!r}")
    assert not hits, hits


def test_dedupe_dataset_diversity() -> None:
    """
    Require measurable company and title diversity.

    Returns:
        None.
    """
    violations, stats = _diversity_stats(_load_rows())
    assert not violations, {"violations": violations, "stats": stats}


def test_dedupe_dataset_c1_and_c3_coverage() -> None:
    """
    Require the C1 difference types and the C3 URL variants.

    Returns:
        None.
    """
    rows = _load_rows()
    c1_types: Set[str] = set()
    for row in rows:
        if row["class"] == "C1":
            c1_types.update(_c1_difference_types(row))
    assert (
        len(c1_types) >= MINIMUM_C1_DIFFERENCE_TYPES
    ), f"C1 difference types {sorted(c1_types)}"
    c3_variants = {_c3_variant(row) for row in rows if row["class"] == "C3"}
    assert c3_variants >= {
        "slash",
        "case",
        "utm",
        "fragment",
    }, f"C3 variants {sorted(c3_variants)}"
