"""
EMSCAD suite: the pipeline scam decision on the local Kaggle CSV.

The CSV is not committed (decision 3 of 2026-10-22). ``load_emscad`` maps
each row the same way as notebook cell 8. ``split_emscad`` is deterministic
and stratified by ``fraudulent``. The held-out part runs one time in Stage B.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ...models.job_listing import (
    ExperienceLevel,
    JobListing,
    JobRequirement,
    JobSource,
    JobType,
    SalaryRange,
)
from ...scoring.scam_detector import JobScamDetector, ScamFilter
from ..report import EvalReport
from ..run_metadata import BACKEND_DIR, build_run_metadata
from .scam import ExpectedLabel, evaluate_scam_listings

SUITE = "emscad"
DEFAULT_DATASET_DIR = BACKEND_DIR / "data" / "kaggle"
EMSCAD_CSV_NAME = "fake_job_postings.csv"
EMSCAD_SPLIT_SEED = 20261024
EMSCAD_HELD_OUT_FRACTION = 0.5

EXPERIENCE_MAP: Dict[str, ExperienceLevel] = {
    "Internship": ExperienceLevel.INTERNSHIP,
    "Entry level": ExperienceLevel.ENTRY,
    "Mid-Senior level": ExperienceLevel.MID,
    "Senior": ExperienceLevel.SENIOR,
    "Director": ExperienceLevel.LEAD,
    "Executive": ExperienceLevel.EXECUTIVE,
    "Not Applicable": ExperienceLevel.NOT_SPECIFIED,
}

JOB_TYPE_MAP: Dict[str, JobType] = {
    "Full-time": JobType.FULL_TIME,
    "Part-time": JobType.PART_TIME,
    "Contract": JobType.CONTRACT,
    "Temporary": JobType.TEMPORARY,
    "Internship": JobType.INTERNSHIP,
    "Other": JobType.FREELANCE,
}


@dataclass(frozen=True)
class EmscadRow:
    """One EMSCAD posting after the notebook mapping."""

    job: JobListing
    expected: ExpectedLabel
    fraudulent: int


def parse_salary_range(salary_str: str) -> Optional[SalaryRange]:
    """
    Parse a Kaggle ``salary_range`` string such as ``50000-80000``.

    Args:
        salary_str: Raw cell text.

    Returns:
        A ``SalaryRange``, or None when the cell is empty or not a pair.
    """
    if not salary_str:
        return None
    parts = salary_str.split("-")
    if len(parts) != 2:
        return None
    try:
        return SalaryRange(
            min_amount=float(parts[0].strip()),
            max_amount=float(parts[1].strip()),
            period="annual",
        )
    except ValueError:
        return None


def _cell(row: Dict[str, str], key: str) -> str:
    """
    Read a CSV cell as stripped text.

    Args:
        row: CSV row.
        key: Column name.

    Returns:
        The cell, or an empty string.
    """
    value = row.get(key)
    if value is None:
        return ""
    return str(value).strip()


def row_to_job_listing(row: Dict[str, str]) -> JobListing:
    """
    Map one EMSCAD row to ``JobListing`` (notebook cell 8).

    Args:
        row: CSV row.

    Returns:
        A listing. Description is the job text plus the company profile.
    """
    desc_parts: List[str] = []
    description = _cell(row, "description")
    profile = _cell(row, "company_profile")
    if description:
        desc_parts.append(description)
    if profile:
        desc_parts.append(profile)
    combined = "\n\n".join(desc_parts) if desc_parts else None

    requirements: List[JobRequirement] = []
    req_text = _cell(row, "requirements")
    if req_text:
        for line in req_text.split("\n"):
            line = line.strip()
            if line:
                requirements.append(JobRequirement(text=line))

    company = _cell(row, "company") or "Unknown"
    title = _cell(row, "title") or "Unknown"
    location = _cell(row, "location") or None
    return JobListing(
        title=title,
        company=company,
        location=location,
        description=combined,
        requirements=requirements,
        salary_range=parse_salary_range(_cell(row, "salary_range")),
        source=JobSource.MANUAL,
        job_id=_cell(row, "job_id"),
        is_remote=_cell(row, "telecommuting") in {"1", "true", "True"},
        experience_level=EXPERIENCE_MAP.get(
            _cell(row, "required_experience"), ExperienceLevel.NOT_SPECIFIED
        ),
        job_type=JOB_TYPE_MAP.get(_cell(row, "employment_type"), JobType.FULL_TIME),
        metadata={
            "has_company_logo": _cell(row, "has_company_logo") in {"1", "true", "True"},
            "has_questions": _cell(row, "has_questions") in {"1", "true", "True"},
            "industry": _cell(row, "industry") or None,
            "function": _cell(row, "function") or None,
            "benefits": _cell(row, "benefits") or None,
        },
    )


def load_emscad(csv_path: Path) -> List[EmscadRow]:
    """
    Load EMSCAD rows from a CSV path.

    Args:
        csv_path: Path of ``fake_job_postings.csv``.

    Returns:
        Mapped rows in file order.

    Raises:
        FileNotFoundError: When the CSV is missing. The message names the
            path and decision 3.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"{csv_path} not found. Download EMSCAD into this folder after "
            "checking the license (decision 3 of 2026-10-22)."
        )
    rows: List[EmscadRow] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            fraudulent = 1 if _cell(raw, "fraudulent") in {"1", "true", "True"} else 0
            rows.append(
                EmscadRow(
                    job=row_to_job_listing(raw),
                    expected="scam" if fraudulent else "legit",
                    fraudulent=fraudulent,
                )
            )
    return rows


def split_emscad(
    rows: Sequence[EmscadRow],
    seed: int = EMSCAD_SPLIT_SEED,
    held_out_fraction: float = EMSCAD_HELD_OUT_FRACTION,
) -> Tuple[List[EmscadRow], List[EmscadRow]]:
    """
    Split rows into tuning and held-out parts, stratified by ``fraudulent``.

    Args:
        rows: Mapped EMSCAD rows.
        seed: RNG seed. The same seed returns the same parts.
        held_out_fraction: Share of each label that goes to the held-out part.

    Returns:
        ``(tuning, heldout)``. The parts share no row.
    """
    rng = random.Random(seed)
    buckets: Dict[int, List[EmscadRow]] = {0: [], 1: []}
    for row in rows:
        buckets[row.fraudulent].append(row)
    tuning: List[EmscadRow] = []
    heldout: List[EmscadRow] = []
    for label in sorted(buckets):
        group = list(buckets[label])
        rng.shuffle(group)
        n_held = int(round(len(group) * held_out_fraction))
        if len(group) >= 2:
            n_held = min(max(n_held, 1), len(group) - 1)
        heldout.extend(group[:n_held])
        tuning.extend(group[n_held:])
    return tuning, heldout


def run_emscad_suite(
    dataset_dir: Path = DEFAULT_DATASET_DIR, part: str = "tuning"
) -> EvalReport:
    """
    Score the pipeline decision on one EMSCAD part.

    Args:
        dataset_dir: Folder that holds ``fake_job_postings.csv``.
        part: ``tuning`` or ``heldout``.

    Returns:
        Report with the same metrics as the scam suite, plus split metadata.

    Raises:
        FileNotFoundError: When the CSV is missing.
        ValueError: When ``part`` is not ``tuning`` or ``heldout``.
    """
    if part not in {"tuning", "heldout"}:
        raise ValueError(f"emscad part must be tuning or heldout: {part}")
    csv_path = Path(dataset_dir) / EMSCAD_CSV_NAME
    rows = load_emscad(csv_path)
    tuning, heldout = split_emscad(
        rows, seed=EMSCAD_SPLIT_SEED, held_out_fraction=EMSCAD_HELD_OUT_FRACTION
    )
    chosen = tuning if part == "tuning" else heldout
    items = [
        (row.job.job_id or f"row-{index}", row.job, row.expected, ())
        for index, row in enumerate(chosen)
    ]
    metrics, details = evaluate_scam_listings(
        items,
        detector=JobScamDetector(threshold=0.7),
        filter_hit_fn=ScamFilter.is_potential_scam,
    )
    details.update(
        {
            "part": part,
            "csv_rows": len(rows),
            "tuning_rows": len(tuning),
            "heldout_rows": len(heldout),
            "part_rows": len(chosen),
            "part_scam": sum(1 for row in chosen if row.expected == "scam"),
            "part_legit": sum(1 for row in chosen if row.expected == "legit"),
            "held_out_fraction": EMSCAD_HELD_OUT_FRACTION,
            "csv_name": EMSCAD_CSV_NAME,
        }
    )
    metadata = build_run_metadata(
        SUITE,
        [csv_path],
        len(chosen),
        seed=EMSCAD_SPLIT_SEED,
    )
    return EvalReport(
        suite=SUITE,
        metadata=metadata,
        metrics=metrics,
        details=details,
    )
