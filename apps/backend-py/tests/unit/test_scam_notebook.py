"""
Checks that the scam evaluation notebook calls the CLI and stores no output.

The evaluation logic lives in ``src/evaluation/suites/emscad.py``. The
notebook must not download the CSV, load secrets, run the detector itself,
or mention the held-out part in a code cell.
"""

from __future__ import annotations

import json

from src.evaluation.run_metadata import BACKEND_DIR

NOTEBOOK_PATH = BACKEND_DIR / "notebooks" / "scam_detector_evaluation.ipynb"

_FORBIDDEN = (
    "heldout",
    "load_dotenv",
    ".env",
    "kaggle datasets download",
    "JobScamDetector(",
)

_REQUIRED = ("main.py", "eval", "emscad", "--part", "tuning")


def _code_cells() -> list[str]:
    """
    Return the source of each code cell.

    Returns:
        Code-cell sources in notebook order.
    """
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    sources: list[str] = []
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        sources.append(source)
    return sources


def test_notebook_has_no_outputs_or_execution_counts() -> None:
    """Committed code cells have no output and a null execution count."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        assert cell.get("outputs") in (None, []), f"cell {index} has outputs"
        assert (
            cell.get("execution_count") is None
        ), f"cell {index} has an execution count"


def test_notebook_does_not_contain_forbidden_strings() -> None:
    """Code cells do not load secrets, download data, or run the detector."""
    for index, source in enumerate(_code_cells()):
        for token in _FORBIDDEN:
            assert token not in source, f"cell {index} contains {token!r}"


def test_notebook_runs_the_tuning_cli() -> None:
    """At least one code cell runs the EMSCAD tuning command."""
    joined = "\n".join(_code_cells())
    missing = [token for token in _REQUIRED if token not in joined]
    assert not missing, f"notebook is missing {missing}"
