"""
Structured-output eval suite (Step 3.7).

Runs the real component of each JSON call site on a fixed set of synthetic
inputs, with a router that records each LLM answer, and checks each answer
against the call site's output model (``src/llm/structured.py``):

- ``strict``: the whole answer is one JSON object that matches the model;
- ``rescued``: only the text from the first ``{`` to the last ``}`` (what
  the old regex took) is a JSON object that matches the model;
- ``failed``: neither.

It also counts the answers in which the old parsing found no JSON object
(the component then used its fallback), the prompts that filled the
context, the peak GPU memory, and the calls that did not reach Ollama.
The suite needs Ollama, so it runs locally, not in CI. It loads one model
at a time and unloads each model after its cases.

A dataset folder has ``cases.jsonl``. The cases refer to the grounding set
(profiles, jobs, and letters) and to text files under ``tests/fixtures``.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import time
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

import requests
from pydantic import BaseModel, model_validator

from ...classifiers.job_classifier import JobClassifier
from ...extractors.jd_extractor import JDExtractor
from ...extractors.resume_parser import ResumeParser
from ...generation.cover_letter_reviewer import CoverLetterReviewer
from ...generation.cover_letter_validator import CoverLetterValidator
from ...generation.cover_letter_writer import GeneratedCoverLetter
from ...generation.resume_analyzer import ResumeAnalyzer
from ...generation.resume_writer import GeneratedResume, ResumeWriter
from ...generation.selector import ResumeSelector, SelectionOutput
from ...generation.validator import ResumeValidator
from ...llm.router import TaskType
from ...llm.structured import (
    OUTPUT_MODELS,
    StructuredOutputError,
    extract_braced_object,
    parse_structured,
)
from ...models.job_listing import JobListing
from ...models.user_profile import UserProfile
from ..datasets import load_jsonl
from ..report import EvalReport
from ..run_metadata import BACKEND_DIR, build_run_metadata
from .grounding import DEFAULT_DATASET_DIR as GROUNDING_DIR
from .grounding import GroundingCase

SUITE = "structured"
DEFAULT_DATASET_DIR = BACKEND_DIR / "tests" / "fixtures" / "eval" / "structured"
FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
DEFAULT_SAMPLES = 3
TRUNCATION_SHARE = 0.98
MAX_CONTENT_CHARS = 2000

SITE_TASK_TYPES: Dict[str, TaskType] = {
    "selection": TaskType.SELECTION,
    "resume_writing": TaskType.RESUME_WRITING,
    "resume_validation": TaskType.VALIDATION,
    "resume_analysis": TaskType.RESUME_ANALYSIS,
    "cover_letter_review": TaskType.COVER_LETTER_REVIEW,
    "cover_letter_validation": TaskType.VALIDATION,
    "resume_parsing": TaskType.RESUME_PARSING,
    "jd_extraction": TaskType.JD_EXTRACTION,
    "job_classification": TaskType.CLASSIFICATION,
}

UnloadFn = Callable[[Any, str], None]
ContextProbe = Callable[[Any, str], Optional[int]]
VramProbe = Callable[[], Optional[int]]


class StructuredCase(BaseModel):
    """One input of the fixed set, for one call site."""

    case_id: str
    site: str
    grounding_case: Optional[str] = None
    profile_id: Optional[str] = None
    text_file: Optional[str] = None
    mode: Optional[Literal["general", "job_specific"]] = None

    @model_validator(mode="after")
    def _check_inputs(self) -> "StructuredCase":
        """
        Require a known site, a matching case ID, and the site's inputs.

        Returns:
            The case.

        Raises:
            ValueError: When the site is unknown, the case ID does not start
                with ``<site>__``, or the inputs do not fit the site.
        """
        if self.site not in OUTPUT_MODELS:
            raise ValueError(f"{self.case_id}: unknown site {self.site!r}")
        if not self.case_id.startswith(f"{self.site}__"):
            raise ValueError(f"{self.case_id}: the case ID must start with the site")
        if self.site == "resume_parsing":
            ok = self.profile_id is not None
        elif self.site == "jd_extraction":
            ok = (self.text_file is None) != (self.grounding_case is None)
        elif self.site == "resume_analysis":
            ok = (self.mode == "general" and self.profile_id is not None) or (
                self.mode == "job_specific" and self.grounding_case is not None
            )
        else:
            ok = self.grounding_case is not None
        if not ok:
            raise ValueError(f"{self.case_id}: wrong inputs for site {self.site}")
        return self


@dataclass
class RecordedCall:
    """One LLM answer that the recording router saw."""

    task_type: str
    content: str
    model: Optional[str]
    provider: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    latency_ms: float
    cached: bool


class RecordingRouter:
    """Router wrapper that keeps each answer; other attributes come from the router."""

    def __init__(self, router: Any) -> None:
        """
        Wrap a router.

        Args:
            router: The real (or fake) LLM router.
        """
        self._router = router
        self.calls: List[RecordedCall] = []

    def generate(
        self,
        messages: List[Any],
        task_type: TaskType = TaskType.GENERAL,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Call the wrapped router and record its answer.

        Args:
            messages: The messages of the call.
            task_type: The task type of the call.
            model: Optional model override.
            **kwargs: Other generation arguments.

        Returns:
            The wrapped router's response.
        """
        started = time.perf_counter()
        response = self._router.generate(
            messages, task_type=task_type, model=model, **kwargs
        )
        self.calls.append(
            RecordedCall(
                task_type=task_type.value,
                content=str(response.content or ""),
                model=getattr(response, "model", None),
                provider=getattr(response, "provider", None),
                prompt_tokens=getattr(response, "prompt_tokens", None),
                completion_tokens=getattr(response, "completion_tokens", None),
                latency_ms=(time.perf_counter() - started) * 1000,
                cached=bool(getattr(response, "cached", False)),
            )
        )
        return response

    def __getattr__(self, name: str) -> Any:
        """
        Give the wrapped router's attribute (``routes``, ``resolve_primary_model``).

        Args:
            name: Attribute name.

        Returns:
            The attribute of the wrapped router.
        """
        return getattr(self._router, name)


@dataclass
class SuiteData:
    """The grounding profiles and cases that the fixed set refers to."""

    profiles: Dict[str, UserProfile]
    grounding: Dict[str, GroundingCase]


@dataclass
class CallRow:
    """The outcome of one sample of one case."""

    case_id: str
    site: str
    sample: int
    group_model: str
    outcome: str
    reason: Optional[str] = None
    legacy_no_json: bool = False
    model: Optional[str] = None
    provider: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    cached: bool = False
    truncated: bool = False
    error: Optional[str] = None
    content: Optional[str] = None


def classify_answer(
    content: str, model: type[BaseModel]
) -> Tuple[str, Optional[str], bool]:
    """
    Check one answer against its output model.

    Args:
        content: The raw LLM answer.
        model: The call site's output model.

    Returns:
        ``(outcome, reason, legacy_no_json)``: the outcome is ``strict``,
        ``rescued``, or ``failed``; the reason is the strict parser's reason
        (``None`` for ``strict``); ``legacy_no_json`` is true when the old
        parsing found no JSON object.
    """
    try:
        parse_structured(content, model)
        return "strict", None, False
    except StructuredOutputError as exc:
        reason = exc.reason
    braced = extract_braced_object(content)
    if braced is None:
        return "failed", reason, True
    try:
        legacy = json.loads(braced)
    except json.JSONDecodeError:
        return "failed", reason, True
    try:
        model.model_validate(legacy)
    except ValueError:
        return "failed", reason, False
    return "rescued", reason, False


def skill_names(profile: UserProfile) -> List[str]:
    """
    List the profile's skill names in order, without duplicates.

    Args:
        profile: The profile.

    Returns:
        Core skills first, then the other skills.
    """
    names: List[str] = []
    for name in [*profile.core_skills, *(skill.name for skill in profile.skills)]:
        if name and name.lower() not in {known.lower() for known in names}:
            names.append(name)
    return names


def fixed_selection(profile: UserProfile, job: JobListing) -> SelectionOutput:
    """
    A fixed selection for the steps after selection.

    Args:
        profile: The profile.
        job: The job.

    Returns:
        The first 3 profile projects, up to 5 profile skills that the job
        text names, and the first highlight of each selected project.
    """
    job_skills = " ".join(skill.name for skill in job.skills)
    job_text = " ".join([job.title, job.description or "", job_skills]).lower()
    projects = profile.projects[:3]
    keywords = [name for name in skill_names(profile) if name.lower() in job_text]
    return SelectionOutput(
        selected_projects=[
            {"name": project.name, "reason": "Fixed selection for the eval set."}
            for project in projects
        ],
        keywords_to_emphasize=keywords[:5],
        key_achievements=[p.highlights[0] for p in projects if p.highlights],
        summary_suggestion=profile.summary or "",
        raw_response="",
    )


def _dates(start: Any, end: Any, current: bool = False) -> str:
    """
    Format a date range as ``Mon YYYY - Mon YYYY``.

    Args:
        start: Start date or ``None``.
        end: End date or ``None``.
        current: Whether the entry has no end.

    Returns:
        The formatted range.
    """
    first = start.strftime("%b %Y") if start else ""
    last = "Present" if current or end is None else end.strftime("%b %Y")
    return f"{first} - {last}".strip(" -")


def fixed_resume(profile: UserProfile, selection: SelectionOutput) -> GeneratedResume:
    """
    A resume made only from profile facts, for the LLM resume validation.

    Args:
        profile: The profile.
        selection: The fixed selection.

    Returns:
        A resume with the profile's summary, skills, experience, selected
        projects, and education.
    """
    chosen = {item["name"] for item in selection.selected_projects}
    return GeneratedResume(
        summary=profile.summary or "",
        skills=skill_names(profile)[:12],
        experience=[
            {
                "title": item.title,
                "company": item.company,
                "dates": _dates(item.start_date, item.end_date, item.current),
                "highlights": list(item.highlights),
            }
            for item in profile.experience
        ],
        projects=[
            {
                "name": item.name,
                "description": item.description,
                "technologies": list(item.technologies),
                "highlights": list(item.highlights),
            }
            for item in profile.projects
            if item.name in chosen
        ],
        education=[
            {
                "degree": item.degree,
                "school": item.school,
                "year": str(item.end_date.year) if item.end_date else "",
            }
            for item in profile.education
        ],
        raw_response="",
        model_used="eval-fixture",
    )


def render_resume_text(profile: UserProfile) -> str:
    """
    Write a profile as plain resume text, the input of the resume parser.

    Args:
        profile: The profile.

    Returns:
        The resume text.
    """
    lines = [profile.name, profile.contact.location, str(profile.contact.email)]
    if profile.summary:
        lines += ["", "SUMMARY", profile.summary]
    lines += ["", "TECHNICAL SKILLS", ", ".join(skill_names(profile))]
    if profile.experience:
        lines += ["", "EXPERIENCE"]
        for item in profile.experience:
            lines += [
                f"{item.title} - {item.company}",
                _dates(item.start_date, item.end_date, item.current),
            ]
            lines += [f"- {text}" for text in item.highlights]
    if profile.projects:
        lines += ["", "PROJECTS"]
        for project in profile.projects:
            lines += [f"{project.name}: {project.description}"]
            if project.technologies:
                lines += [f"Tech: {', '.join(project.technologies)}"]
            lines += [f"- {text}" for text in project.highlights]
    if profile.education:
        lines += ["", "EDUCATION"]
        for school in profile.education:
            lines += [
                f"{school.degree}, {school.school}",
                _dates(school.start_date, school.end_date),
            ]
    return "\n".join(lines) + "\n"


def render_job_text(job: JobListing) -> str:
    """
    Write a job as pasted posting text, the input of the JD extractor.

    Args:
        job: The job.

    Returns:
        The posting text.
    """
    lines = [job.title, f"{job.company} - {job.location or 'Singapore'}", ""]
    lines += [job.description or ""]
    if job.skills:
        lines += ["", "Skills: " + ", ".join(skill.name for skill in job.skills)]
    return "\n".join(lines) + "\n"


def load_suite_data(grounding_dir: Path = GROUNDING_DIR) -> SuiteData:
    """
    Load the grounding profiles and cases.

    Args:
        grounding_dir: The grounding dataset folder.

    Returns:
        Profiles and cases by ID.
    """
    raw = json.loads((grounding_dir / "profiles.json").read_text(encoding="utf-8"))
    profiles = {pid: UserProfile.model_validate(data) for pid, data in raw.items()}
    cases = load_jsonl(grounding_dir / "cases.jsonl", GroundingCase)
    return SuiteData(profiles=profiles, grounding={c.case_id: c for c in cases})


def check_references(cases: List[StructuredCase], data: SuiteData) -> None:
    """
    Check that each case refers to an existing input.

    Args:
        cases: The fixed set.
        data: The grounding data.

    Raises:
        ValueError: When a case names a missing grounding case, profile, or file.
    """
    for case in cases:
        if case.grounding_case and case.grounding_case not in data.grounding:
            raise ValueError(f"{case.case_id}: unknown grounding case")
        if case.profile_id and case.profile_id not in data.profiles:
            raise ValueError(f"{case.case_id}: unknown profile")
        if case.text_file and not (FIXTURES_DIR / case.text_file).is_file():
            raise ValueError(f"{case.case_id}: missing file {case.text_file}")


def run_case(case: StructuredCase, data: SuiteData, router: Any) -> None:
    """
    Run the call site's component one time on the case's inputs.

    Args:
        case: The case.
        data: The grounding data.
        router: The (recording) router.
    """
    site = case.site
    if site == "resume_parsing":
        assert case.profile_id is not None
        ResumeParser(llm_router=router).parse_text(
            render_resume_text(data.profiles[case.profile_id])
        )
        return
    if site == "jd_extraction" and case.text_file:
        text = (FIXTURES_DIR / case.text_file).read_text(encoding="utf-8")
        JDExtractor(llm_router=router).extract_from_text(text)
        return
    if site == "resume_analysis" and case.mode == "general":
        assert case.profile_id is not None
        ResumeAnalyzer(router).analyze_general(data.profiles[case.profile_id])
        return
    assert case.grounding_case is not None
    grounding = data.grounding[case.grounding_case]
    profile = data.profiles[grounding.profile_id]
    job = JobListing.model_validate(grounding.job)
    if site == "jd_extraction":
        JDExtractor(llm_router=router).extract_from_text(render_job_text(job))
    elif site == "resume_analysis":
        ResumeAnalyzer(router).analyze_job_specific(profile, job)
    elif site == "job_classification":
        JobClassifier(llm_router=router).classify(job, use_llm=True)
    elif site == "selection":
        ResumeSelector(router).select(job, profile)
    else:
        selection = fixed_selection(profile, job)
        letter = GeneratedCoverLetter(
            content=grounding.letter,
            highlighted_experiences=[],
            word_count=len(grounding.letter.split()),
            model_used="eval-fixture",
        )
        if site == "resume_writing":
            ResumeWriter(router).write(job, profile, selection)
        elif site == "resume_validation":
            ResumeValidator(llm_router=router).validate_with_llm(
                fixed_resume(profile, selection), job, profile, selection
            )
        elif site == "cover_letter_review":
            CoverLetterReviewer(router).review(letter, job, profile, selection)
        else:
            CoverLetterValidator(llm_router=router).validate_with_llm(
                letter, job, profile, selection
            )


def ollama_base_url(router: Any, model: str) -> Optional[str]:
    """
    The base URL of the Ollama client that the router uses for a model.

    Args:
        router: The real router.
        model: The model name.

    Returns:
        The base URL, or ``None`` when the router has no Ollama client.
    """
    try:
        return str(router._get_client("ollama", model).base_url)
    except Exception:
        return None


def unload_ollama_model(router: Any, model: str) -> None:
    """
    Unload a model from Ollama (``keep_alive`` 0).

    Args:
        router: The real router.
        model: The model name.
    """
    base_url = ollama_base_url(router, model)
    if base_url is None:
        return
    try:
        requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=60,
        )
    except requests.RequestException:
        pass


def ollama_context_length(router: Any, model: str) -> Optional[int]:
    """
    The context length that Ollama uses for a loaded model (``/api/ps``).

    Args:
        router: The real router.
        model: The model name.

    Returns:
        The context length, or ``None`` when Ollama does not report it.
    """
    base_url = ollama_base_url(router, model)
    if base_url is None:
        return None
    try:
        loaded = requests.get(f"{base_url}/api/ps", timeout=10).json()
    except (requests.RequestException, ValueError):
        return None
    for item in loaded.get("models", []):
        if item.get("name") == model or item.get("model") == model:
            value = item.get("context_length")
            return int(value) if value else None
    return None


def gpu_memory_used_mib() -> Optional[int]:
    """
    The GPU memory in use, from ``nvidia-smi``.

    Returns:
        The used memory in MiB, or ``None`` when ``nvidia-smi`` is missing.
    """
    try:
        output = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
        return int(output.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def default_router() -> Any:
    """
    The app's router with local models first and the response cache off.

    Returns:
        A router that follows the saved Settings. The response cache is
        off, so each sample is a new answer.
    """
    from ...llm.router import create_router

    router = create_router(prefer_local=True)
    router._response_cache.enabled = False
    return router


def _rate(count: int, total: int) -> Optional[float]:
    """
    A share, or ``None`` for no data.

    Args:
        count: The count.
        total: The total.

    Returns:
        ``count / total``, or ``None`` when the total is 0.
    """
    return count / total if total else None


def summarize(
    rows: List[CallRow], peak_vram: Optional[int]
) -> Tuple[Dict[str, Optional[float]], Dict[str, Any]]:
    """
    Count the outcomes for each site and in total.

    Args:
        rows: One row for each answer (or missing answer).
        peak_vram: The highest GPU memory use in MiB, or ``None``.

    Returns:
        ``(metrics, per_site)``.
    """
    metrics: Dict[str, Optional[float]] = {}
    per_site: Dict[str, Any] = {}
    groups: List[Tuple[str, List[CallRow]]] = [
        (site, [row for row in rows if row.site == site]) for site in OUTPUT_MODELS
    ]
    groups.append(("", rows))
    for site, site_rows in groups:
        answered = [row for row in site_rows if row.outcome != "no_call"]
        counts = {
            name: sum(1 for row in answered if row.outcome == name)
            for name in ("strict", "rescued", "failed")
        }
        suffix = f".{site}" if site else ""
        total = len(answered)
        metrics[f"calls{suffix}"] = float(total)
        for name, count in counts.items():
            metrics[f"{name}_rate{suffix}"] = _rate(count, total)
        legacy = sum(1 for row in answered if row.legacy_no_json)
        metrics[f"legacy_no_json_rate{suffix}"] = _rate(legacy, total)
        metrics[f"truncated{suffix}"] = float(sum(r.truncated for r in answered))
        metrics[f"no_call{suffix}"] = float(len(site_rows) - total)
        if site:
            reasons: Dict[str, int] = {}
            for row in answered:
                if row.reason:
                    reasons[row.reason] = reasons.get(row.reason, 0) + 1
            latencies = [row.latency_ms for row in answered if row.latency_ms]
            prompts = [row.prompt_tokens for row in answered if row.prompt_tokens]
            per_site[site] = {
                "models": sorted({row.group_model for row in site_rows}),
                "outcomes": counts,
                "reasons": reasons,
                "errors": sum(1 for row in site_rows if row.error),
                "latency_ms_p50": statistics.median(latencies) if latencies else None,
                "prompt_tokens_max": max(prompts) if prompts else None,
            }
    metrics["non_local_calls"] = float(
        sum(1 for row in rows if row.provider not in (None, "ollama"))
    )
    metrics["cached_calls"] = float(sum(1 for row in rows if row.cached))
    metrics["peak_vram_mib"] = float(peak_vram) if peak_vram is not None else None
    return metrics, per_site


def run_structured_suite(
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    *,
    router: Optional[Any] = None,
    samples: int = DEFAULT_SAMPLES,
    unload: Optional[UnloadFn] = None,
    context_probe: Optional[ContextProbe] = None,
    vram_probe: Optional[VramProbe] = None,
    grounding_dir: Path = GROUNDING_DIR,
) -> EvalReport:
    """
    Run each case ``samples`` times and check each answer.

    Args:
        dataset_dir: Folder with ``cases.jsonl``.
        router: Router to use; the default is the app's router with the
            response cache off. Tests pass a fake.
        samples: Runs of each case.
        unload: Unloads a model after its cases (default: Ollama).
        context_probe: Gives a loaded model's context length (default:
            Ollama ``/api/ps``).
        vram_probe: Gives the GPU memory in use (default: ``nvidia-smi``).
        grounding_dir: The grounding set that the cases refer to.

    Returns:
        Report with the outcome rates per site and in total, the truncated
        prompts, the peak GPU memory, and one row for each answer.

    Raises:
        FileNotFoundError: When ``cases.jsonl`` is missing.
        ValueError: When a case is invalid or refers to a missing input.
    """
    cases_path = Path(dataset_dir) / "cases.jsonl"
    if not cases_path.exists():
        raise FileNotFoundError(f"{cases_path} not found")
    cases = load_jsonl(cases_path, StructuredCase)
    data = load_suite_data(grounding_dir)
    check_references(cases, data)

    real_router = router if router is not None else default_router()
    unload_fn = unload or unload_ollama_model
    probe_context = context_probe or ollama_context_length
    probe_vram = vram_probe or gpu_memory_used_mib
    recorder = RecordingRouter(real_router)

    def group_model(case: StructuredCase) -> str:
        """
        The primary model of the case's task type.

        Args:
            case: The case.

        Returns:
            The model name.
        """
        return str(real_router.resolve_primary_model(SITE_TASK_TYPES[case.site])[1])

    ordered = sorted(cases, key=lambda c: (group_model(c), c.site, c.case_id))
    rows: List[CallRow] = []
    context_lengths: Dict[str, Optional[int]] = {}
    peak_vram: Optional[int] = None
    for model_name, group in groupby(ordered, key=group_model):
        for case in group:
            output_model = OUTPUT_MODELS[case.site]
            task_value = SITE_TASK_TYPES[case.site].value
            for sample in range(samples):
                start = len(recorder.calls)
                error = None
                try:
                    run_case(case, data, recorder)
                except Exception as exc:  # noqa: BLE001 - count, then go on
                    error = type(exc).__name__
                calls = [
                    call
                    for call in recorder.calls[start:]
                    if call.task_type == task_value
                ]
                if not calls:
                    rows.append(
                        CallRow(
                            case_id=case.case_id,
                            site=case.site,
                            sample=sample,
                            group_model=model_name,
                            outcome="no_call",
                            error=error,
                        )
                    )
                for call in calls:
                    outcome, reason, legacy = classify_answer(
                        call.content, output_model
                    )
                    rows.append(
                        CallRow(
                            case_id=case.case_id,
                            site=case.site,
                            sample=sample,
                            group_model=model_name,
                            outcome=outcome,
                            reason=reason,
                            legacy_no_json=legacy,
                            model=call.model,
                            provider=call.provider,
                            prompt_tokens=call.prompt_tokens,
                            completion_tokens=call.completion_tokens,
                            latency_ms=round(call.latency_ms, 1),
                            cached=call.cached,
                            error=error,
                            content=(
                                None
                                if outcome == "strict"
                                else call.content[:MAX_CONTENT_CHARS]
                            ),
                        )
                    )
                used = probe_vram()
                if used is not None and (peak_vram is None or used > peak_vram):
                    peak_vram = used
        context_lengths[model_name] = probe_context(real_router, model_name)
        unload_fn(real_router, model_name)

    for row in rows:
        limit = context_lengths.get(row.group_model)
        if limit and row.prompt_tokens:
            row.truncated = row.prompt_tokens >= TRUNCATION_SHARE * limit

    metrics, per_site = summarize(rows, peak_vram)
    files = [cases_path, grounding_dir / "profiles.json", grounding_dir / "cases.jsonl"]
    files += sorted({FIXTURES_DIR / c.text_file for c in cases if c.text_file})
    metadata = build_run_metadata(SUITE, files, len(cases))
    return EvalReport(
        suite=SUITE,
        metadata=metadata,
        metrics=metrics,
        details={
            "samples": samples,
            "context_lengths": context_lengths,
            "sites": per_site,
            "rows": [row.__dict__ for row in rows],
        },
    )
