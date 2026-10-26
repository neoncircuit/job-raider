"""
Tests for the local catalog pairs script (Step 3.5 A2c).

The tests use a synthetic catalog under ``tmp_path``. They do not read
the real catalog or print listing text.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from scripts.prepare_dedupe_catalog_pairs import prepare_dedupe_catalog_pairs

RECRUITER_FIELDS = (
    "recruiter_name",
    "recruiter_email",
    "recruiter_phone",
    "raw_html",
    "metadata",
)


def _listing(
    job_id: str,
    company: str,
    title: str,
    *,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build one synthetic catalog listing.

    Args:
        job_id: Listing identifier.
        company: Company name.
        title: Job title.
        extra: Optional extra fields, including recruiter fields.

    Returns:
        A catalog listing object.
    """
    row: Dict[str, Any] = {
        "job_id": job_id,
        "source": "jobstreet",
        "source_url": f"https://www.jobstreet.com.sg/job/{job_id}",
        "title": title,
        "company": company,
        "location": "Singapore",
        "description": "Keep the book current. File the sheet at noon.",
        "posted_date": "2026-10-01T00:00:00+00:00",
        "recruiter_name": "Do Not Store",
        "recruiter_email": "hidden@example.com",
        "recruiter_phone": "00000000",
        "raw_html": "<p>hidden</p>",
        "metadata": {"secret": True},
    }
    if extra:
        row.update(extra)
    return row


def _write_catalog(path: Path, listings: Dict[str, Dict[str, Any]]) -> None:
    """
    Write a synthetic catalog JSON file.

    Args:
        path: Destination path.
        listings: Mapping of job id to listing.

    Returns:
        None.
    """
    path.write_text(
        json.dumps({"updated_at": "2026-10-26T00:00:00Z", "listings": listings}),
        encoding="utf-8",
    )


def test_pair_count_and_no_recruiter_fields(tmp_path: Path) -> None:
    """
    Emit one pair per two listings that share a company and title.

    Args:
        tmp_path: Temporary catalog and output folder.

    Returns:
        None.
    """
    catalog = tmp_path / "catalog.json"
    output = tmp_path / "cases.jsonl"
    _write_catalog(
        catalog,
        {
            "js-1": _listing("js-1", "Harbourline", "Harbour Clerk"),
            "js-2": _listing("js-2", "Harbourline", "Harbour Clerk"),
            "js-3": _listing("js-3", "Harbourline", "Harbour Clerk"),
            "js-4": _listing("js-4", "Tidewell Instruments", "Analyst"),
            "js-5": _listing("js-5", "Tidewell Instruments", "Other Role"),
        },
    )
    groups, pairs = prepare_dedupe_catalog_pairs(catalog, output)
    assert groups == 1
    assert pairs == 3
    rows = [
        json.loads(line)
        for line in output.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 3
    for row in rows:
        assert row["class"] == "catalog"
        assert row["expected"] == "TODO"
        assert row["source"] == "catalog"
        for side in ("a", "b"):
            listing = row[side]
            for field in RECRUITER_FIELDS:
                assert field not in listing
            assert set(listing) <= {
                "job_id",
                "source",
                "source_url",
                "title",
                "company",
                "location",
                "description",
                "posted_date",
            }


def test_does_not_overwrite_a_labeled_file(tmp_path: Path) -> None:
    """
    Leave a labeled cases file unchanged.

    Args:
        tmp_path: Temporary catalog and output folder.

    Returns:
        None.
    """
    catalog = tmp_path / "catalog.json"
    output = tmp_path / "cases.jsonl"
    _write_catalog(
        catalog,
        {
            "js-1": _listing("js-1", "Harbourline", "Harbour Clerk"),
            "js-2": _listing("js-2", "Harbourline", "Harbour Clerk"),
        },
    )
    original = (
        json.dumps(
            {
                "case_id": "catalog__kept",
                "class": "catalog",
                "expected": "same",
                "a": {"job_id": "kept-a"},
                "b": {"job_id": "kept-b"},
                "source": "catalog",
                "note": "user label",
            }
        )
        + "\n"
    )
    output.write_text(original, encoding="utf-8")
    groups, pairs = prepare_dedupe_catalog_pairs(catalog, output)
    assert groups == 1
    assert pairs == 1
    assert output.read_text(encoding="utf-8") == original
