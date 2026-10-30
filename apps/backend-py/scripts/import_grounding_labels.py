#!/usr/bin/env python3
"""
Job Raider - Import the labels of the real-letter grounding set
(Step 3.2 real letters, MH-C)

Reads ``letters.jsonl`` (written by MH-A) and ``labels.json`` (exported by
the MH-B page) and writes ``cases.jsonl`` in the dataset folder, one
``GroundingCase`` for each letter. The import stops when a letter has no
labels, a label entry names an unknown case, a letter is not marked as
reviewed, a label is unknown, or an ungrounded sentence is not a sentence of
its letter. ``ungrounded_claims`` is set from the sentence list, as the
labeling guide says. An existing ``cases.jsonl`` is not replaced without
``--force``, because the labels are frozen once the eval has run.

Usage (from apps/backend-py; the browser saves labels.json in Downloads):

    python scripts/import_grounding_labels.py --labels /path/to/labels.json

Author: Job Raider
Date: 2026-10-30
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Allow ``from src...`` and ``from scripts...`` when run as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from scripts.build_grounding_label_page import read_letters  # noqa: E402
from src.evaluation.suites.grounding import (  # noqa: E402
    GROUNDING_LABELS,
    GroundingCase,
)

DEFAULT_DATASET = _BACKEND_ROOT / "data" / "eval" / "grounding_real"
SENTENCE_LABEL = "ungrounded_claims"


def build_cases(
    letters: Sequence[Dict[str, Any]], labels: Dict[str, Dict[str, Any]]
) -> List[GroundingCase]:
    """
    Join the letters and their labels into grounding cases.

    Args:
        letters: The letter records of MH-A.
        labels: The exported label entries by case ID.

    Returns:
        One case for each letter, in letter order. The labels follow the
        order of ``GROUNDING_LABELS``. ``ungrounded_claims`` is present
        exactly when the sentence list is not empty.

    Raises:
        ValueError: When a letter has no labels, an entry names an unknown
            case, a letter is not reviewed, a label is unknown, or a sentence
            is not a sentence of its letter.
    """
    letter_ids = [record["case_id"] for record in letters]
    unknown_cases = sorted(set(labels) - set(letter_ids))
    if unknown_cases:
        raise ValueError(f"labels for unknown cases: {unknown_cases}")
    missing = [case_id for case_id in letter_ids if case_id not in labels]
    if missing:
        raise ValueError(f"letters without labels: {missing}")
    unreviewed = [
        case_id for case_id in letter_ids if labels[case_id].get("reviewed") is not True
    ]
    if unreviewed:
        raise ValueError(f"letters not marked as reviewed: {unreviewed}")

    cases: List[GroundingCase] = []
    for record in letters:
        case_id = record["case_id"]
        entry = labels[case_id]
        issues = set(entry.get("expected_issues", []))
        unknown_labels = sorted(issues - set(GROUNDING_LABELS))
        if unknown_labels:
            raise ValueError(f"{case_id}: unknown labels {unknown_labels}")
        sentences = [
            " ".join(text.split()) for text in entry.get("ungrounded_sentences", [])
        ]
        if sentences:
            issues.add(SENTENCE_LABEL)
        else:
            issues.discard(SENTENCE_LABEL)
        cases.append(
            GroundingCase(
                case_id=case_id,
                profile_id=record["profile_id"],
                job=record["job"],
                selection=record.get("selection"),
                letter=record["letter"],
                expected_issues=[
                    label for label in GROUNDING_LABELS if label in issues
                ],
                note=str(entry.get("note", "")),
                ungrounded_sentences=sentences,
            )
        )
    return cases


def write_cases(
    path: Path, cases: Sequence[GroundingCase], force: bool = False
) -> None:
    """
    Write ``cases.jsonl``, one case for each line.

    Args:
        path: The ``cases.jsonl`` file.
        cases: The grounding cases.
        force: Replace an existing file.

    Raises:
        FileExistsError: When the file exists and ``force`` is false.
    """
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; the labels are frozen")
    lines = [
        json.dumps(case.model_dump(mode="json"), ensure_ascii=False) + "\n"
        for case in cases
    ]
    path.write_text("".join(lines), encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Import ``labels.json`` into ``cases.jsonl``.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        0 when ``cases.jsonl`` is written, 1 when the import stops.
    """
    parser = argparse.ArgumentParser(
        description="Write cases.jsonl from letters.jsonl and the exported labels."
    )
    parser.add_argument(
        "--dataset", type=Path, default=DEFAULT_DATASET, help="Dataset folder"
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=None,
        help="Exported labels.json (default: labels.json in the dataset folder)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Replace an existing cases.jsonl"
    )
    args = parser.parse_args(argv)

    letters_path = args.dataset / "letters.jsonl"
    labels_path = args.labels or args.dataset / "labels.json"
    cases_path = args.dataset / "cases.jsonl"
    for path in (letters_path, labels_path):
        if not path.exists():
            print(f"{path} is missing")
            return 1
    if cases_path.exists() and not args.force:
        print(
            f"{cases_path} exists; the labels are frozen. "
            "Use --force only before the eval runs."
        )
        return 1

    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    try:
        cases = build_cases(read_letters(letters_path), labels)
    except ValueError as exc:
        print(f"Import stopped: {exc}")
        return 1

    kept_labels = args.dataset / "labels.json"
    if labels_path.resolve() != kept_labels.resolve():
        shutil.copyfile(labels_path, kept_labels)
    write_cases(cases_path, cases, force=args.force)
    labeled = sum(1 for case in cases if case.expected_issues)
    sentences = sum(len(case.ungrounded_sentences or []) for case in cases)
    print(
        f"Wrote {len(cases)} cases to {cases_path}: "
        f"{labeled} with labels, {sentences} ungrounded sentences"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
