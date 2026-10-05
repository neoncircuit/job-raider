#!/usr/bin/env python3
"""
Job Raider - Safe cover-letter model A/B compare (CLI)

Thin command-line wrapper over ``src.evaluation.cover_letter_compare``. The
same compare runs from the Metrics page in the app. Each run is logged to
MLflow (experiment ``cover_letter_model_compare``) unless ``--no-mlflow``.

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
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

# Allow ``from src...`` when run as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.evaluation.cover_letter_compare import (  # noqa: E402
    ALLOWED_MODELS,
    DEFAULT_COOL_DOWN_S,
    DEFAULT_REPORT_PATH,
    FORBIDDEN_SUBSTRINGS,
    choose_winner,
    list_installed_models,
    log_to_mlflow,
    model_is_installed,
    run_compare,
    save_report,
    validate_models,
)

__all__ = [
    "ALLOWED_MODELS",
    "FORBIDDEN_SUBSTRINGS",
    "choose_winner",
    "model_is_installed",
    "validate_models",
    "main",
]


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
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    # Normalize env for LLMRouter / OllamaClient constructed later.
    os.environ["OLLAMA_HOST"] = host
    return f"http://{host}"


def _print_progress(model: str, case_id: str, done: int, total: int) -> None:
    """Print one progress line before each case.

    Args:
        model: Model tag being run.
        case_id: Fixture id.
        done: Cases finished so far.
        total: Total cases in the compare.
    """
    print(f"  [{done + 1}/{total}] model={model} case={case_id} generating…")


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
        default=DEFAULT_COOL_DOWN_S,
        help="Seconds to sleep after unloading each model (default: 20).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path for the JSON report.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate allow-list and installed tags only; do not generate.",
    )
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Do not log the run to MLflow.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        validate_models(args.models)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    base_url = _ollama_base()
    try:
        installed = list_installed_models(base_url)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

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
            "(do NOT pull qwen3.5:9b), for example from Settings > Local models."
        )
        if args.dry_run:
            return 0
        runnable = [m for m in args.models if m not in missing]
        if not runnable:
            print("No allowed models installed; aborting.", file=sys.stderr)
            return 1
        print(f"\nContinuing with installed allow-list models only: {runnable}")
        args.models = runnable

    if args.dry_run:
        print("\nDry-run OK. Safe to compare when ready.")
        return 0

    report = run_compare(
        args.models,
        base_url=base_url,
        cool_down_s=args.cool_down,
        on_progress=_print_progress,
    )
    save_report(report, args.output)
    if not args.no_mlflow:
        report["mlflow"] = log_to_mlflow(report, args.output)
        save_report(report, args.output)
        if report["mlflow"]:
            print(f"MLflow run: {report['mlflow']['ui_url']}")
    print(f"\nWinner (mean validator score): {report['winner']}")
    print(f"Wrote report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
