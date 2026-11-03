"""Format tests for the Step 3.4 ranking set (``tests/fixtures/eval/ranking``)."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile

SET_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "eval" / "ranking"


def read_jsonl(name: str) -> List[Dict[str, Any]]:
    """
    Read one JSON Lines file of the set.

    Args:
        name: The file name.

    Returns:
        One dictionary for each non-empty line.
    """
    text = (SET_DIR / name).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def read_json(name: str) -> Dict[str, Any]:
    """
    Read one JSON file of the set.

    Args:
        name: The file name.

    Returns:
        The parsed object.
    """
    data: Dict[str, Any] = json.loads((SET_DIR / name).read_text(encoding="utf-8"))
    return data


def test_profiles_are_valid_and_have_modes() -> None:
    """Each profile validates and has the matcher mode of the pipeline."""
    profiles = read_json("profiles.json")
    modes = read_json("modes.json")

    assert set(profiles) == {"fresh_ml", "mid_backend"}
    assert set(modes) == set(profiles)
    for profile_id, data in profiles.items():
        UserProfile.model_validate(data)
        assert isinstance(modes[profile_id]["fresh_grad_mode"], bool)
    assert modes["fresh_ml"]["fresh_grad_mode"] is True
    assert modes["mid_backend"]["fresh_grad_mode"] is False


def test_jobs_are_valid_with_unique_ids() -> None:
    """Each job validates, and the job IDs are unique and numbered."""
    jobs = read_jsonl("jobs.jsonl")
    ids = [job["job_id"] for job in jobs]

    assert len(jobs) == 70
    assert len(set(ids)) == len(ids)
    for job in jobs:
        JobListing.model_validate(job)
        assert re.fullmatch(r"rk-\d{3}", job["job_id"]), job["job_id"]


def test_each_profile_has_one_label_for_each_job() -> None:
    """Each profile and job pair has exactly one label of 0, 1, or 2 with a reason."""
    profiles = read_json("profiles.json")
    job_ids = {job["job_id"] for job in read_jsonl("jobs.jsonl")}
    labels = read_jsonl("labels.jsonl")
    pairs = Counter((row["profile_id"], row["job_id"]) for row in labels)

    assert set(pairs) == {(p, j) for p in profiles for j in job_ids}
    assert set(pairs.values()) == {1}
    for row in labels:
        assert row["label"] in (0, 1, 2), row
        assert row["reason"].strip(), row


def test_each_profile_has_relevant_and_irrelevant_jobs() -> None:
    """Each profile has enough jobs of each label for the ranking metrics."""
    labels = read_jsonl("labels.jsonl")

    for profile_id in ("fresh_ml", "mid_backend"):
        counts = Counter(r["label"] for r in labels if r["profile_id"] == profile_id)
        assert counts[2] >= 5, (profile_id, counts)
        assert counts[1] >= 5, (profile_id, counts)
        assert counts[0] >= 20, (profile_id, counts)


def test_the_guide_states_the_label_rules() -> None:
    """The labeling guide defines each label and the rule to label first."""
    guide = (SET_DIR / "README.md").read_text(encoding="utf-8")

    for heading in ("### `2` (apply)", "### `1` (maybe)", "### `0` (not relevant)"):
        assert heading in guide
    assert "Write Labels Before Any Ranker Runs" in guide
