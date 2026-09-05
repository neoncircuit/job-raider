#!/usr/bin/env python3
"""
Job Raider - Safe cover-letter model A/B compare

Compares writer models sequentially on fixed profile/JD fixtures.
Designed for hosts that BSODs under multi-model GPU hops.

Rules (locked):
- Allowed tags: qwen2.5:7b (baseline) and qwen3.5:4b only.
- Forbidden: qwen3.5:9b and larger / multi-model hop sessions.
- One Ollama model loaded at a time; unload between models.
- Cool-down sleep after each model completes.

Usage (from apps/backend-py with .venv active):

```bash
python scripts/compare_cover_letter_models.py
python scripts/compare_cover_letter_models.py --models qwen2.5:7b qwen3.5:4b
python scripts/compare_cover_letter_models.py --dry-run
```

Author: Job Raider
Date: 2026-08-25
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Allow ``from src...`` when run as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

ALLOWED_MODELS = ("qwen2.5:7b", "qwen3.5:4b")
FORBIDDEN_SUBSTRINGS = ("qwen3.5:9b", "9b", "12b", "14b", "32b", "70b")


def _ollama_base() -> str:
    """
    Resolve the Ollama HTTP base URL.

    Strips a leading ``http(s)://`` so the shared Ollama client (which always
    prepends ``http://``) does not double the scheme when ``OLLAMA_HOST`` is
    set for this script.

    Returns:
        Base URL without a trailing slash.
    """
    host = (os.getenv("OLLAMA_HOST") or "127.0.0.1:11434").strip().rstrip("/")
    if host.startswith("https://"):
        host = host[len("https://") :]
    elif host.startswith("http://"):
        host = host[len("http://") :]
    # Normalize env for LLMRouter / OllamaClient constructed later.
    os.environ["OLLAMA_HOST"] = host
    return f"http://{host}"


def list_installed_models() -> List[str]:
    """
    List model tags installed on the Ollama host.

    Returns:
        Model name strings (may include ``:latest`` tags).
    """
    url = f"{_ollama_base()}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not list Ollama models at {url}: {exc}") from exc
    models = payload.get("models") or []
    names: List[str] = []
    for item in models:
        name = item.get("name") if isinstance(item, dict) else None
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def model_is_installed(model: str, installed: Sequence[str]) -> bool:
    """
    Return True when ``model`` matches an installed tag.

    Args:
        model: Requested model tag.
        installed: Tags from ``/api/tags``.

    Returns:
        True if an exact or prefix match exists.
    """
    if model in installed:
        return True
    return any(tag == model or tag.startswith(f"{model}:") for tag in installed)


def unload_model(model: str) -> None:
    """
    Ask Ollama to unload a model from VRAM (``keep_alive=0``).

    Args:
        model: Model tag to unload.
    """
    url = f"{_ollama_base()}/api/generate"
    body = json.dumps(
        {"model": model, "prompt": "", "keep_alive": 0, "stream": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Warning: unload of {model} failed: {exc}", file=sys.stderr)


def validate_models(models: Sequence[str]) -> None:
    """
    Reject forbidden or unknown compare tags.

    Args:
        models: Requested writer model tags.

    Raises:
        ValueError: When a model is outside the safe allow-list.
    """
    for model in models:
        lowered = model.lower()
        if model not in ALLOWED_MODELS:
            raise ValueError(
                f"Model '{model}' is not in the safe allow-list "
                f"{ALLOWED_MODELS}. Do not use 9B+ on unstable GPU hosts."
            )
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in lowered and model not in ALLOWED_MODELS:
                raise ValueError(f"Forbidden model tag fragment '{bad}' in '{model}'")


def build_fixtures() -> List[Tuple[str, Any, Any, Any]]:
    """
    Build fixed (case_id, job, profile, selection) fixtures.

    Returns:
        List of compare cases shared across models.
    """
    from src.generation.selector import SelectionOutput
    from src.models.job_listing import JobListing, JobRequirement, JobSource
    from src.models.job_listing import Skill as JobSkill
    from src.models.user_profile import (
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

    cases: List[Tuple[str, Any, Any, Any]] = [
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
    return cases


def score_letter(
    letter: Any,
    job: Any,
    profile: Any,
    selection: Any,
) -> Dict[str, Any]:
    """
    Score a generated letter with the deterministic validator.

    Args:
        letter: ``GeneratedCoverLetter`` instance.
        job: Target job listing.
        profile: Candidate profile.
        selection: Selection strategy output.

    Returns:
        Compact score payload for the compare report.
    """
    from src.generation.cover_letter_validator import CoverLetterValidator

    validation = CoverLetterValidator().validate(
        cover_letter=letter,
        job=job,
        profile=profile,
        selection=selection,
    )
    issue_names = [
        issue.value if hasattr(issue, "value") else str(issue)
        for issue in validation.issues
    ]
    return {
        "score": validation.score,
        "is_valid": validation.is_valid,
        "issues": issue_names,
        "word_count": letter.word_count,
        "ungrounded_sentence_count": len(
            (validation.details or {}).get("ungrounded_sentences") or []
        ),
    }


def run_model(
    model: str,
    cases: Sequence[Tuple[str, Any, Any, Any]],
    cool_down_s: float,
) -> Dict[str, Any]:
    """
    Generate and score all fixtures for one model, then unload it.

    Args:
        model: Writer model tag.
        cases: Fixed compare fixtures.
        cool_down_s: Seconds to sleep after unload.

    Returns:
        Per-model report dict.
    """
    from src.generation.cover_letter_writer import CoverLetterWriter
    from src.llm.router import LLMRouter

    print(f"\n=== Model {model} ===")
    router = LLMRouter()
    writer = CoverLetterWriter(router)
    case_results: List[Dict[str, Any]] = []

    try:
        for case_id, job, profile, selection in cases:
            print(f"  case={case_id} generating…")
            started = time.perf_counter()
            letter = writer.write(
                job=job,
                profile=profile,
                selection=selection,
                model=model,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            scored = score_letter(letter, job, profile, selection)
            case_results.append(
                {
                    "case_id": case_id,
                    "elapsed_ms": round(elapsed_ms, 1),
                    "model_used": letter.model_used,
                    "preview": " ".join(letter.content.split()[:40]),
                    **scored,
                }
            )
            print(
                f"  case={case_id} score={scored['score']} "
                f"valid={scored['is_valid']} words={scored['word_count']}"
            )
    finally:
        print(f"  unloading {model}…")
        unload_model(model)
        if cool_down_s > 0:
            print(f"  cool-down {cool_down_s:.0f}s…")
            time.sleep(cool_down_s)

    scores = [c["score"] for c in case_results]
    return {
        "model": model,
        "mean_score": round(sum(scores) / len(scores), 2) if scores else None,
        "cases": case_results,
    }


def choose_winner(reports: Sequence[Dict[str, Any]]) -> Optional[str]:
    """
    Pick the model with the highest mean validator score.

    Args:
        reports: Per-model compare reports.

    Returns:
        Winning model tag, or None when reports are empty.
    """
    ranked = [
        (r["model"], r.get("mean_score"))
        for r in reports
        if r.get("mean_score") is not None
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[0][0]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    CLI entry point.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 success, 1 validation/runtime error).
    """
    parser = argparse.ArgumentParser(
        description="Safe sequential cover-letter A/B (7b vs 4b only)."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(ALLOWED_MODELS),
        help=f"Models to compare (default: {' '.join(ALLOWED_MODELS)})",
    )
    parser.add_argument(
        "--cool-down",
        type=float,
        default=20.0,
        help="Seconds to sleep after unloading each model (default: 20).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_BACKEND_ROOT / "data" / "outputs" / "cover_letter_model_ab.json",
        help="Path for the JSON report.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate allow-list and installed tags only; do not generate.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        validate_models(args.models)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        installed = list_installed_models()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Ensure OLLAMA_HOST is scheme-free before LLMRouter starts.
    _ollama_base()

    missing = [m for m in args.models if not model_is_installed(m, installed)]
    print("Installed Ollama models:")
    for name in installed:
        print(f"  - {name}")
    if missing:
        print("\nMissing models for compare:")
        for name in missing:
            print(f"  - {name}")
        print(
            "\nPull only the missing 4b tag when ready "
            "(do NOT pull qwen3.5:9b):\n"
            "  ollama pull qwen3.5:4b\n"
            "Then re-run this script with one model resident at a time."
        )
        if args.dry_run:
            return 0
        # Still allow partial run on installed allow-list models.
        runnable = [m for m in args.models if m not in missing]
        if not runnable:
            print("No allowed models installed; aborting.", file=sys.stderr)
            return 1
        print(f"\nContinuing with installed allow-list models only: {runnable}")
        args.models = runnable

    if args.dry_run:
        print("\nDry-run OK. Safe to compare when ready.")
        return 0

    cases = build_fixtures()
    reports: List[Dict[str, Any]] = []
    for model in args.models:
        reports.append(run_model(model, cases, cool_down_s=args.cool_down))

    winner = choose_winner(reports)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "protocol": {
            "allowed": list(ALLOWED_MODELS),
            "forbidden": ["qwen3.5:9b", "larger multi-model hops"],
            "one_model_at_a_time": True,
            "cool_down_s": args.cool_down,
        },
        "winner": winner,
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWinner (mean validator score): {winner}")
    print(f"Wrote report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
