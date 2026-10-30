"""Tests for the labeling page of the real-letter set (Step 3.2 real letters, MH-B)."""

import json
import re
from pathlib import Path
from typing import Any, Dict

import pytest

from scripts import build_grounding_label_page as page
from src.evaluation.suites.grounding import GROUNDING_LABELS
from src.generation.cover_letter_grounding import split_letter_sentences
from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile

LETTER = (
    "Dear team, I am applying for the backend role. "
    "I built a FastAPI service for payments! "
    "Did I also run Kafka for five years? "
    "Thank you for your time."
)
DRAFT = {
    "expected_issues": ["fabricated_technology", "ungrounded_claims"],
    "ungrounded_sentences": ["Did I also run Kafka  for five years?"],
    "note": "Kafka is not in the profile.",
}


def letter_record(
    job: JobListing, case_id: str = "real__01", letter: str = LETTER
) -> Dict[str, Any]:
    """Build one letter record in the MH-A format.

    Args:
        job: The job.
        case_id: The case ID.
        letter: The letter text.

    Returns:
        A letter record.
    """
    return {
        "case_id": case_id,
        "profile_id": "real",
        "job": job.model_dump(mode="json"),
        "selection": None,
        "letter": letter,
    }


def embedded_data(html: str) -> Dict[str, Any]:
    """Read the JSON data that the page embeds.

    Args:
        html: The page.

    Returns:
        The decoded page data.
    """
    match = re.search(
        r'<script type="application/json" id="page-data">(.*?)</script>', html, re.S
    )
    assert match is not None
    return json.loads(match.group(1))


def test_guide_definitions_reads_every_label() -> None:
    """The committed guide gives a definition for each of the 8 labels."""
    definitions = page.guide_definitions(page.GUIDE_PATH.read_text(encoding="utf-8"))

    assert set(definitions) == set(GROUNDING_LABELS)
    assert definitions["fabricated_technology"].startswith(
        "Use this label when the letter claims a technology"
    )
    assert "Sentence labels" not in definitions["ungrounded_claims"]


def test_cases_use_the_suite_sentence_split(
    sample_job_listing: JobListing, sample_user_profile: UserProfile
) -> None:
    """Each case has the suite's sentences and empty start values without a draft."""
    data = page.build_page_data(
        [letter_record(sample_job_listing)],
        {"real": sample_user_profile.model_dump(mode="json")},
        {},
        {},
    )

    case = data["cases"][0]
    assert case["sentences"] == split_letter_sentences(LETTER)
    assert len(case["sentences"]) == 4
    assert case["start"] == {
        "expected_issues": [],
        "ungrounded": [],
        "note": "",
        "reviewed": False,
    }
    assert data["labels"] == list(GROUNDING_LABELS)


def test_drafts_become_the_start_values(sample_job_listing: JobListing) -> None:
    """A draft gives the start labels; ungrounded_claims comes from the sentences."""
    data = page.build_page_data(
        [letter_record(sample_job_listing)], {}, {"real__01": DRAFT}, {}
    )

    assert data["cases"][0]["start"] == {
        "expected_issues": ["fabricated_technology"],
        "ungrounded": [2],
        "note": "Kafka is not in the profile.",
        "reviewed": False,
    }


@pytest.mark.parametrize(
    ("drafts", "message"),
    [
        ({"real__09": {}}, "unknown cases"),
        ({"real__01": {"expected_issues": ["made_up_label"]}}, "unknown labels"),
        (
            {"real__01": {"ungrounded_sentences": ["I led a team of ten."]}},
            "not in the letter",
        ),
    ],
    ids=["unknown case", "unknown label", "sentence not in the letter"],
)
def test_bad_drafts_stop_the_build(
    sample_job_listing: JobListing, drafts: Dict[str, Any], message: str
) -> None:
    """A draft for an unknown case, label, or sentence raises a clear ValueError."""
    with pytest.raises(ValueError, match=message):
        page.build_page_data([letter_record(sample_job_listing)], {}, drafts, {})


def test_page_is_self_contained_and_escapes_the_data(
    sample_job_listing: JobListing,
) -> None:
    """Letter text cannot close the data script, and the page loads nothing."""
    letter = "Dear team, see </script><script>alert(1)</script> here. Thank you."
    data = page.build_page_data(
        [letter_record(sample_job_listing, letter=letter)], {}, {}, {}
    )

    html = page.render_page(data)

    assert "<script>alert(1)" not in html
    assert embedded_data(html)["cases"][0]["sentences"] == split_letter_sentences(
        letter
    )
    assert "<script src" not in html
    assert "<link" not in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "labels.json" in html


def test_main_writes_the_page_next_to_the_letters(
    tmp_path: Path, sample_job_listing: JobListing, sample_user_profile: UserProfile
) -> None:
    """main reads the folder, uses drafts.json, and writes label.html."""
    record = letter_record(sample_job_listing)
    (tmp_path / "letters.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    (tmp_path / "profiles.json").write_text(
        json.dumps({"real": sample_user_profile.model_dump(mode="json")}),
        encoding="utf-8",
    )
    (tmp_path / "drafts.json").write_text(
        json.dumps({"real__01": DRAFT}), encoding="utf-8"
    )

    assert page.main(["--dataset", str(tmp_path)]) == 0

    data = embedded_data((tmp_path / "label.html").read_text(encoding="utf-8"))
    assert [case["case_id"] for case in data["cases"]] == ["real__01"]
    assert data["cases"][0]["start"]["ungrounded"] == [2]
    assert set(data["definitions"]) == set(GROUNDING_LABELS)
    assert data["profiles"]["real"]["name"] == sample_user_profile.name


def test_main_stops_without_letters(tmp_path: Path) -> None:
    """main writes nothing when letters.jsonl is missing."""
    assert page.main(["--dataset", str(tmp_path)]) == 1
    assert not (tmp_path / "label.html").exists()
