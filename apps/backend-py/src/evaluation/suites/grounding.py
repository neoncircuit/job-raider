"""
Grounding suite: the deterministic cover-letter validator on labeled letters.

A dataset folder has ``profiles.json`` (profile ID to ``UserProfile``) and
``cases.jsonl`` (one letter per line with its expected grounding issues).
The validator runs without an LLM, as in the cover-letter service. Only the
grounding labels are scored; structure and tone checks are ignored.

Step 3.1 adds the runner. Step 3.2 adds the labeled set and its guide in
``tests/fixtures/eval/grounding/``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...generation.cover_letter_validator import CoverLetterIssue, CoverLetterValidator
from ...generation.cover_letter_writer import GeneratedCoverLetter
from ...generation.selector import SelectionOutput
from ...models.job_listing import JobListing
from ...models.user_profile import UserProfile
from ..datasets import load_jsonl
from ..metrics import (
    clean_case_false_positive_rate,
    micro_scores,
    multilabel_scores,
)
from ..report import EvalReport
from ..run_metadata import BACKEND_DIR, build_run_metadata

SUITE = "grounding"
DEFAULT_DATASET_DIR = BACKEND_DIR / "tests" / "fixtures" / "eval" / "grounding"

GROUNDING_LABELS: tuple[str, ...] = tuple(
    issue.value
    for issue in (
        CoverLetterIssue.FABRICATED_TECHNOLOGY,
        CoverLetterIssue.INFLATED_DURATION,
        CoverLetterIssue.INCONSISTENT_METRIC,
        CoverLetterIssue.FABRICATED_EXPERIENCE,
        CoverLetterIssue.ANALOGICAL_CLAIM,
        CoverLetterIssue.SCOPE_INFLATION,
        CoverLetterIssue.TECHNIQUE_MISMATCH,
        CoverLetterIssue.UNGROUNDED_CLAIMS,
    )
)


class GroundingCase(BaseModel):
    """One labeled cover letter."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    profile_id: str
    job: Dict[str, Any]
    selection: Optional[Dict[str, Any]] = None
    letter: str
    expected_issues: List[str] = Field(default_factory=list)
    note: str = ""

    @field_validator("expected_issues")
    @classmethod
    def _only_grounding_labels(cls, value: List[str]) -> List[str]:
        """
        Reject labels that the suite does not score.

        Args:
            value: Expected issue names.

        Returns:
            The same list.

        Raises:
            ValueError: When a name is not a grounding label.
        """
        unknown = sorted(set(value) - set(GROUNDING_LABELS))
        if unknown:
            raise ValueError(f"not grounding labels: {unknown}")
        return value


def _load_profiles(path: Path) -> Dict[str, UserProfile]:
    """
    Load the profiles that the cases refer to.

    Args:
        path: ``profiles.json`` (an object of profile ID to profile).

    Returns:
        Validated profiles by ID.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {pid: UserProfile.model_validate(data) for pid, data in raw.items()}


def _selection(case: GroundingCase) -> SelectionOutput:
    """
    The selection used to generate the letter, or an empty one.

    Args:
        case: Labeled case.

    Returns:
        Selection output for the validator.
    """
    if case.selection:
        return SelectionOutput(**case.selection)
    return SelectionOutput(
        selected_projects=[],
        keywords_to_emphasize=[],
        key_achievements=[],
        summary_suggestion="",
        raw_response="",
    )


def predict_issues(
    validator: CoverLetterValidator, case: GroundingCase, profile: UserProfile
) -> Set[str]:
    """
    Run the validator on one case and keep the grounding labels.

    Args:
        validator: Deterministic validator (no LLM).
        case: Labeled case.
        profile: Profile that the case refers to.

    Returns:
        Predicted grounding labels.
    """
    letter = GeneratedCoverLetter(
        content=case.letter,
        highlighted_experiences=[],
        word_count=len(case.letter.split()),
        model_used="eval-fixture",
    )
    result = validator.validate(
        letter, JobListing.model_validate(case.job), profile, _selection(case)
    )
    return {issue.value for issue in result.issues} & set(GROUNDING_LABELS)


def run_grounding_suite(dataset_dir: Path = DEFAULT_DATASET_DIR) -> EvalReport:
    """
    Score the validator on a labeled dataset.

    Args:
        dataset_dir: Folder with ``profiles.json`` and ``cases.jsonl``.

    Returns:
        Report with per-label and micro precision, recall, and F1, the
        false-positive rate on clean letters, and per-case results.

    Raises:
        FileNotFoundError: When a dataset file is missing.
        ValueError: When a case is invalid or names an unknown profile.
    """
    cases_path = dataset_dir / "cases.jsonl"
    profiles_path = dataset_dir / "profiles.json"
    for path in (cases_path, profiles_path):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. The labeled grounding set is added in Step 3.2; "
                "pass --dataset to use another folder."
            )

    cases = load_jsonl(cases_path, GroundingCase)
    profiles = _load_profiles(profiles_path)
    for case in cases:
        if case.profile_id not in profiles:
            raise ValueError(
                f"case {case.case_id}: unknown profile_id {case.profile_id!r}"
            )

    metadata = build_run_metadata(SUITE, [profiles_path, cases_path], len(cases))
    validator = CoverLetterValidator(llm_router=None, strict_mode=False)

    expected: List[Set[str]] = []
    predicted: List[Set[str]] = []
    case_rows: List[Dict[str, Any]] = []
    for case in cases:
        want = set(case.expected_issues)
        got = predict_issues(validator, case, profiles[case.profile_id])
        expected.append(want)
        predicted.append(got)
        case_rows.append(
            {
                "case_id": case.case_id,
                "expected": sorted(want),
                "predicted": sorted(got),
                "missed": sorted(want - got),
                "extra": sorted(got - want),
            }
        )

    per_label = multilabel_scores(expected, predicted, GROUNDING_LABELS)
    micro = micro_scores(per_label)
    metrics: Dict[str, Optional[float]] = {
        "case_count": float(len(cases)),
        "clean_false_positive_rate": clean_case_false_positive_rate(
            expected, predicted
        ),
        "micro.precision": micro.precision,
        "micro.recall": micro.recall,
        "micro.f1": micro.f1,
    }
    for label, scores in per_label.items():
        metrics[f"precision.{label}"] = scores.precision
        metrics[f"recall.{label}"] = scores.recall
        metrics[f"f1.{label}"] = scores.f1

    return EvalReport(
        suite=SUITE,
        metadata=metadata,
        metrics=metrics,
        details={
            "labels": list(GROUNDING_LABELS),
            "per_label": {
                label: {
                    "true_positives": s.true_positives,
                    "false_positives": s.false_positives,
                    "false_negatives": s.false_negatives,
                    "support": s.support,
                }
                for label, s in per_label.items()
            },
            "cases": case_rows,
        },
    )
