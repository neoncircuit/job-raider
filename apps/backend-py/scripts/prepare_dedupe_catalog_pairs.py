"""
Write unlabeled catalog pairs for the local dedupe check.

The script reads ``data/listings/catalog.json``, groups listings by
normalized company and title, and writes every pair in a group of two or
more to ``data/dedupe_catalog/cases.jsonl``. It prints group and pair
counts only. It does not overwrite a file that already has a label other
than ``TODO``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Sequence, Tuple

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.metrics.outcome_tracker import normalize_match_label  # noqa: E402

DEFAULT_CATALOG_PATH = _BACKEND_ROOT / "data" / "listings" / "catalog.json"
DEFAULT_OUTPUT_PATH = _BACKEND_ROOT / "data" / "dedupe_catalog" / "cases.jsonl"
KEEP_FIELDS: Tuple[str, ...] = (
    "job_id",
    "source",
    "source_url",
    "title",
    "company",
    "location",
    "description",
    "posted_date",
)


def _listing_fields(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Keep the listing fields that a pair case may store.

    Args:
        raw: One catalog listing.

    Returns:
        The keep-list fields that are present and not None.
    """
    kept: Dict[str, Any] = {}
    for key in KEEP_FIELDS:
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if key == "source_url":
            value = str(value)
        kept[key] = value
    return kept


def _group_key(listing: Mapping[str, Any]) -> Tuple[str, str]:
    """
    Return the normalized company and title for one listing.

    Args:
        listing: One catalog listing.

    Returns:
        ``(company, title)`` after ``normalize_match_label``.
    """
    company = normalize_match_label(str(listing.get("company") or ""))
    title = normalize_match_label(str(listing.get("title") or ""))
    return company, title


def _pair_case_id(left_id: str, right_id: str) -> str:
    """
    Build a stable catalog case id from two job ids.

    Args:
        left_id: First job id.
        right_id: Second job id.

    Returns:
        ``catalog__<16 hex chars>``.
    """
    first, second = sorted((left_id, right_id))
    digest = hashlib.sha256(f"{first}\0{second}".encode("utf-8")).hexdigest()[:16]
    return f"catalog__{digest}"


def _has_labeled_row(path: Path) -> bool:
    """
    Return whether a cases file has a label other than ``TODO``.

    Args:
        path: Existing or missing JSONL file.

    Returns:
        True when any row has ``expected`` other than ``TODO``.
    """
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("expected") != "TODO":
            return True
    return False


def _pairs_from_groups(
    groups: Mapping[Tuple[str, str], Sequence[Mapping[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Build one case object for every pair in each multi-listing group.

    Args:
        groups: Listings keyed by normalized company and title.

    Returns:
        Case objects in group order, then job-id order.
    """
    cases: List[Dict[str, Any]] = []
    for key in sorted(groups):
        members = sorted(
            groups[key],
            key=lambda item: str(item.get("job_id") or ""),
        )
        if len(members) < 2:
            continue
        for left, right in combinations(members, 2):
            left_id = str(left.get("job_id") or "")
            right_id = str(right.get("job_id") or "")
            cases.append(
                {
                    "case_id": _pair_case_id(left_id, right_id),
                    "class": "catalog",
                    "expected": "TODO",
                    "a": _listing_fields(left),
                    "b": _listing_fields(right),
                    "source": "catalog",
                    "note": "Generated from the local catalog. Label before the suite runs.",
                }
            )
    return cases


def prepare_dedupe_catalog_pairs(
    catalog_path: Path,
    output_path: Path,
) -> Tuple[int, int]:
    """
    Group the catalog and write unlabeled pairs.

    Args:
        catalog_path: Catalog JSON with a ``listings`` object.
        output_path: Destination JSONL file.

    Returns:
        ``(group_count, pair_count)`` from the catalog. The file is not
        written when it already has a label other than ``TODO``.

    Raises:
        FileNotFoundError: When the catalog is missing.
        ValueError: When the catalog shape is invalid.
    """
    if not catalog_path.is_file():
        raise FileNotFoundError(f"catalog not found: {catalog_path}")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("listings"), dict):
        raise ValueError("catalog must be an object with a listings object")
    listings = payload["listings"]
    groups: DefaultDict[Tuple[str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for listing in listings.values():
        if isinstance(listing, dict):
            groups[_group_key(listing)].append(listing)
    multi = {key: items for key, items in groups.items() if len(items) > 1}
    cases = _pairs_from_groups(multi)
    if not _has_labeled_row(output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(json.dumps(case, ensure_ascii=True) + "\n" for case in cases),
            encoding="utf-8",
        )
    return len(multi), len(cases)


def main(argv: Iterable[str] | None = None) -> int:
    """
    Run the script with the default catalog and output paths.

    Args:
        argv: Unused. Kept so tests can call ``main``.

    Returns:
        Exit code 0 on success, 1 when the catalog is missing or invalid.
    """
    del argv
    try:
        groups, pairs = prepare_dedupe_catalog_pairs(
            DEFAULT_CATALOG_PATH, DEFAULT_OUTPUT_PATH
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1
    print(f"groups={groups}")
    print(f"pairs={pairs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
