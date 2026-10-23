"""
Sentence-level ungrounded_claims labels and suite scoring (D6a).

Names and letters are new. They are not copied from the main set or the
holdout set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from src.evaluation.suites.grounding import GroundingCase
from src.generation.cover_letter_validator import CoverLetterIssue

JOB: Dict[str, Any] = {
    "title": "Relay Engineer",
    "company": "Cinder Quay",
    "job_id": "d6a-relay",
    "source": "manual",
    "location": "Pebble Reach",
    "description": "Keep a relay log attached to the vessel that produced it.",
}

PROFILE: Dict[str, Any] = {
    "name": "Pax Ellison",
    "contact": {"email": "pax.ellison@example.com", "location": "Pebble Reach"},
    "summary": "Relay engineer who writes Python services.",
    "skills": [
        {
            "name": "Python",
            "category": "programming_language",
            "years_of_experience": 3,
        }
    ],
    "experience": [
        {
            "company": "Keelwright Analog",
            "title": "Signal Engineer",
            "location": "Pebble Reach",
            "start_date": "2021-01-01T00:00:00",
            "end_date": "2024-01-01T00:00:00",
            "current": False,
            "description": "Built Python services for signal review.",
            "highlights": ["Built Python services for signal review."],
            "technologies": ["Python"],
        }
    ],
}

GREETING_LETTER = (
    "Dear hiring team, I invented a QuantumLoom compiler at Zorblax Foundry.\n\n"
    "I built Python services for signal review.\n\n"
    "Thank you.\n\n"
    "Sincerely,\n"
    "Pax Ellison"
)
GREETING_SENTENCE = (
    "Dear hiring team, I invented a QuantumLoom compiler at Zorblax Foundry."
)


def _write_dataset(directory: Path, cases: List[Dict[str, Any]]) -> Path:
    """
    Write a tiny grounding dataset with a new profile.

    Args:
        directory: Target directory.
        cases: Case dicts.

    Returns:
        The dataset directory.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "profiles.json").write_text(
        json.dumps({"pax": PROFILE}), encoding="utf-8"
    )
    lines = [json.dumps(case) for case in cases]
    (directory / "cases.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def _case(**overrides: Any) -> Dict[str, Any]:
    """
    Build one case dict with defaults.

    Args:
        **overrides: Fields that replace the defaults.

    Returns:
        A case dict for ``cases.jsonl``.
    """
    data: Dict[str, Any] = {
        "case_id": "d6a__default",
        "profile_id": "pax",
        "job": JOB,
        "letter": GREETING_LETTER,
        "expected_issues": ["ungrounded_claims"],
        "note": "D6a test case.",
        "ungrounded_sentences": [GREETING_SENTENCE],
    }
    data.update(overrides)
    return data


def test_ungrounded_sentence_must_equal_a_letter_sentence() -> None:
    """An item that is not a letter sentence raises with the case and item."""
    with pytest.raises(ValueError, match="d6a__bad_item") as err:
        GroundingCase.model_validate(
            _case(
                case_id="d6a__bad_item",
                ungrounded_sentences=["this line is not in the letter"],
            )
        )
    assert "this line is not in the letter" in str(err.value)


def test_ungrounded_claims_label_matches_nonempty_list() -> None:
    """A nonempty list requires ungrounded_claims in expected_issues."""
    with pytest.raises(ValueError, match="d6a__label_mismatch"):
        GroundingCase.model_validate(
            _case(
                case_id="d6a__label_mismatch",
                expected_issues=[],
                ungrounded_sentences=[GREETING_SENTENCE],
            )
        )


def test_none_sentence_list_skips_the_field_checks() -> None:
    """None means the case is not labeled at sentence level."""
    case = GroundingCase.model_validate(
        _case(
            case_id="d6a__none",
            expected_issues=[],
            ungrounded_sentences=None,
        )
    )
    assert case.ungrounded_sentences is None


def test_greeting_finding_maps_to_the_full_sentence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finding after a greeting clause maps to the joined letter sentence."""
    from src.evaluation.suites import grounding as suite

    finding = "I invented a QuantumLoom compiler at Zorblax Foundry"
    _patch_validate(monkeypatch, [finding])
    dataset = _write_dataset(
        tmp_path / "greet",
        [_case(case_id="d6a__greet")],
    )

    report = suite.run_grounding_suite(dataset)

    row = report.details["cases"][0]
    assert row["sentence_missed"] == []
    assert row["sentence_extra"] == []
    assert report.metrics["sentence.labeled_cases"] == 1.0
    assert report.metrics["sentence.precision"] == pytest.approx(1.0)
    assert report.metrics["sentence.recall"] == pytest.approx(1.0)
    assert report.metrics["sentence.f1"] == pytest.approx(1.0)


def test_unmapped_finding_is_a_false_positive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finding that maps to no letter sentence is a false positive."""
    from src.evaluation.suites import grounding as suite

    finding = "this finding is not a letter sentence"
    _patch_validate(monkeypatch, [finding])
    dataset = _write_dataset(
        tmp_path / "unmapped",
        [
            _case(
                case_id="d6a__unmapped",
                expected_issues=[],
                ungrounded_sentences=[],
            )
        ],
    )

    report = suite.run_grounding_suite(dataset)

    row = report.details["cases"][0]
    assert finding in row["sentence_extra"]
    assert report.metrics["sentence.precision"] == pytest.approx(0.0)
    assert report.metrics["sentence.false_positives"] == 1.0


def test_none_case_is_not_included_in_sentence_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A case with None is omitted from sentence precision and recall."""
    from src.evaluation.suites import grounding as suite

    _patch_validate(
        monkeypatch, ["I invented a QuantumLoom compiler at Zorblax Foundry"]
    )
    dataset = _write_dataset(
        tmp_path / "skip",
        [
            _case(
                case_id="d6a__skip",
                expected_issues=["ungrounded_claims"],
                ungrounded_sentences=None,
            )
        ],
    )

    report = suite.run_grounding_suite(dataset)

    assert report.metrics["sentence.labeled_cases"] == 0.0
    assert report.metrics["sentence.precision"] is None
    assert report.metrics["sentence.recall"] is None
    assert report.metrics["sentence.f1"] is None
    row = report.details["cases"][0]
    assert "sentence_missed" not in row
    assert "sentence_extra" not in row


def test_sentence_scores_on_a_known_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two labeled cases produce known sentence precision, recall, and F1."""
    from src.evaluation.suites import grounding as suite

    gold = "I invented a QuantumLoom compiler at Zorblax Foundry."
    other = "I built Python services for signal review."
    letter = f"{gold}\n\n{other}\n\nThank you.\n\nSincerely,\nPax Ellison"

    calls = iter(
        [
            ["I invented a QuantumLoom compiler at Zorblax Foundry"],
            ["I built Python services for signal review"],
        ]
    )

    def _fake_validate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
        result = MagicMock()
        result.issues = [CoverLetterIssue.UNGROUNDED_CLAIMS]
        result.details = {"ungrounded_sentences": list(next(calls))}
        return result

    monkeypatch.setattr(
        "src.evaluation.suites.grounding.CoverLetterValidator.validate",
        _fake_validate,
    )
    dataset = _write_dataset(
        tmp_path / "known",
        [
            _case(
                case_id="d6a__tp",
                letter=letter,
                ungrounded_sentences=[gold],
            ),
            _case(
                case_id="d6a__fn_fp",
                letter=letter,
                expected_issues=["ungrounded_claims"],
                ungrounded_sentences=[gold],
            ),
        ],
    )

    report = suite.run_grounding_suite(dataset)

    # Case 1: gold gold, predicted gold -> TP.
    # Case 2: gold gold, predicted other -> FN + FP.
    assert report.metrics["sentence.labeled_cases"] == 2.0
    assert report.metrics["sentence.precision"] == pytest.approx(0.5)
    assert report.metrics["sentence.recall"] == pytest.approx(0.5)
    assert report.metrics["sentence.f1"] == pytest.approx(0.5)
    assert report.details["cases"][0]["sentence_missed"] == []
    assert report.details["cases"][0]["sentence_extra"] == []
    assert report.details["cases"][1]["sentence_missed"] == [gold]
    assert report.details["cases"][1]["sentence_extra"] == [other]


def test_containment_mapping_mutation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exact match instead of containment fails the greeting mapping test."""
    from src.evaluation.suites import grounding as suite

    original = suite.map_finding_to_letter_sentence

    def _exact(finding: str, sentences: List[str]) -> Any:
        needle = suite._normalize_sentence_key(finding)
        for sentence in sentences:
            if needle == suite._normalize_sentence_key(sentence):
                return sentence
        return None

    monkeypatch.setattr(suite, "map_finding_to_letter_sentence", _exact)
    finding = "I invented a QuantumLoom compiler at Zorblax Foundry"
    _patch_validate(monkeypatch, [finding])
    dataset = _write_dataset(
        tmp_path / "mutate",
        [_case(case_id="d6a__mutate")],
    )

    report = suite.run_grounding_suite(dataset)
    row = report.details["cases"][0]
    assert finding in row["sentence_extra"]
    assert GREETING_SENTENCE in row["sentence_missed"]
    monkeypatch.setattr(suite, "map_finding_to_letter_sentence", original)


def _patch_validate(monkeypatch: pytest.MonkeyPatch, findings: List[str]) -> None:
    """
    Replace the validator with a result that returns the given findings.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        findings: Strings to put in ``details['ungrounded_sentences']``.

    Returns:
        None.
    """

    def _fake_validate(self: Any, *args: Any, **kwargs: Any) -> MagicMock:
        result = MagicMock()
        result.issues = [CoverLetterIssue.UNGROUNDED_CLAIMS] if findings else []
        result.details = {"ungrounded_sentences": list(findings)}
        return result

    monkeypatch.setattr(
        "src.evaluation.suites.grounding.CoverLetterValidator.validate",
        _fake_validate,
    )
