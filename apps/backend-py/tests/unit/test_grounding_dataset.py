"""
Structural tests for the committed grounding evaluation dataset.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

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
    assert all(120 <= len(case.letter.split()) <= 300 for case in cases)
    assert all(case.note.strip() for case in cases)
    assert all(
        str(profile.contact.email).endswith("@example.com")
        for profile in profiles.values()
    )
