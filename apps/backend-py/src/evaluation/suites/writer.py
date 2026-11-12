"""
Writer suite: one cover-letter writer model on the grounding set (Step 3.8).

Each profile-job pair of the grounding set gets ``samples`` letters from one
writer model. The deterministic validator checks each letter (no LLM, as in
the grounding suite), and the report gives the share of letters that each
grounding check flags. The labels of the grounding cases belong to their
fixed letters, so this suite uses only the jobs and the profiles.

The main metric is the share of letters with ``ungrounded_claims``: on the
real letters of Step 3.2, this check has precision 0.875 and recall 0.778 at
the letter level. The rows keep the count of ungrounded sentences, but the
metrics do not rank on it (precision 0.182 and recall 0.154 at the sentence
level). The validator does not find analogical claims in real letters.

Each written letter also goes through the generic-phrasing detector
(``generic_phrasing.py``). ``generic_phrasing_rate`` is the share of written
letters with one or more stock phrases, and ``generic_per_100w_p50`` is the
median count of stock phrases per 100 words. The rows keep the phrases found.

One run uses one model. Letters from the writer's template fallback or from
another model are counted, not scored. Tests pass a fake writer.

Without a fake writer, the run uses the app's cover-letter writer for one
model of ``WRITER_MODELS``, local only (Step 3.8, MH-2). The run stops before
any call when the cover-letter route is not Ollama with that model, sets the
route's fallback to none, records the peak VRAM, and unloads the model once.
"""

from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from ...generation.cover_letter_validator import CoverLetterValidator
from ...generation.cover_letter_writer import CoverLetterWriter, GeneratedCoverLetter
from ...generation.generic_phrasing import find_generic_phrases
from ...generation.selector import SelectionOutput
from ...llm.router import TaskType
from ...models.job_listing import JobListing
from ...models.user_profile import UserProfile
from ..report import EvalReport
from ..run_metadata import build_run_metadata
from .grounding import DEFAULT_DATASET_DIR as GROUNDING_DIR
from .structured import (
    default_router,
    fixed_selection,
    gpu_memory_used_mib,
    load_suite_data,
    unload_ollama_model,
)

SUITE = "writer"
DEFAULT_DATASET_DIR = GROUNDING_DIR
DEFAULT_SAMPLES = 3
WRITER_TEMPERATURE = 0.8  # The temperature of ``CoverLetterWriter.write``.
FALLBACK_MODEL = "template_fallback"  # ``model_used`` of the template letter.
MAIN_CHECK = "ungrounded_claims"
CHECKS: tuple[str, ...] = (
    MAIN_CHECK,
    "fabricated_technology",
    "fabricated_experience",
    "scope_inflation",
    "unfilled_placeholder",
)
# Local models of 7B or smaller that the user approved for this host (Step 3.8).
WRITER_MODELS: tuple[str, ...] = ("qwen2.5:7b", "qwen3.5:4b", "qwen2.5:3b", "gemma3:4b")

WriteFn = Callable[[JobListing, UserProfile, SelectionOutput], GeneratedCoverLetter]
Clock = Callable[[], float]
UnloadFn = Callable[[str], None]
VramProbe = Callable[[], Optional[int]]


@dataclass(frozen=True)
class WriterPair:
    """One profile-job pair of the grounding set, with its fixed selection."""

    case_id: str
    profile_id: str
    job: JobListing
    profile: UserProfile
    selection: SelectionOutput


@dataclass
class LetterRow:
    """One letter of one pair and its validator result."""

    case_id: str
    profile_id: str
    sample: int
    outcome: str = "written"
    model_used: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    is_valid: Optional[bool] = None
    score: Optional[float] = None
    word_count: int = 0
    ungrounded_sentences: int = 0
    generic_phrases: List[str] = field(default_factory=list)
    generic_per_100w: Optional[float] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


def load_pairs(dataset_dir: Path = DEFAULT_DATASET_DIR) -> List[WriterPair]:
    """
    Load the profile-job pairs of the grounding set, ordered by case ID.

    Args:
        dataset_dir: The grounding dataset folder.

    Returns:
        One pair for each case, with the fixed selection for its job.

    Raises:
        ValueError: When a case names an unknown profile.
    """
    data = load_suite_data(Path(dataset_dir))
    pairs: List[WriterPair] = []
    for case_id in sorted(data.grounding):
        case = data.grounding[case_id]
        profile = data.profiles.get(case.profile_id)
        if profile is None:
            raise ValueError(f"case {case_id}: unknown profile_id {case.profile_id!r}")
        job = JobListing.model_validate(case.job)
        pairs.append(
            WriterPair(
                case_id=case_id,
                profile_id=case.profile_id,
                job=job,
                profile=profile,
                selection=fixed_selection(profile, job),
            )
        )
    return pairs


def write_and_check(
    pair: WriterPair,
    sample: int,
    model: str,
    write: WriteFn,
    validator: Any,
    clock: Clock = time.perf_counter,
) -> LetterRow:
    """
    Write one letter for a pair and check it with the validator.

    Args:
        pair: The profile-job pair.
        sample: The sample number of this letter.
        model: The model that must write the letter.
        write: Writes a letter for a job, a profile, and a selection.
        validator: Has ``validate(letter, job, profile, selection)``.
        clock: Gives the time in seconds (tests pass a fake).

    Returns:
        The row. Its outcome is ``written``, ``fallback`` (the template
        letter), ``other_model``, or ``error`` (the writer raised).
    """
    row = LetterRow(case_id=pair.case_id, profile_id=pair.profile_id, sample=sample)
    started = clock()
    try:
        letter = write(pair.job, pair.profile, pair.selection)
    except Exception as exc:  # noqa: BLE001 - count, then go on
        row.outcome = "error"
        row.error = type(exc).__name__
        return row
    row.latency_ms = round((clock() - started) * 1000.0, 1)
    row.model_used = letter.model_used
    row.word_count = letter.word_count
    if letter.model_used == FALLBACK_MODEL:
        row.outcome = "fallback"
        return row
    if letter.model_used != model:
        row.outcome = "other_model"
        return row
    result = validator.validate(letter, pair.job, pair.profile, pair.selection)
    row.issues = sorted(
        issue.value if hasattr(issue, "value") else str(issue)
        for issue in result.issues
    )
    row.is_valid = bool(result.is_valid)
    row.score = float(result.score)
    row.ungrounded_sentences = len(
        (result.details or {}).get("ungrounded_sentences") or []
    )
    generic = find_generic_phrases(letter.content)
    row.generic_phrases = [hit.phrase for hit in generic.hits for _ in range(hit.count)]
    row.generic_per_100w = generic.per_100_words
    return row


def percentile(values: Sequence[float], share: float) -> Optional[float]:
    """
    The nearest-rank percentile of a list of numbers.

    Args:
        values: The numbers.
        share: The percentile as a share, from 0 to 1 (0.5 is the median).

    Returns:
        The smallest value with at least ``share`` of the values at or below
        it, or None when the list is empty.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(share * len(ordered)))
    return ordered[rank - 1]


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


def summarize(rows: Sequence[LetterRow]) -> Dict[str, Optional[float]]:
    """
    The metrics of one run.

    Args:
        rows: All rows of the run.

    Returns:
        The counts of each outcome, and for the written letters: the share
        that each check flags, the share of valid letters, the mean score,
        the share with a stock phrase, the median stock phrases per 100
        words, the median word count, and the median and 95th-percentile
        latency.
    """
    written = [row for row in rows if row.outcome == "written"]
    metrics: Dict[str, Optional[float]] = {
        "letters": float(len(rows)),
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
    metrics["words_p50"] = percentile([float(row.word_count) for row in written], 0.5)
    latencies = [row.latency_ms for row in written]
    metrics["latency_p50_ms"] = percentile(latencies, 0.5)
    metrics["latency_p95_ms"] = percentile(latencies, 0.95)
    return metrics


def pair_counts(rows: Sequence[LetterRow]) -> Dict[str, Dict[str, Any]]:
    """
    For each pair: the written letters and the letters that each check flags.

    Args:
        rows: All rows of the run.

    Returns:
        Case ID to ``{"profile_id", "written", "flagged": {check: count}}``.
        The paired comparison of two runs uses this.
    """
    counts: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        entry = counts.setdefault(
            row.case_id,
            {
                "profile_id": row.profile_id,
                "written": 0,
                "flagged": {check: 0 for check in CHECKS},
            },
        )
        if row.outcome != "written":
            continue
        entry["written"] += 1
        for check in CHECKS:
            if check in row.issues:
                entry["flagged"][check] += 1
    return counts


def profile_rates(rows: Sequence[LetterRow]) -> Dict[str, Optional[float]]:
    """
    The share of written letters with the main check, for each profile.

    Args:
        rows: All rows of the run.

    Returns:
        Profile ID to the share of its written letters with ``ungrounded_claims``.
    """
    rates: Dict[str, Optional[float]] = {}
    for profile_id in sorted({row.profile_id for row in rows}):
        written = [
            row
            for row in rows
            if row.profile_id == profile_id and row.outcome == "written"
        ]
        flagged = sum(1 for row in written if MAIN_CHECK in row.issues)
        rates[profile_id] = _rate(flagged, len(written))
    return rates


def check_model(model: str) -> None:
    """
    Refuse a model that is not on the writer allow-list.

    Args:
        model: The writer model of the run.

    Raises:
        ValueError: When the model is not in ``WRITER_MODELS``.
    """
    if model not in WRITER_MODELS:
        raise ValueError(
            f"model {model!r} is not on the writer allow-list: "
            f"{', '.join(WRITER_MODELS)}"
        )


def local_writer(router: Any, model: str) -> WriteFn:
    """
    The app's cover-letter writer, fixed to one local model with no fallback.

    Args:
        router: The app's LLM router.
        model: The Ollama model that the cover-letter route must use.

    Returns:
        The write function, which calls the writer with ``model``.

    Raises:
        ValueError: When the cover-letter route does not resolve to
            ``ollama/<model>``. No call is made.
    """
    provider, resolved = router.resolve_primary_model(
        TaskType.COVER_LETTER_WRITING, model
    )
    if provider != "ollama" or resolved != model:
        raise ValueError(
            f"The cover-letter route uses {provider}/{resolved}, not ollama/{model}. "
            "Set the cover-letter writing route to Ollama in Settings."
        )
    router.routes[TaskType.COVER_LETTER_WRITING].fallback_provider = "none"
    writer = CoverLetterWriter(router)

    def write(
        job: JobListing, profile: UserProfile, selection: SelectionOutput
    ) -> GeneratedCoverLetter:
        """
        Write one letter with the model.

        Args:
            job: The job.
            profile: The profile.
            selection: The selection.

        Returns:
            The letter.
        """
        return writer.write(job=job, profile=profile, selection=selection, model=model)

    return write


def run_writer_suite(
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    *,
    model: str,
    write: Optional[WriteFn] = None,
    samples: int = DEFAULT_SAMPLES,
    validator: Optional[Any] = None,
    clock: Clock = time.perf_counter,
    router: Optional[Any] = None,
    unload: Optional[UnloadFn] = None,
    vram_probe: Optional[VramProbe] = None,
) -> EvalReport:
    """
    Write ``samples`` letters for each pair with one model and check them.

    Args:
        dataset_dir: The grounding dataset folder.
        model: The writer model of this run; it must be in ``WRITER_MODELS``.
        write: Writes a letter for a job, a profile, and a selection with
            ``model``. When None, the app's writer is used (see ``local_writer``),
            and the model is unloaded and the VRAM is read unless ``unload`` or
            ``vram_probe`` is given.
        samples: Letters for each pair.
        validator: The letter validator; the default is the deterministic
            validator of the grounding suite (no LLM).
        clock: Gives the time in seconds (tests pass a fake).
        router: The LLM router for the default writer (default: the app's).
        unload: Unloads the model once after the letters, also on error.
        vram_probe: Gives the used VRAM in MiB after each letter, or None.

    Returns:
        Report with the metrics of ``summarize`` and ``peak_vram_mib``, the
        main-check share for each profile, the counts for each pair, and one
        row for each letter.

    Raises:
        ValueError: When ``samples`` is below 1, the model is not on the
            writer allow-list, a case names an unknown profile, or (with no
            ``write``) the cover-letter route is not Ollama with ``model``.
    """
    if samples < 1:
        raise ValueError("samples must be 1 or more")
    check_model(model)
    if write is None:
        app_router = router if router is not None else default_router()
        write = local_writer(app_router, model)
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
    checker = validator or CoverLetterValidator(llm_router=None, strict_mode=False)
    rows: List[LetterRow] = []
    peak: Optional[int] = None
    try:
        for pair in pairs:
            for sample in range(samples):
                rows.append(write_and_check(pair, sample, model, write, checker, clock))
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
        temperature=WRITER_TEMPERATURE,
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
            "main_check": MAIN_CHECK,
            "profiles": profile_rates(rows),
            "pairs": pair_counts(rows),
            "rows": [row.__dict__ for row in rows],
        },
    )
