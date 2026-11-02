"""
Offline evaluation suites, by name (Step 3.1).

Each suite loads a labeled dataset folder and returns an ``EvalReport``.
Suites are imported only when they run, so ``main.py --help`` stays fast.
Step 3.3 adds ``scam`` and ``emscad``. Step 3.5 adds ``dedupe``.
Step 3.7 adds ``structured`` (local only; it needs Ollama).
Step 3.8 adds ``writer`` (local only; it needs Ollama).
Later steps add ``ranking`` and ``compare``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Tuple

from ..report import EvalReport

SuiteRunner = Callable[..., EvalReport]

SUITE_NAMES: Tuple[str, ...] = (
    "grounding",
    "scam",
    "emscad",
    "dedupe",
    "structured",
    "writer",
)


def get_suite(name: str) -> Tuple[SuiteRunner, Path]:
    """
    Return the runner and the default dataset folder of a suite.

    Args:
        name: Suite name from ``SUITE_NAMES``.

    Returns:
        ``(runner, default_dataset_dir)``.

    Raises:
        KeyError: When the suite does not exist.
    """
    if name == "grounding":
        from .grounding import DEFAULT_DATASET_DIR, run_grounding_suite

        return run_grounding_suite, DEFAULT_DATASET_DIR
    if name == "scam":
        from .scam import DEFAULT_DATASET_DIR, run_scam_suite

        return run_scam_suite, DEFAULT_DATASET_DIR
    if name == "emscad":
        from .emscad import DEFAULT_DATASET_DIR, run_emscad_suite

        return run_emscad_suite, DEFAULT_DATASET_DIR
    if name == "dedupe":
        from .dedupe import DEFAULT_DATASET_DIR, run_dedupe_suite

        return run_dedupe_suite, DEFAULT_DATASET_DIR
    if name == "structured":
        from .structured import DEFAULT_DATASET_DIR, run_structured_suite

        return run_structured_suite, DEFAULT_DATASET_DIR
    if name == "writer":
        from .writer import DEFAULT_DATASET_DIR, run_writer_suite

        return run_writer_suite, DEFAULT_DATASET_DIR
    raise KeyError(f"unknown eval suite: {name}")
