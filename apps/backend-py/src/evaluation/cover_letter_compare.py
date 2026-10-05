"""
Job Raider - Safe cover-letter model compare (core).

Compares writer models one at a time on fixed profile and job fixtures, scores
each letter with the deterministic validator, and logs the run to MLflow.
Used by ``scripts/compare_cover_letter_models.py`` and the evaluation API.

Rules (locked; the host is unstable under multi-model GPU hops):

- Allowed tags: ``qwen2.5:7b`` (baseline) and ``qwen3.5:4b`` only.
- One Ollama model loaded at a time; unload between models.
- Cool-down sleep after each model completes.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import requests

from ..utils.logger import Components, get_logger

logger = get_logger(Components.GENERATION)

ALLOWED_MODELS: Tuple[str, ...] = ("qwen2.5:7b", "qwen3.5:4b")
FORBIDDEN_SUBSTRINGS = ("qwen3.5:9b", "9b", "12b", "14b", "32b", "70b")
DEFAULT_COOL_DOWN_S = 20.0
DEFAULT_REPORT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "outputs"
    / "cover_letter_model_ab.json"
)
MLFLOW_EXPERIMENT = "cover_letter_model_compare"

Case = Tuple[str, Any, Any, Any]
ProgressFn = Callable[[str, str, int, int], None]
"""Called as ``(model, case_id, done_cases, total_cases)`` before each case."""


def validate_models(models: Sequence[str]) -> None:
    """Reject forbidden or unknown compare tags.

    Args:
        models: Requested writer model tags.

    Raises:
        ValueError: When the list is empty or a model is outside the allow-list.
    """
    if not models:
        raise ValueError("Choose at least one model to compare.")
    for model in models:
        if model not in ALLOWED_MODELS:
            raise ValueError(
                f"Model '{model}' is not in the safe allow-list "
                f"{ALLOWED_MODELS}. Do not use 9B+ on unstable GPU hosts."
            )
        lowered = model.lower()
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in lowered:
                raise ValueError(f"Forbidden model tag fragment '{bad}' in '{model}'")


def model_is_installed(model: str, installed: Sequence[str]) -> bool:
    """Return True when ``model`` matches an installed tag.

    Args:
        model: Requested model tag.
        installed: Tags from ``/api/tags``.

    Returns:
        True if an exact or prefix match exists.
    """
    return any(tag == model or tag.startswith(f"{model}:") for tag in installed)


def list_installed_models(base_url: str, timeout: float = 10.0) -> List[str]:
    """List model tags installed on the Ollama host.

    Args:
        base_url: Ollama base URL, for example ``http://localhost:11434``.
        timeout: Request timeout in seconds.

    Returns:
        Model name strings.

    Raises:
        RuntimeError: When Ollama cannot be reached.
    """
    url = f"{base_url}/api/tags"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        models = response.json().get("models") or []
    except Exception as exc:  # noqa: BLE001 - any transport error
        raise RuntimeError(f"Could not list Ollama models at {url}: {exc}") from exc
    return [
        m["name"].strip()
        for m in models
        if isinstance(m, dict) and isinstance(m.get("name"), str) and m["name"].strip()
    ]


def unload_model(base_url: str, model: str) -> None:
    """Ask Ollama to unload a model from VRAM (``keep_alive=0``).

    Args:
        base_url: Ollama base URL.
        model: Model tag to unload.
    """
    try:
        requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": 0, "stream": False},
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001 - unload is best effort
        logger.warning("Unload of %s failed: %s", model, exc)


def build_fixtures() -> List[Case]:
    """Build fixed ``(case_id, job, profile, selection)`` fixtures.

    Returns:
        Compare cases shared across models.
    """
    from ..generation.selector import SelectionOutput
    from ..models.job_listing import JobListing, JobRequirement, JobSource
    from ..models.job_listing import Skill as JobSkill
    from ..models.user_profile import (
        ContactInfo,
        ProficiencyLevel,
        Project,
        Skill,
        SkillCategory,
        UserProfile,
        WorkExperience,
    )

    profile = UserProfile(
        name="Alex Chen",
        contact=ContactInfo(email="alex@example.com", location="Singapore"),
        summary="Software engineer focused on Python APIs and data pipelines.",
        skills=[
            Skill(
                name="Python",
                category=SkillCategory.PROGRAMMING_LANGUAGE,
                proficiency=ProficiencyLevel.ADVANCED,
                years_of_experience=4,
            ),
            Skill(
                name="FastAPI",
                category=SkillCategory.FRAMEWORK,
                proficiency=ProficiencyLevel.INTERMEDIATE,
                years_of_experience=2,
            ),
            Skill(
                name="PostgreSQL",
                category=SkillCategory.DATABASE,
                proficiency=ProficiencyLevel.INTERMEDIATE,
                years_of_experience=2,
            ),
        ],
        core_skills=["Python", "FastAPI", "PostgreSQL"],
        projects=[
            Project(
                name="Job Matching API",
                description="Built a FastAPI service that ranks job listings.",
                technologies=["Python", "FastAPI", "PostgreSQL"],
                highlights=["Cut ranking latency by 35%"],
            )
        ],
        experience=[
            WorkExperience(
                company="DataWorks",
                title="Software Engineer",
                location="Singapore",
                start_date=datetime(2022, 1, 1),
                current=True,
                description="Built internal APIs and ETL jobs.",
                highlights=[
                    "Reduced API latency by 35%",
                    "Shipped FastAPI billing endpoints used by 8 teams",
                ],
                technologies=["Python", "FastAPI", "PostgreSQL"],
            )
        ],
    )

    selection = SelectionOutput(
        selected_projects=[
            {
                "name": "Job Matching API",
                "reason": "Uses Python and FastAPI",
            }
        ],
        keywords_to_emphasize=["Python", "FastAPI", "PostgreSQL", "API"],
        key_achievements=[
            "Reduced API latency by 35%",
            "Shipped FastAPI billing endpoints used by 8 teams",
        ],
        summary_suggestion="Python engineer with FastAPI and PostgreSQL experience",
        raw_response="",
    )

    return [
        (
            "python_api_aligned",
            JobListing(
                title="Backend Engineer",
                company="Harbor Labs",
                job_id="ab-case-1",
                source=JobSource.MANUAL,
                location="Singapore",
                description=(
                    "Build FastAPI services and PostgreSQL schemas for "
                    "internal products."
                ),
                requirements=[
                    JobRequirement(text="Python experience"),
                    JobRequirement(text="FastAPI or similar web frameworks"),
                ],
                skills=[
                    JobSkill(name="Python"),
                    JobSkill(name="FastAPI"),
                    JobSkill(name="PostgreSQL"),
                ],
            ),
            profile,
            selection,
        ),
        (
            "data_pipeline_partial",
            JobListing(
                title="Data Engineer",
                company="River Analytics",
                job_id="ab-case-2",
                source=JobSource.MANUAL,
                location="Remote",
                description=(
                    "Own ETL pipelines and warehouse models. Python preferred."
                ),
                requirements=[
                    JobRequirement(text="Python for data pipelines"),
                    JobRequirement(text="SQL and data modeling"),
                ],
                skills=[
                    JobSkill(name="Python"),
                    JobSkill(name="SQL"),
                ],
            ),
            profile,
            selection,
        ),
        (
            "domain_mismatch_facilities",
            JobListing(
                title="Facilities Coordinator",
                company="CampusOps",
                job_id="ab-case-3",
                source=JobSource.MANUAL,
                location="On-site",
                description=(
                    "Coordinate building maintenance work orders and vendor "
                    "schedules."
                ),
                requirements=[
                    JobRequirement(text="Facilities operations experience"),
                    JobRequirement(text="Vendor coordination"),
                ],
                skills=[],
            ),
            profile,
            selection,
        ),
    ]


def score_letter(letter: Any, job: Any, profile: Any, selection: Any) -> Dict[str, Any]:
    """Score a generated letter with the deterministic validator.

    Args:
        letter: ``GeneratedCoverLetter`` instance.
        job: Target job listing.
        profile: Candidate profile.
        selection: Selection strategy output.

    Returns:
        Compact score payload for the compare report.
    """
    from ..generation.cover_letter_validator import CoverLetterValidator

    validation = CoverLetterValidator().validate(
        cover_letter=letter, job=job, profile=profile, selection=selection
    )
    return {
        "score": validation.score,
        "is_valid": validation.is_valid,
        "issues": [
            issue.value if hasattr(issue, "value") else str(issue)
            for issue in validation.issues
        ],
        "word_count": letter.word_count,
        "ungrounded_sentence_count": len(
            (validation.details or {}).get("ungrounded_sentences") or []
        ),
    }


def _default_writer() -> Any:
    """Create the production cover-letter writer.

    Returns:
        A ``CoverLetterWriter`` backed by a fresh ``LLMRouter``.
    """
    from ..generation.cover_letter_writer import CoverLetterWriter
    from ..llm.router import LLMRouter

    return CoverLetterWriter(LLMRouter())


def run_compare(
    models: Sequence[str],
    base_url: str,
    cool_down_s: float = DEFAULT_COOL_DOWN_S,
    cases: Optional[Sequence[Case]] = None,
    writer_factory: Callable[[], Any] = _default_writer,
    scorer: Callable[[Any, Any, Any, Any], Dict[str, Any]] = score_letter,
    on_progress: Optional[ProgressFn] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Generate and score every fixture for each model, one model at a time.

    Args:
        models: Validated writer model tags, run in order.
        base_url: Ollama base URL (used to unload between models).
        cool_down_s: Seconds to sleep after each model is unloaded.
        cases: Fixtures; defaults to ``build_fixtures()``.
        writer_factory: Creates a writer with ``write(job, profile, selection, model)``.
        scorer: Scores a letter; defaults to the deterministic validator.
        on_progress: Optional callback before each case.
        sleep: Sleep function (injectable for tests).

    Returns:
        Report dict with ``generated_at``, ``protocol``, ``winner``, and ``reports``.
    """
    cases = list(cases) if cases is not None else build_fixtures()
    total = len(models) * len(cases)
    done = 0
    reports: List[Dict[str, Any]] = []

    for model in models:
        writer = writer_factory()
        case_results: List[Dict[str, Any]] = []
        try:
            for case_id, job, profile, selection in cases:
                if on_progress:
                    on_progress(model, case_id, done, total)
                started = time.perf_counter()
                letter = writer.write(
                    job=job, profile=profile, selection=selection, model=model
                )
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                case_results.append(
                    {
                        "case_id": case_id,
                        "elapsed_ms": round(elapsed_ms, 1),
                        "model_used": letter.model_used,
                        "preview": " ".join(letter.content.split()[:40]),
                        **scorer(letter, job, profile, selection),
                    }
                )
                done += 1
        finally:
            unload_model(base_url, model)
            if cool_down_s > 0:
                sleep(cool_down_s)

        scores = [c["score"] for c in case_results]
        reports.append(
            {
                "model": model,
                "mean_score": round(sum(scores) / len(scores), 2) if scores else None,
                "cases": case_results,
            }
        )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "protocol": {
            "allowed": list(ALLOWED_MODELS),
            "forbidden": ["qwen3.5:9b", "larger multi-model hops"],
            "one_model_at_a_time": True,
            "cool_down_s": cool_down_s,
        },
        "winner": choose_winner(reports),
        "reports": reports,
    }


def choose_winner(reports: Sequence[Dict[str, Any]]) -> Optional[str]:
    """Pick the model with the highest mean validator score.

    Args:
        reports: Per-model compare reports.

    Returns:
        Winning model tag, or None when no model has a score.
    """
    ranked = [
        (r["model"], r["mean_score"])
        for r in reports
        if r.get("mean_score") is not None
    ]
    if not ranked:
        return None
    return max(ranked, key=lambda item: item[1])[0]


def _metric_key(*parts: str) -> str:
    """Build an MLflow-safe metric key.

    Args:
        parts: Key parts such as model tag and case id.

    Returns:
        Parts joined by ``.`` with unsupported characters replaced by ``_``.
    """
    return ".".join(re.sub(r"[^A-Za-z0-9_\-/ ]", "_", p) for p in parts)


def save_report(report: Dict[str, Any], path: Path = DEFAULT_REPORT_PATH) -> Path:
    """Write the compare report as JSON.

    Args:
        report: Report from ``run_compare`` (may include ``mlflow``).
        path: Output file.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def load_report(path: Path = DEFAULT_REPORT_PATH) -> Optional[Dict[str, Any]]:
    """Read the last saved compare report.

    Args:
        path: Report file.

    Returns:
        The report, or None when no readable report exists.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def log_to_mlflow(
    report: Dict[str, Any],
    report_path: Path,
    tracker_factory: Optional[Callable[..., Any]] = None,
) -> Optional[Dict[str, str]]:
    """Log a compare run to MLflow: params, metrics, and the JSON report.

    MLflow problems are logged and swallowed so a finished compare is never
    lost because the tracking server is down.

    Args:
        report: Report from ``run_compare``.
        report_path: Saved JSON report to attach as an artifact.
        tracker_factory: Creates the tracker; defaults to ``create_mlflow_tracker``.

    Returns:
        Dict with ``run_id``, ``experiment_id``, and ``ui_url``, or None.
    """
    if tracker_factory is None:
        from ..metrics.mlflow_tracker import create_mlflow_tracker

        tracker_factory = create_mlflow_tracker
    try:
        tracker = tracker_factory(
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI"),
            experiment_name=MLFLOW_EXPERIMENT,
        )
        if tracker is None:
            logger.warning("MLflow is not installed; compare run not logged.")
            return None
        reports = report.get("reports", [])
        run_id = tracker.start_run(
            run_name=f"compare-{report.get('generated_at', '')}",
            tags={"winner": str(report.get("winner"))},
        )
        try:
            tracker.log_params(
                {
                    "models": ",".join(r["model"] for r in reports),
                    "cool_down_s": report.get("protocol", {}).get("cool_down_s"),
                    "case_count": len(reports[0]["cases"]) if reports else 0,
                }
            )
            metrics: Dict[str, float] = {}
            for r in reports:
                if r.get("mean_score") is not None:
                    metrics[_metric_key("mean_score", r["model"])] = r["mean_score"]
                for c in r["cases"]:
                    metrics[_metric_key("score", r["model"], c["case_id"])] = c["score"]
                    metrics[_metric_key("latency_ms", r["model"], c["case_id"])] = c[
                        "elapsed_ms"
                    ]
            tracker.log_metrics(metrics)
            tracker.log_artifact(str(report_path))
        finally:
            tracker.end_run()
        experiment_id = _experiment_id()
        ui_base = os.getenv("MLFLOW_UI_URL", "http://localhost:5000").rstrip("/")
        return {
            "run_id": run_id,
            "experiment_id": experiment_id or "",
            "ui_url": (
                f"{ui_base}/#/experiments/{experiment_id}/runs/{run_id}"
                if experiment_id
                else ui_base
            ),
        }
    except Exception as exc:  # noqa: BLE001 - tracking must not fail the compare
        logger.warning("MLflow logging for compare run failed: %s", exc)
        return None


def _experiment_id() -> Optional[str]:
    """Look up the compare experiment id.

    Returns:
        Experiment id, or None when it cannot be read.
    """
    try:
        import mlflow

        experiment = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT)
        return experiment.experiment_id if experiment else None
    except Exception:  # noqa: BLE001
        return None
