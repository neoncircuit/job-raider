"""Tests for the resume eval suite (CV eval suite task)."""

import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import pytest

from src.evaluation.suites.resume import (
    CHECKS,
    FALLBACK_MODEL,
    NUMBER_CHECK,
    RESUME_TEMPERATURE,
    local_resume_writer,
    run_resume_suite,
)
from src.evaluation.suites.writer import DEFAULT_DATASET_DIR, load_pairs
from src.generation.resume_writer import RESUME_SYSTEM_PROMPT, GeneratedResume
from src.llm.router import TaskType

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
    The job IDs of a dataset, in the order of the suite.

    Args:
        dataset_dir: The dataset folder.

    Returns:
        One job ID for each pair.
    """
    return [pair.job.job_id for pair in load_pairs(dataset_dir)]


def cv(
    summary: str = "An engineer who builds APIs.",
    title: str = "Engineer",
    model: str = MODEL,
) -> GeneratedResume:
    """
    A small generated CV.

    Args:
        summary: The summary (prose).
        title: The job title (not prose).
        model: The ``model_used`` of the CV.

    Returns:
        The CV.
    """
    return GeneratedResume(
        summary=summary,
        skills=["Python"],
        experience=[{"title": title, "company": "Acme", "dates": "", "highlights": []}],
        projects=[],
        education=[],
        raw_response="{}",
        model_used=model,
    )


def writer_with(cvs: Dict[str, GeneratedResume]) -> Callable[..., GeneratedResume]:
    """
    A fake CV writer.

    Args:
        cvs: Job ID to the CV it returns (default: a plain CV).

    Returns:
        The write function.
    """

    def write(job: Any, profile: Any, selection: Any) -> GeneratedResume:
        """
        Return the CV of the job.

        Args:
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            The CV.
        """
        return cvs.get(job.job_id, cv())

    return write


class FakeValidator:
    """Gives fixed issues for each job."""

    def __init__(self, issues_by_job: Optional[Dict[str, List[str]]] = None) -> None:
        """
        Keep the issues.

        Args:
            issues_by_job: Job ID to its issue values.
        """
        self.issues_by_job = issues_by_job or {}

    def validate(self, resume: Any, job: Any, profile: Any, selection: Any) -> Any:
        """
        Return the issues of the job.

        Args:
            resume: The CV.
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            A result with ``issues``, ``is_valid``, and ``overall_score``.
        """
        issues = self.issues_by_job.get(job.job_id, [])
        return SimpleNamespace(
            issues=[SimpleNamespace(value=issue) for issue in issues],
            is_valid=not issues,
            overall_score=100 - 10 * len(issues),
        )


def test_rates_count_the_flagged_cvs(tmp_path: Path) -> None:
    """Each check's rate is the share of written CVs that it flags."""
    dataset = small_dataset(tmp_path)
    first, _, third = job_ids(dataset)
    validator = FakeValidator(
        {
            first: ["hallucinated_skill"],
            third: ["missing_keyword", "hallucinated_skill"],
        }
    )

    report = run_resume_suite(
        dataset, model=MODEL, write=writer_with({}), samples=1, validator=validator
    )

    assert report.metrics["hallucinated_skill_rate"] == 0.667
    assert report.metrics["missing_keyword_rate"] == 0.333
    assert report.metrics["missing_project_rate"] == 0.0
    assert report.metrics["valid_rate"] == 0.333
    assert report.metrics["mean_score"] == round((90 + 100 + 80) / 3, 2)
    assert set(CHECKS) >= {"hallucinated_skill", NUMBER_CHECK}


def test_number_check_reads_the_prose_only(tmp_path: Path) -> None:
    """A number that is not in the profile counts in the summary, not in a title."""
    dataset = small_dataset(tmp_path)
    first, second, _ = job_ids(dataset)
    write = writer_with(
        {
            first: cv(summary="I cut hosting costs by 987%."),
            second: cv(title="Lead for 987% growth"),
        }
    )

    report = run_resume_suite(
        dataset, model=MODEL, write=write, samples=1, validator=FakeValidator()
    )

    rows = {row["case_id"]: row for row in report.details["rows"]}
    flagged = sorted(row["unsupported_numbers"] for row in rows.values())
    assert flagged == [0, 0, 1]
    assert report.metrics[f"{NUMBER_CHECK}_rate"] == 0.333


def test_stock_phrases_in_the_prose(tmp_path: Path) -> None:
    """Stock phrases in the prose give the stock-phrase rate and the rows' lists."""
    dataset = small_dataset(tmp_path)
    first, _, _ = job_ids(dataset)
    write = writer_with({first: cv(summary="A results-driven engineer.")})

    report = run_resume_suite(
        dataset, model=MODEL, write=write, samples=1, validator=FakeValidator()
    )

    assert report.metrics["generic_phrasing_rate"] == 0.333
    phrases = sorted(tuple(row["generic_phrases"]) for row in report.details["rows"])
    assert phrases == [(), (), ("results-driven",)]


def test_fallback_other_model_and_errors_are_counted_not_scored(tmp_path: Path) -> None:
    """Template CVs, CVs from another model, and writer errors are not scored."""
    dataset = small_dataset(tmp_path)
    first, second, third = job_ids(dataset)
    cvs = {
        first: cv(summary="I cut costs by 987%.", model=FALLBACK_MODEL),
        second: cv(model="other:1b"),
    }

    def write(job: Any, profile: Any, selection: Any) -> GeneratedResume:
        """
        Fail for the third job, else return the prepared CV.

        Args:
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            The CV.

        Raises:
            RuntimeError: For the third job.
        """
        if job.job_id == third:
            raise RuntimeError("model down")
        return cvs[job.job_id]

    report = run_resume_suite(
        dataset, model=MODEL, write=write, samples=1, validator=FakeValidator()
    )

    assert report.metrics["written"] == 0
    assert (
        report.metrics["fallback"],
        report.metrics["other_model"],
        report.metrics["error"],
    ) == (1.0, 1.0, 1.0)
    assert report.metrics[f"{NUMBER_CHECK}_rate"] is None
    fallback = [r for r in report.details["rows"] if r["outcome"] == "fallback"][0]
    assert (fallback["unsupported_numbers"], fallback["issues"]) == (0, [])


def test_metadata_names_the_model_temperature_and_prompt(tmp_path: Path) -> None:
    """The run metadata has the suite, model, temperature, and prompt hash."""
    report = run_resume_suite(
        small_dataset(tmp_path, 1),
        model=MODEL,
        write=writer_with({}),
        samples=2,
        validator=FakeValidator(),
    )

    assert report.suite == "resume"
    assert report.metrics["cvs"] == 2
    assert report.metadata.model == MODEL
    assert report.metadata.temperature == RESUME_TEMPERATURE
    assert (
        report.metadata.prompt_sha256
        == hashlib.sha256(RESUME_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    )


def test_unload_runs_once_and_vram_peak_is_kept(tmp_path: Path) -> None:
    """The model is unloaded once; the highest VRAM reading is the peak."""
    unloaded: List[str] = []
    readings = iter([3000, 5100, 4200])
    report = run_resume_suite(
        small_dataset(tmp_path),
        model=MODEL,
        write=writer_with({}),
        samples=1,
        validator=FakeValidator(),
        unload=unloaded.append,
        vram_probe=lambda: next(readings),
    )
    assert unloaded == [MODEL]
    assert report.metrics["peak_vram_mib"] == 5100.0


@pytest.mark.parametrize(
    "kwargs, message",
    [({"samples": 0}, "samples"), ({"model": "qwen3.5:9b"}, "allow-list")],
)
def test_bad_samples_and_models_are_refused(
    tmp_path: Path, kwargs: Dict[str, Any], message: str
) -> None:
    """Samples below 1 and models off the allow-list are refused."""
    args: Dict[str, Any] = {"model": MODEL, "write": writer_with({}), "samples": 1}
    args.update(kwargs)
    with pytest.raises(ValueError, match=message):
        run_resume_suite(small_dataset(tmp_path), **args)


def test_route_must_be_ollama_with_the_model() -> None:
    """The local writer refuses a route on another provider or model, before any call."""
    routes = {TaskType.RESUME_WRITING: SimpleNamespace(fallback_provider="openai")}
    router = SimpleNamespace(
        resolve_primary_model=lambda task, override=None: ("openai", "gpt-x"),
        routes=routes,
    )
    with pytest.raises(ValueError, match="resume writing route"):
        local_resume_writer(router, MODEL)
    assert routes[TaskType.RESUME_WRITING].fallback_provider == "openai"

    router.resolve_primary_model = lambda task, override=None: ("ollama", MODEL)
    local_resume_writer(router, MODEL)
    assert routes[TaskType.RESUME_WRITING].fallback_provider == "none"


def test_polish_step_gives_before_after_and_paired_counts(tmp_path: Path) -> None:
    """The same CVs are checked before and after the polish step."""
    import dataclasses

    dataset = small_dataset(tmp_path)
    first, second, _ = job_ids(dataset)
    write = writer_with(
        {
            first: cv(summary="A results-driven engineer."),
            second: cv(summary="An engineer."),
        }
    )

    def polish(resume: GeneratedResume) -> Any:
        """
        Remove the stock phrase of the first CV; add a number to the second.

        Args:
            resume: The CV as written.

        Returns:
            The CV after the step and the count of replaced sentences.
        """
        if "results-driven" in resume.summary:
            return dataclasses.replace(resume, summary="An engineer who ships."), 1
        if resume.summary == "An engineer.":
            return dataclasses.replace(resume, summary="I cut costs by 987%."), 1
        return resume, 0

    report = run_resume_suite(
        dataset,
        model=MODEL,
        write=write,
        polish=polish,
        samples=1,
        validator=FakeValidator(),
    )

    metrics = report.metrics
    assert metrics["before_generic_phrasing_rate"] == 0.333
    assert metrics["generic_phrasing_rate"] == 0.0
    assert metrics["cvs_losing_stock_phrases"] == 1.0
    assert metrics["cvs_gaining_accuracy_flag"] == 1.0
    assert metrics["before_unsupported_numbers_rate"] == 0.0
    assert metrics["unsupported_numbers_rate"] == 0.333
    assert metrics["stock_phrase_edits"] == 2.0
    assert metrics["polish_ms_p50"] is not None
    assert report.details["polish"] is True


def test_without_polish_after_equals_before(tmp_path: Path) -> None:
    """With a given writer and no polish, the CVs are checked as written only."""
    dataset = small_dataset(tmp_path)
    first, _, _ = job_ids(dataset)
    report = run_resume_suite(
        dataset,
        model=MODEL,
        write=writer_with({first: cv(summary="A results-driven engineer.")}),
        samples=1,
        validator=FakeValidator(),
    )
    assert report.details["polish"] is False
    assert (
        report.metrics["before_generic_phrasing_rate"]
        == report.metrics["generic_phrasing_rate"]
    )
    assert report.metrics["cvs_gaining_accuracy_flag"] == 0.0
    assert report.metrics["polish_ms_p50"] is None


def test_local_writer_turns_the_writers_polish_off(monkeypatch: Any) -> None:
    """The suite's writer asks for the CV as written, so 'before' is not polished."""
    seen: Dict[str, Any] = {}

    class FakeResumeWriter:
        """Records the write arguments."""

        def __init__(self, router: Any) -> None:
            """
            Keep nothing.

            Args:
                router: The router.
            """

        def write(self, **kwargs: Any) -> GeneratedResume:
            """
            Record the arguments and return a CV.

            Args:
                **kwargs: The write arguments.

            Returns:
                A CV.
            """
            seen.update(kwargs)
            return cv()

    monkeypatch.setattr("src.evaluation.suites.resume.ResumeWriter", FakeResumeWriter)
    routes = {TaskType.RESUME_WRITING: SimpleNamespace(fallback_provider="openai")}
    router = SimpleNamespace(
        resolve_primary_model=lambda task, override=None: ("ollama", MODEL),
        routes=routes,
    )
    write = local_resume_writer(router, MODEL)
    write("job", "profile", "selection")
    assert seen["polish"] is False


def test_polish_time_counts_only_cvs_with_stock_phrases(tmp_path: Path) -> None:
    """The median polish time is over CVs that had a stock phrase (they can call the model)."""
    dataset = small_dataset(tmp_path)
    first, _, _ = job_ids(dataset)
    write = writer_with({first: cv(summary="A results-driven engineer.")})
    # Per CV: write start, write end, polish start, polish end.
    times = iter([0.0, 1.0, 1.0, 3.0, 3.0, 4.0, 4.0, 4.001, 4.001, 5.0, 5.0, 5.001])

    report = run_resume_suite(
        dataset,
        model=MODEL,
        write=write,
        polish=lambda resume: (resume, 0),
        samples=1,
        validator=FakeValidator(),
        clock=lambda: next(times),
    )

    assert report.metrics["polish_ms_p50"] == 2000.0
