"""
Resume suite: one CV writer model on the grounding set (CV eval suite task).

Each profile-job pair of the grounding set gets ``samples`` CVs from the app's
CV writer (``ResumeWriter``). The deterministic resume validator checks each
CV (no LLM), as the Generate Resumes stage does, and the number check of the
cover-letter grounding (``flag_unsupported_number_sentences``) looks for
percents, multipliers, and counts in the CV prose that are not in the
profile. The report gives the share of CVs that each check flags.

The accuracy checks are ``hallucinated_skill`` (a skill that is not on the
profile) and ``unsupported_numbers`` (a number in the prose that is not in
the profile). The suite also reports the stock phrases in the prose
(``generic_phrasing.py``).

One run uses one model. ``ResumeWriter.write`` has no model override, so the
run stops before any call when the ``resume_writing`` route is not Ollama
with that model, and it sets the route's fallback to none. CVs from the
writer's template fallback or from another model are counted, not scored.
Tests pass a fake writer.
"""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from ...generation.cover_letter_grounding import flag_unsupported_number_sentences
from ...generation.generic_phrasing import count_words, find_generic_phrases
from ...generation.resume_writer import (
    RESUME_SYSTEM_PROMPT,
    GeneratedResume,
    ResumeWriter,
)
from ...generation.selector import SelectionOutput
from ...generation.validator import ResumeValidator, resume_prose_text
from ...llm.router import TaskType
from ...models.job_listing import JobListing
from ...models.user_profile import UserProfile
from ..report import EvalReport
from ..run_metadata import build_run_metadata
from .structured import default_router, gpu_memory_used_mib, unload_ollama_model
from .writer import DEFAULT_DATASET_DIR as WRITER_DATASET_DIR
from .writer import WriterPair, check_model, load_pairs, percentile

SUITE = "resume"
DEFAULT_DATASET_DIR = WRITER_DATASET_DIR
DEFAULT_SAMPLES = 3  # The same as the writer suite and the CLI default.
RESUME_TEMPERATURE = 0.7  # The temperature of ``ResumeWriter.write``.
FALLBACK_MODEL = "template_fallback"  # ``model_used`` of the template CV.
NUMBER_CHECK = "unsupported_numbers"

# The validator's issue values, and the number check of this suite.
CHECKS: tuple[str, ...] = (
    "hallucinated_skill",
    NUMBER_CHECK,
    "missing_project",
    "missing_keyword",
    "date_inconsistency",
)

ResumeWriteFn = Callable[[JobListing, UserProfile, SelectionOutput], GeneratedResume]
Clock = Callable[[], float]
UnloadFn = Callable[[str], None]
VramProbe = Callable[[], Optional[int]]


@dataclass
class ResumeRow:
    """One CV of one pair and its check results."""

    case_id: str
    profile_id: str
    sample: int
    outcome: str = "written"
    model_used: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    is_valid: Optional[bool] = None
    score: Optional[float] = None
    unsupported_numbers: int = 0
    generic_phrases: List[str] = field(default_factory=list)
    generic_per_100w: Optional[float] = None
    prose_words: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None


def write_and_check_cv(
    pair: WriterPair,
    sample: int,
    model: str,
    write: ResumeWriteFn,
    validator: Any,
    clock: Clock = time.perf_counter,
) -> ResumeRow:
    """
    Write one CV for a pair and check it.

    Args:
        pair: The profile-job pair.
        sample: The sample number of this CV.
        model: The model that must write the CV.
        write: Writes a CV for a job, a profile, and a selection.
        validator: Has ``validate(resume=..., job=..., profile=..., selection=...)``.
        clock: Gives the time in seconds (tests pass a fake).

    Returns:
        The row. Its outcome is ``written``, ``fallback`` (the template CV),
        ``other_model``, or ``error`` (the writer raised).
    """
    row = ResumeRow(case_id=pair.case_id, profile_id=pair.profile_id, sample=sample)
    started = clock()
    try:
        resume = write(pair.job, pair.profile, pair.selection)
    except Exception as exc:  # noqa: BLE001 - count, then go on
        row.outcome = "error"
        row.error = type(exc).__name__
        return row
    row.latency_ms = round((clock() - started) * 1000.0, 1)
    row.model_used = resume.model_used
    if resume.model_used == FALLBACK_MODEL:
        row.outcome = "fallback"
        return row
    if resume.model_used != model:
        row.outcome = "other_model"
        return row

    result = validator.validate(
        resume=resume, job=pair.job, profile=pair.profile, selection=pair.selection
    )
    issues = {
        issue.value if hasattr(issue, "value") else str(issue)
        for issue in result.issues
    }
    prose = resume_prose_text(resume)
    unsupported = flag_unsupported_number_sentences(prose, pair.profile)
    if unsupported:
        issues.add(NUMBER_CHECK)
    generic = find_generic_phrases(prose)

    row.issues = sorted(issues)
    row.is_valid = bool(result.is_valid)
    row.score = float(result.overall_score)
    row.unsupported_numbers = len(unsupported)
    row.generic_phrases = [hit.phrase for hit in generic.hits for _ in range(hit.count)]
    row.generic_per_100w = generic.per_100_words
    row.prose_words = count_words(prose)
    return row


def _rate(count: int, total: int) -> Optional[float]:
    """
    A share rounded to 3 places.

    Args:
        count: The part.
        total: The whole.

    Returns:
        ``count / total``, or None when ``total`` is 0.
    """
    return round(count / total, 3) if total else None


def summarize(rows: Sequence[ResumeRow]) -> Dict[str, Optional[float]]:
    """
    The metrics of one run.

    Args:
        rows: All rows of the run.

    Returns:
        The counts of each outcome, and for the written CVs: the share that
        each check flags, the share of valid CVs, the mean score, the share
        with a stock phrase, the median stock phrases per 100 prose words,
        the median prose word count, and the median and 95th-percentile
        latency.
    """
    written = [row for row in rows if row.outcome == "written"]
    metrics: Dict[str, Optional[float]] = {
        "cvs": float(len(rows)),
        "written": float(len(written)),
    }
    for outcome in ("fallback", "other_model", "error"):
        metrics[outcome] = float(sum(1 for row in rows if row.outcome == outcome))
    for check in CHECKS:
        flagged = sum(1 for row in written if check in row.issues)
        metrics[f"{check}_rate"] = _rate(flagged, len(written))
    metrics["valid_rate"] = _rate(
        sum(1 for row in written if row.is_valid), len(written)
    )
    scores = [row.score for row in written if row.score is not None]
    metrics["mean_score"] = round(statistics.fmean(scores), 2) if scores else None
    metrics["generic_phrasing_rate"] = _rate(
        sum(1 for row in written if row.generic_phrases), len(written)
    )
    metrics["generic_per_100w_p50"] = percentile(
        [row.generic_per_100w for row in written if row.generic_per_100w is not None],
        0.5,
    )
    metrics["prose_words_p50"] = percentile(
        [float(row.prose_words) for row in written], 0.5
    )
    latencies = [row.latency_ms for row in written]
    metrics["latency_p50_ms"] = percentile(latencies, 0.5)
    metrics["latency_p95_ms"] = percentile(latencies, 0.95)
    return metrics


def local_resume_writer(router: Any, model: str) -> ResumeWriteFn:
    """
    The app's CV writer, on a route that must use one local model, no fallback.

    Args:
        router: The app's LLM router.
        model: The Ollama model that the ``resume_writing`` route must use.

    Returns:
        The write function.

    Raises:
        ValueError: When the ``resume_writing`` route does not resolve to
            ``ollama/<model>``. No call is made.
    """
    provider, resolved = router.resolve_primary_model(TaskType.RESUME_WRITING)
    if provider != "ollama" or resolved != model:
        raise ValueError(
            f"The resume writing route uses {provider}/{resolved}, not ollama/{model}. "
            "Set the resume writing route to Ollama with that model in Settings."
        )
    router.routes[TaskType.RESUME_WRITING].fallback_provider = "none"
    writer = ResumeWriter(router)

    def write(
        job: JobListing, profile: UserProfile, selection: SelectionOutput
    ) -> GeneratedResume:
        """
        Write one CV on the checked route.

        Args:
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            The CV.
        """
        return writer.write(job=job, profile=profile, selection=selection)

    return write


def run_resume_suite(
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    *,
    model: str,
    write: Optional[ResumeWriteFn] = None,
    samples: int = DEFAULT_SAMPLES,
    validator: Optional[Any] = None,
    clock: Clock = time.perf_counter,
    router: Optional[Any] = None,
    unload: Optional[UnloadFn] = None,
    vram_probe: Optional[VramProbe] = None,
) -> EvalReport:
    """
    Write ``samples`` CVs for each pair with one model and check them.

    Args:
        dataset_dir: The grounding dataset folder.
        model: The CV writer model of this run; it must be on the writer
            allow-list (local, 7B or smaller).
        write: Writes a CV for a job, a profile, and a selection with
            ``model``. When None, the app's CV writer is used (see
            ``local_resume_writer``), and the model is unloaded and the VRAM
            is read unless ``unload`` or ``vram_probe`` is given.
        samples: CVs for each pair.
        validator: The resume validator; the default is the deterministic
            validator that the Generate Resumes stage uses.
        clock: Gives the time in seconds (tests pass a fake).
        router: The LLM router for the default writer (default: the app's).
        unload: Unloads the model once after the CVs, also on error.
        vram_probe: Gives the used VRAM in MiB after each CV, or None.

    Returns:
        Report with the metrics of ``summarize`` and ``peak_vram_mib``, and
        one row for each CV.

    Raises:
        ValueError: When ``samples`` is below 1, the model is not on the
            allow-list, a case names an unknown profile, or (with no
            ``write``) the ``resume_writing`` route is not Ollama with
            ``model``.
    """
    if samples < 1:
        raise ValueError("samples must be 1 or more")
    check_model(model)
    if write is None:
        app_router = router if router is not None else default_router()
        write = local_resume_writer(app_router, model)
        if unload is None:

            def unload_model(name: str) -> None:
                """
                Unload the model from Ollama.

                Args:
                    name: The model name.
                """
                unload_ollama_model(app_router, name)

            unload = unload_model
        if vram_probe is None:
            vram_probe = gpu_memory_used_mib

    dataset_dir = Path(dataset_dir)
    pairs = load_pairs(dataset_dir)
    checker = validator or ResumeValidator()
    rows: List[ResumeRow] = []
    peak: Optional[int] = None
    try:
        for pair in pairs:
            for sample in range(samples):
                rows.append(
                    write_and_check_cv(pair, sample, model, write, checker, clock)
                )
                if vram_probe is not None:
                    reading = vram_probe()
                    if reading is not None and (peak is None or reading > peak):
                        peak = reading
    finally:
        if unload is not None:
            unload(model)

    metadata = build_run_metadata(
        SUITE,
        [dataset_dir / "profiles.json", dataset_dir / "cases.jsonl"],
        len(pairs),
        model=model,
        temperature=RESUME_TEMPERATURE,
        prompt_sha256=hashlib.sha256(RESUME_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
    )
    metrics: Dict[str, Optional[float]] = summarize(rows)
    metrics["peak_vram_mib"] = float(peak) if peak is not None else None
    return EvalReport(
        suite=SUITE,
        metadata=metadata,
        metrics=metrics,
        details={
            "model": model,
            "samples": samples,
            "checks": list(CHECKS),
            "rows": [row.__dict__ for row in rows],
        },
    )
