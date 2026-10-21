"""
Offline evaluation suites, by name (Step 3.1).

Each suite loads a labeled dataset folder and returns an ``EvalReport``.
Suites are imported only when they run, so ``main.py --help`` stays fast.
Steps 3.3 to 3.8 add ``scam``, ``dedupe``, ``ranking``, and ``compare``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Tuple

from ..report import EvalReport

SuiteRunner = Callable[[Path], EvalReport]

SUITE_NAMES: Tuple[str, ...] = ("grounding",)


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
    raise KeyError(f"unknown eval suite: {name}")
