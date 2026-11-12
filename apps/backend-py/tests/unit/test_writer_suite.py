"""Tests for the writer eval suite (Step 3.8, MH-1)."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import pytest

from src.evaluation.suites.writer import (
    CHECKS,
    DEFAULT_DATASET_DIR,
    FALLBACK_MODEL,
    MAIN_CHECK,
    WRITER_TEMPERATURE,
    load_pairs,
    percentile,
    run_writer_suite,
)
from src.generation.cover_letter_writer import GeneratedCoverLetter

MODEL = "qwen2.5:7b"


def small_dataset(tmp_path: Path, count: int = 3) -> Path:
    """
    A copy of the grounding profiles with the first cases of the set.

    Args:
        tmp_path: The test folder.
        count: Cases to keep.

    Returns:
        The dataset folder.
    """
    shutil.copy(DEFAULT_DATASET_DIR / "profiles.json", tmp_path / "profiles.json")
    lines = (DEFAULT_DATASET_DIR / "cases.jsonl").read_text(encoding="utf-8")
    kept = [line for line in lines.splitlines() if line.strip()][:count]
    (tmp_path / "cases.jsonl").write_text("\n".join(kept) + "\n", encoding="utf-8")
    return tmp_path


def job_ids(dataset_dir: Path) -> List[str]:
    """
    The job IDs of a dataset, in the order of the suite (by case ID).

    Args:
        dataset_dir: The dataset folder.

    Returns:
        One job ID for each pair.
    """
    return [pair.job.job_id for pair in load_pairs(dataset_dir)]


def writer_for(models: Optional[Dict[str, str]] = None) -> Callable[..., Any]:
    """
    A fake writer that returns a short letter.

    Args:
        models: Job ID to the ``model_used`` of its letters (default: MODEL).

    Returns:
        The write function.
    """

    def write(job: Any, profile: Any, selection: Any) -> GeneratedCoverLetter:
        """
        Return a fixed letter for the job.

        Args:
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            The letter.
        """
        used = (models or {}).get(job.job_id, MODEL)
        return GeneratedCoverLetter(
            content="Dear team, I built this.",
            highlighted_experiences=[],
            word_count=120,
            model_used=used,
        )

    return write


class FakeValidator:
    """Gives the issues of a map for each job and sample, in call order."""

    def __init__(self, issues_by_job: Dict[str, List[List[str]]]) -> None:
        """
        Keep the issues.

        Args:
            issues_by_job: Job ID to the issues of sample 0, sample 1, and so on.
        """
        self.issues_by_job = issues_by_job
        self.seen: Dict[str, int] = {}

    def validate(self, letter: Any, job: Any, profile: Any, selection: Any) -> Any:
        """
        Return the next issues for the job.

        Args:
            letter: The letter.
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            A result with ``issues``, ``is_valid``, ``score``, and ``details``.
        """
        sample = self.seen.get(job.job_id, 0)
        self.seen[job.job_id] = sample + 1
        per_sample = self.issues_by_job.get(job.job_id, [])
        issues = per_sample[sample] if sample < len(per_sample) else []
        return SimpleNamespace(
            issues=[SimpleNamespace(value=issue) for issue in issues],
            is_valid=not issues,
            score=100 - 10 * len(issues),
            details={"ungrounded_sentences": ["x"] * issues.count(MAIN_CHECK)},
        )


def test_load_pairs_gives_one_pair_for_each_grounding_case() -> None:
    """Each grounding case is one pair, ordered by case ID, with a fixed selection."""
    pairs = load_pairs()

    assert len(pairs) == 65
    assert [p.case_id for p in pairs] == sorted(p.case_id for p in pairs)
    assert {p.profile_id for p in pairs} == {"ml", "backend", "grad"}
    for pair in pairs:
        names = [project.name for project in pair.profile.projects[:3]]
        assert [s["name"] for s in pair.selection.selected_projects] == names


def test_load_pairs_rejects_an_unknown_profile(tmp_path: Path) -> None:
    """A case with a profile that is not in profiles.json stops the run."""
    dataset = small_dataset(tmp_path, count=1)
    case = json.loads((dataset / "cases.jsonl").read_text(encoding="utf-8"))
    case["profile_id"] = "nobody"
    (dataset / "cases.jsonl").write_text(json.dumps(case) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unknown profile_id"):
        load_pairs(dataset)


def test_each_pair_gets_each_sample(tmp_path: Path) -> None:
    """Each pair is written once for each sample."""
    dataset = small_dataset(tmp_path)
    calls: List[str] = []
    inner = writer_for()

    def write(job: Any, profile: Any, selection: Any) -> GeneratedCoverLetter:
        """Record the job, then write."""
        calls.append(job.job_id)
        return inner(job, profile, selection)

    report = run_writer_suite(
        dataset, model=MODEL, write=write, samples=2, validator=FakeValidator({})
    )

    assert len(calls) == 6
    rows = report.details["rows"]
    assert [(r["case_id"], r["sample"]) for r in rows] == [
        (pair.case_id, sample) for pair in load_pairs(dataset) for sample in range(2)
    ]
    assert report.metrics["letters"] == 6
    assert report.metrics["written"] == 6


def test_rates_count_the_flagged_letters(tmp_path: Path) -> None:
    """Each check's rate is the share of written letters that it flags."""
    dataset = small_dataset(tmp_path)
    first, second, _ = job_ids(dataset)
    validator = FakeValidator(
        {
            first: [[MAIN_CHECK], []],
            second: [
                [MAIN_CHECK, "fabricated_technology"],
                [MAIN_CHECK, "fabricated_technology"],
            ],
        }
    )

    report = run_writer_suite(
        dataset, model=MODEL, write=writer_for(), samples=2, validator=validator
    )

    assert report.metrics["ungrounded_claims_rate"] == 0.5
    assert report.metrics["fabricated_technology_rate"] == 0.333
    assert report.metrics["fabricated_experience_rate"] == 0.0
    assert report.metrics["scope_inflation_rate"] == 0.0
    assert report.metrics["valid_rate"] == 0.5
    assert report.metrics["mean_score"] == round(
        (90 + 100 + 80 + 80 + 100 + 100) / 6, 2
    )


def test_fallback_and_other_model_letters_are_counted_not_scored(
    tmp_path: Path,
) -> None:
    """Template letters and letters from another model do not enter the rates."""
    dataset = small_dataset(tmp_path)
    first, second, third = job_ids(dataset)
    write = writer_for({first: FALLBACK_MODEL, second: "qwen3.5:4b"})
    validator = FakeValidator({third: [[MAIN_CHECK], []]})

    report = run_writer_suite(
        dataset, model=MODEL, write=write, samples=2, validator=validator
    )

    assert report.metrics["fallback"] == 2
    assert report.metrics["other_model"] == 2
    assert report.metrics["written"] == 2
    assert report.metrics["ungrounded_claims_rate"] == 0.5
    assert set(validator.seen) == {third}


def test_writer_errors_are_counted(tmp_path: Path) -> None:
    """A writer that raises gives an error row, and the run goes on."""
    dataset = small_dataset(tmp_path)
    first = job_ids(dataset)[0]
    inner = writer_for()

    def write(job: Any, profile: Any, selection: Any) -> GeneratedCoverLetter:
        """Raise for the first job, else write."""
        if job.job_id == first:
            raise RuntimeError("model not loaded")
        return inner(job, profile, selection)

    report = run_writer_suite(
        dataset, model=MODEL, write=write, samples=2, validator=FakeValidator({})
    )

    assert report.metrics["error"] == 2
    assert report.metrics["written"] == 4
    errors = [r for r in report.details["rows"] if r["outcome"] == "error"]
    assert {r["error"] for r in errors} == {"RuntimeError"}


def test_issues_outside_the_checks_do_not_change_the_rates(tmp_path: Path) -> None:
    """Structure issues stay in the rows but are not grounding rates."""
    dataset = small_dataset(tmp_path, count=1)
    first = job_ids(dataset)[0]
    validator = FakeValidator({first: [["too_long"]]})

    report = run_writer_suite(
        dataset, model=MODEL, write=writer_for(), samples=1, validator=validator
    )

    assert all(report.metrics[f"{check}_rate"] == 0.0 for check in CHECKS)
    assert report.details["rows"][0]["issues"] == ["too_long"]
    assert report.metrics["valid_rate"] == 0.0


def test_pair_counts_for_the_paired_comparison(tmp_path: Path) -> None:
    """For each pair, the report counts written and flagged letters."""
    dataset = small_dataset(tmp_path)
    first, second, _ = job_ids(dataset)
    pairs = load_pairs(dataset)
    write = writer_for({second: FALLBACK_MODEL})
    validator = FakeValidator({first: [[MAIN_CHECK], [MAIN_CHECK, "scope_inflation"]]})

    report = run_writer_suite(
        dataset, model=MODEL, write=write, samples=2, validator=validator
    )

    counts = report.details["pairs"]
    assert counts[pairs[0].case_id]["written"] == 2
    assert counts[pairs[0].case_id]["flagged"][MAIN_CHECK] == 2
    assert counts[pairs[0].case_id]["flagged"]["scope_inflation"] == 1
    assert counts[pairs[1].case_id]["written"] == 0
    assert counts[pairs[1].case_id]["profile_id"] == pairs[1].profile_id


def test_profile_rates_give_the_main_check_for_each_profile(tmp_path: Path) -> None:
    """The report gives the main-check share of written letters for each profile."""
    dataset = small_dataset(tmp_path, count=65)
    pairs = load_pairs(dataset)
    flagged = [p.job.job_id for p in pairs if p.profile_id == "grad"]
    validator = FakeValidator({job_id: [[MAIN_CHECK]] for job_id in flagged})
    write = writer_for({flagged[0]: FALLBACK_MODEL})

    report = run_writer_suite(
        dataset, model=MODEL, write=write, samples=1, validator=validator
    )

    assert report.details["profiles"] == {"backend": 0.0, "grad": 1.0, "ml": 0.0}
    assert report.metrics["ungrounded_claims_rate"] == round(14 / 64, 3)


def test_latency_uses_the_clock(tmp_path: Path) -> None:
    """The latency of each letter comes from the clock."""
    dataset = small_dataset(tmp_path, count=2)
    ticks = iter([0.0, 2.0, 10.0, 11.0])

    report = run_writer_suite(
        dataset,
        model=MODEL,
        write=writer_for(),
        samples=1,
        validator=FakeValidator({}),
        clock=lambda: next(ticks),
    )

    assert [r["latency_ms"] for r in report.details["rows"]] == [2000.0, 1000.0]
    assert report.metrics["latency_p50_ms"] == 1000.0
    assert report.metrics["latency_p95_ms"] == 2000.0
    assert report.metrics["words_p50"] == 120.0


@pytest.mark.parametrize(
    ("values", "share", "expected"),
    [
        ([1.0, 2.0, 3.0, 4.0], 0.5, 2.0),
        ([1.0, 2.0, 3.0, 4.0], 0.95, 4.0),
        ([4.0, 1.0, 3.0], 0.5, 3.0),
        ([5.0], 0.95, 5.0),
        ([], 0.5, None),
    ],
)
def test_percentile_is_nearest_rank(
    values: List[float], share: float, expected: Optional[float]
) -> None:
    """The percentile is the nearest-rank value."""
    assert percentile(values, share) == expected


def test_metadata_names_the_model_and_temperature(tmp_path: Path) -> None:
    """The run metadata gives the suite, the model, the temperature, and the pairs."""
    dataset = small_dataset(tmp_path)

    report = run_writer_suite(
        dataset, model=MODEL, write=writer_for(), samples=1, validator=FakeValidator({})
    )

    assert report.suite == "writer"
    assert report.metadata.model == MODEL
    assert report.metadata.temperature == WRITER_TEMPERATURE == 0.8
    assert report.metadata.case_count == 3
    assert report.details["samples"] == 1
    assert report.details["main_check"] == MAIN_CHECK


def test_samples_below_one_are_refused(tmp_path: Path) -> None:
    """A run needs at least one sample."""
    with pytest.raises(ValueError, match="samples"):
        run_writer_suite(
            small_dataset(tmp_path), model=MODEL, write=writer_for(), samples=0
        )


def test_default_validator_has_no_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a validator, the suite makes the deterministic one."""
    made: List[Dict[str, Any]] = []

    def make(**kwargs: Any) -> FakeValidator:
        """Record the arguments and return a fake."""
        made.append(kwargs)
        return FakeValidator({})

    monkeypatch.setattr("src.evaluation.suites.writer.CoverLetterValidator", make)

    run_writer_suite(
        small_dataset(tmp_path, count=1), model=MODEL, write=writer_for(), samples=1
    )

    assert made == [{"llm_router": None, "strict_mode": False}]


def text_writer(
    texts: Dict[str, str], models: Optional[Dict[str, str]] = None
) -> Callable[..., Any]:
    """
    A fake writer that returns a given text for each job.

    Args:
        texts: Job ID to the letter text (default: a plain sentence).
        models: Job ID to the ``model_used`` of its letters (default: MODEL).

    Returns:
        The write function.
    """

    def write(job: Any, profile: Any, selection: Any) -> GeneratedCoverLetter:
        """
        Return the text of the job as a letter.

        Args:
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            The letter.
        """
        return GeneratedCoverLetter(
            content=texts.get(job.job_id, "Dear team, I built this."),
            highlighted_experiences=[],
            word_count=120,
            model_used=(models or {}).get(job.job_id, MODEL),
        )

    return write


def test_generic_phrasing_metrics_and_rows(tmp_path: Path) -> None:
    """The rate is the share of written letters with a stock phrase; rows keep the phrases."""
    dataset = small_dataset(tmp_path)
    first, _, third = job_ids(dataset)
    write = text_writer(
        {
            first: "Moreover, I am a team player. Moreover yes.",
            third: "I am confident that this works.",
        }
    )

    report = run_writer_suite(
        dataset, model=MODEL, write=write, samples=1, validator=FakeValidator({})
    )

    assert report.metrics["generic_phrasing_rate"] == 0.667
    assert report.metrics["generic_per_100w_p50"] == 16.67
    rows = {row["case_id"]: row for row in report.details["rows"]}
    phrases = sorted(tuple(row["generic_phrases"]) for row in rows.values())
    assert phrases == [
        (),
        ("i am confident that",),
        ("moreover", "moreover", "team player"),
    ]
    assert sorted(row["generic_per_100w"] for row in rows.values()) == [
        0.0,
        16.67,
        37.5,
    ]


def test_generic_phrasing_counts_written_letters_only(tmp_path: Path) -> None:
    """A fallback letter with stock phrases does not count in the rate."""
    dataset = small_dataset(tmp_path)
    first, _, _ = job_ids(dataset)
    write = text_writer(
        {first: "Furthermore, I am a team player."},
        models={first: FALLBACK_MODEL},
    )

    report = run_writer_suite(
        dataset, model=MODEL, write=write, samples=1, validator=FakeValidator({})
    )

    assert report.metrics["written"] == 2
    fallback = [r for r in report.details["rows"] if r["outcome"] == "fallback"]
    assert [(r["generic_phrases"], r["generic_per_100w"]) for r in fallback] == [
        ([], None)
    ]
    assert report.metrics["generic_phrasing_rate"] == 0.0
    assert report.metrics["generic_per_100w_p50"] == 0.0
