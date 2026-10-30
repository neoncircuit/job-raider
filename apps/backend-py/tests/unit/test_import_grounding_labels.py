"""Tests for the label import of the real-letter set (Step 3.2 real letters, MH-C)."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from scripts import import_grounding_labels as imp
from src.evaluation.datasets import load_jsonl
from src.evaluation.suites.grounding import GroundingCase
from src.models.job_listing import JobListing

LETTER = (
    "Dear team, I am applying for the backend role. "
    "I built a FastAPI service for payments! "
    "Did I also run Kafka for five years? "
    "Thank you for your time."
)


def letter_record(job: JobListing, case_id: str = "real__01") -> Dict[str, Any]:
    """Build one letter record in the MH-A format.

    Args:
        job: The job.
        case_id: The case ID.

    Returns:
        A letter record.
    """
    return {
        "case_id": case_id,
        "profile_id": "real",
        "job": job.model_dump(mode="json"),
        "selection": None,
        "letter": LETTER,
    }


def label_entry(**changes: Any) -> Dict[str, Any]:
    """Build one reviewed label entry, as the MH-B page exports it.

    Args:
        **changes: Fields to change.

    Returns:
        A label entry.
    """
    entry: Dict[str, Any] = {
        "expected_issues": ["fabricated_technology", "ungrounded_claims"],
        "ungrounded_sentences": ["Did I also run Kafka for five years?"],
        "note": "Kafka is not in the profile.",
        "reviewed": True,
    }
    entry.update(changes)
    return entry


def write_dataset(folder: Path, records: List[Dict[str, Any]]) -> None:
    """Write letters.jsonl in a dataset folder.

    Args:
        folder: The dataset folder.
        records: The letter records.
    """
    folder.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record) + "\n" for record in records]
    (folder / "letters.jsonl").write_text("".join(lines), encoding="utf-8")


def test_build_cases_sets_ungrounded_claims_from_the_sentences(
    sample_job_listing: JobListing,
) -> None:
    """ungrounded_claims follows the sentence list, and labels keep the suite order."""
    letters = [
        letter_record(sample_job_listing, "real__01"),
        letter_record(sample_job_listing, "real__02"),
    ]
    labels = {
        "real__01": label_entry(
            expected_issues=[
                "scope_inflation",
                "fabricated_experience",
                "inflated_duration",
            ],
            ungrounded_sentences=["Did I also run Kafka  for five years?"],
        ),
        "real__02": label_entry(
            expected_issues=["ungrounded_claims"], ungrounded_sentences=[]
        ),
    }

    cases = imp.build_cases(letters, labels)

    assert cases[0].expected_issues == [
        "inflated_duration",
        "fabricated_experience",
        "scope_inflation",
        "ungrounded_claims",
    ]
    assert cases[0].ungrounded_sentences == ["Did I also run Kafka for five years?"]
    assert cases[0].note == "Kafka is not in the profile."
    assert cases[1].expected_issues == []
    assert cases[1].ungrounded_sentences == []


@pytest.mark.parametrize(
    ("labels", "message"),
    [
        ({}, "letters without labels"),
        (
            {"real__01": label_entry(), "real__09": label_entry()},
            "labels for unknown cases",
        ),
        ({"real__01": label_entry(reviewed=False)}, "not marked as reviewed"),
        (
            {"real__01": label_entry(expected_issues=["made_up_label"])},
            "unknown labels",
        ),
        (
            {"real__01": label_entry(ungrounded_sentences=["I led a team of ten."])},
            "not a letter sentence",
        ),
    ],
    ids=["missing", "unknown case", "not reviewed", "unknown label", "bad sentence"],
)
def test_bad_labels_stop_the_import(
    sample_job_listing: JobListing, labels: Dict[str, Any], message: str
) -> None:
    """Each problem in labels.json stops the import with a clear message."""
    with pytest.raises(ValueError, match=message):
        imp.build_cases([letter_record(sample_job_listing)], labels)


def test_main_writes_cases_that_the_suite_loads(
    tmp_path: Path, sample_job_listing: JobListing
) -> None:
    """main writes cases.jsonl in the suite format and keeps a copy of the labels."""
    dataset = tmp_path / "grounding_real"
    write_dataset(dataset, [letter_record(sample_job_listing)])
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    labels_text = json.dumps({"real__01": label_entry()})
    (downloads / "labels.json").write_text(labels_text, encoding="utf-8")

    code = imp.main(
        ["--dataset", str(dataset), "--labels", str(downloads / "labels.json")]
    )

    assert code == 0
    cases = load_jsonl(dataset / "cases.jsonl", GroundingCase)
    assert [case.case_id for case in cases] == ["real__01"]
    assert cases[0].expected_issues == ["fabricated_technology", "ungrounded_claims"]
    assert (dataset / "labels.json").read_text(encoding="utf-8") == labels_text


def test_main_keeps_frozen_cases(
    tmp_path: Path, sample_job_listing: JobListing
) -> None:
    """An existing cases.jsonl is replaced only with --force."""
    write_dataset(tmp_path, [letter_record(sample_job_listing)])
    (tmp_path / "labels.json").write_text(
        json.dumps({"real__01": label_entry()}), encoding="utf-8"
    )
    (tmp_path / "cases.jsonl").write_text("frozen\n", encoding="utf-8")

    assert imp.main(["--dataset", str(tmp_path)]) == 1
    assert (tmp_path / "cases.jsonl").read_text(encoding="utf-8") == "frozen\n"

    assert imp.main(["--dataset", str(tmp_path), "--force"]) == 0
    assert len(load_jsonl(tmp_path / "cases.jsonl", GroundingCase)) == 1


def test_main_writes_nothing_when_the_import_stops(
    tmp_path: Path, sample_job_listing: JobListing
) -> None:
    """Missing files or a bad label give exit code 1 and no cases.jsonl."""
    assert imp.main(["--dataset", str(tmp_path)]) == 1

    write_dataset(tmp_path, [letter_record(sample_job_listing)])
    assert imp.main(["--dataset", str(tmp_path)]) == 1

    (tmp_path / "labels.json").write_text(
        json.dumps({"real__01": label_entry(reviewed=False)}), encoding="utf-8"
    )
    assert imp.main(["--dataset", str(tmp_path)]) == 1
    assert not (tmp_path / "cases.jsonl").exists()
