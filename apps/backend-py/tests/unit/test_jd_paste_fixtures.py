"""
Golden tests for messy JD paste fixtures.

Fixtures live under ``tests/fixtures/jd_paste/`` and encode real highlight-drag
cases (LinkedIn chrome, Greenhouse HTML crumbs, mid-cut paste, prose-only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.extractors.paste_job import build_job_listing_from_paste

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "jd_paste"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"


def _load_manifest() -> list[dict]:
    """Load fixture expectations from the paste manifest."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return payload["fixtures"]


@pytest.mark.parametrize(
    "case",
    _load_manifest(),
    ids=lambda case: case["id"],
)
def test_jd_paste_fixture(case: dict) -> None:
    """
    Each messy paste fixture cleans and structures to the golden contract.
    """
    raw = (FIXTURE_DIR / case["file"]).read_text(encoding="utf-8")
    job = build_job_listing_from_paste(
        title=case["title"],
        company=case["company"],
        description=raw,
        job_id=f"fixture-{case['id']}",
    )

    description = job.description or ""
    for needle in case["must_contain_in_description"]:
        assert needle in description, f"missing {needle!r} in cleaned description"

    lowered = description.lower()
    for needle in case["must_not_contain_in_description"]:
        assert needle.lower() not in lowered, f"still contains {needle!r}"

    skill_names = {s.name.lower() for s in job.skills}
    for skill in case["required_skills"]:
        assert (
            skill in skill_names
        ), f"missing skill {skill!r}; got {sorted(skill_names)}"

    assert len(job.requirements) >= case["min_requirements"]

    if case.get("allow_trailing_truncation"):
        assert not description.rstrip().endswith("-")
