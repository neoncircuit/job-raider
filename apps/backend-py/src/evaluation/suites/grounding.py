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
from typing import Any, Dict, List, Optional, Sequence, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...generation.cover_letter_grounding import split_letter_sentences
from ...generation.cover_letter_validator import CoverLetterIssue, CoverLetterValidator
from ...generation.cover_letter_writer import GeneratedCoverLetter
from ...generation.selector import SelectionOutput
from ...models.job_listing import JobListing
from ...models.user_profile import UserProfile
from ..datasets import load_jsonl
from ..metrics import (
    LabelScores,
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
    ungrounded_sentences: Optional[List[str]] = None

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

    @model_validator(mode="after")
    def _check_ungrounded_sentences(self) -> "GroundingCase":
        """
        Check sentence-level ungrounded labels when they are present.

        Args:
            self: Validated case.

        Returns:
            The same case.

        Raises:
            ValueError: When an item is not a letter sentence, or when
                ``ungrounded_claims`` does not match a nonempty list.
        """
        if self.ungrounded_sentences is None:
            return self
        sentences = split_letter_sentences(self.letter)
        for item in self.ungrounded_sentences:
            joined = " ".join(item.split())
            if joined not in sentences:
                raise ValueError(
                    f"{self.case_id}: ungrounded sentence is not a letter "
                    f"sentence: {item!r}"
                )
        has_label = CoverLetterIssue.UNGROUNDED_CLAIMS.value in self.expected_issues
        if bool(self.ungrounded_sentences) != has_label:
            raise ValueError(
                f"{self.case_id}: ungrounded_claims must be in expected_issues "
                "exactly when ungrounded_sentences is not empty"
            )
        return self


def _normalize_sentence_key(text: str) -> str:
    """
    Join whitespace, lowercase, and drop end punctuation.

    Args:
        text: Finding or letter sentence.

    Returns:
        Normalized key used for containment mapping.
    """
    return " ".join(text.split()).lower().rstrip(".!?")


def map_finding_to_letter_sentence(
    finding: str, sentences: Sequence[str]
) -> Optional[str]:
    """
    Map a validator finding to the letter sentence that contains it.

    Containment is required because the validator may drop a leading
    greeting clause before it reports a sentence.

    Args:
        finding: Validator finding string.
        sentences: Letter sentences from ``split_letter_sentences``.

    Returns:
        The first letter sentence that contains the finding, or None.
    """
    needle = _normalize_sentence_key(finding)
    if not needle:
        return None
    for sentence in sentences:
        if needle in _normalize_sentence_key(sentence):
            return sentence
    return None


def _sentence_scores(
    true_positives: int, false_positives: int, false_negatives: int
) -> LabelScores:
    """
    Build sentence-level scores for ``ungrounded_claims``.

    Args:
        true_positives: Sentences found that were labeled.
        false_positives: Extra sentences, including unmapped findings.
        false_negatives: Labeled sentences the validator missed.

    Returns:
        Precision, recall, and F1 over sentences.
    """
    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives)
        else None
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives)
        else None
    )
    if precision is None or recall is None:
        f1: Optional[float] = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return LabelScores(
        label="ungrounded_claims.sentence",
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        support=true_positives + false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
    )


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


def _validate_case(
    validator: CoverLetterValidator, case: GroundingCase, profile: UserProfile
) -> Any:
    """
    Run the validator on one case.

    Args:
        validator: Deterministic validator (no LLM).
        case: Labeled case.
        profile: Profile that the case refers to.

    Returns:
        The validator result, including ``details``.
    """
    letter = GeneratedCoverLetter(
        content=case.letter,
        highlighted_experiences=[],
        word_count=len(case.letter.split()),
        model_used="eval-fixture",
    )
    return validator.validate(
        letter, JobListing.model_validate(case.job), profile, _selection(case)
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
    result = _validate_case(validator, case, profile)
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
    sentence_tp = 0
    sentence_fp = 0
    sentence_fn = 0
    labeled_cases = 0
    unmapped_findings: List[Dict[str, str]] = []
    for case in cases:
        want = set(case.expected_issues)
        result = _validate_case(validator, case, profiles[case.profile_id])
        got = {issue.value for issue in result.issues} & set(GROUNDING_LABELS)
        expected.append(want)
        predicted.append(got)
        row: Dict[str, Any] = {
            "case_id": case.case_id,
            "expected": sorted(want),
            "predicted": sorted(got),
            "missed": sorted(want - got),
            "extra": sorted(got - want),
        }
        if case.ungrounded_sentences is not None:
            labeled_cases += 1
            letter_sentences = split_letter_sentences(case.letter)
            gold = {" ".join(item.split()) for item in case.ungrounded_sentences}
            findings = result.details.get("ungrounded_sentences") or []
            pred: Set[str] = set()
            unmapped: List[str] = []
            for finding in findings:
                mapped = map_finding_to_letter_sentence(str(finding), letter_sentences)
                if mapped is None:
                    unmapped.append(str(finding))
                    unmapped_findings.append(
                        {"case_id": case.case_id, "finding": str(finding)}
                    )
                else:
                    pred.add(" ".join(mapped.split()))
            missed = sorted(gold - pred)
            extra_mapped = sorted(pred - gold)
            sentence_tp += len(gold & pred)
            sentence_fn += len(gold - pred)
            sentence_fp += len(pred - gold) + len(unmapped)
            row["sentence_missed"] = missed
            row["sentence_extra"] = unmapped + extra_mapped
        case_rows.append(row)

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
    if labeled_cases:
        sentence = _sentence_scores(sentence_tp, sentence_fp, sentence_fn)
        metrics["sentence.precision"] = sentence.precision
        metrics["sentence.recall"] = sentence.recall
        metrics["sentence.f1"] = sentence.f1
        metrics["sentence.labeled_cases"] = float(labeled_cases)
        metrics["sentence.true_positives"] = float(sentence.true_positives)
        metrics["sentence.false_positives"] = float(sentence.false_positives)
        metrics["sentence.false_negatives"] = float(sentence.false_negatives)
    else:
        metrics["sentence.precision"] = None
        metrics["sentence.recall"] = None
        metrics["sentence.f1"] = None
        metrics["sentence.labeled_cases"] = 0.0
        metrics["sentence.true_positives"] = None
        metrics["sentence.false_positives"] = None
        metrics["sentence.false_negatives"] = None

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
            "unmapped_ungrounded_findings": unmapped_findings,
        },
    )
