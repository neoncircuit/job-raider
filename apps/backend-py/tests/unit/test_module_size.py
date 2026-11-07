"""
Job Raider - Module Size Guard

Large modules are hard to read and to review. This test keeps the modules
that were split in Step 5 under a line limit, so they do not grow back.
"""

from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
MAX_LINES = 600

# Modules that a split made smaller. A module that does not exist yet is
# skipped, so the list can name the modules of a split before it is applied.
LIMITED_MODULES = [
    "src/pipeline/stages.py",
    "src/pipeline/stage_base.py",
    "src/pipeline/stages_collect.py",
    "src/pipeline/stages_rank.py",
    "src/pipeline/stages_generate.py",
]


def count_lines(path: Path) -> int:
    """
    Count the lines of a text file.

    Args:
        path: File to count.

    Returns:
        The number of lines.
    """
    return len(path.read_text(encoding="utf-8").splitlines())


def test_split_modules_exist() -> None:
    """The stage modules exist, so the size checks below test real files."""
    missing = [m for m in LIMITED_MODULES if not (BACKEND_DIR / m).exists()]
    assert missing == []


@pytest.mark.parametrize("module", LIMITED_MODULES)
def test_module_stays_under_limit(module: str) -> None:
    """
    Each limited module has fewer than MAX_LINES lines.

    Args:
        module: Module path relative to apps/backend-py.
    """
    path = BACKEND_DIR / module
    if not path.exists():
        pytest.skip(f"{module} does not exist")
    assert count_lines(path) < MAX_LINES
