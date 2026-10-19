"""
Fail if production ``src/`` constructs ``LLMRouter(`` outside the factory.

Call sites must use ``create_router()`` so Settings (host, models, fallback)
apply everywhere.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

# Files that may construct LLMRouter directly (the factory and this package).
ALLOWED_FILES = frozenset(
    {
        "llm/router.py",
    }
)


def _bare_llm_router_calls(path: Path) -> List[Tuple[int, str]]:
    """
    Find ``LLMRouter(`` call sites in a Python file.

    Args:
        path: Path to a ``.py`` file under ``src/``.

    Returns:
        List of (line_number, source_line) for each bare construction.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: List[Tuple[int, str]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name) and func.id == "LLMRouter":
            name = "LLMRouter"
        elif isinstance(func, ast.Attribute) and func.attr == "LLMRouter":
            name = "LLMRouter"
        if name != "LLMRouter":
            continue
        line_no = getattr(node, "lineno", 0)
        line = lines[line_no - 1].strip() if 0 < line_no <= len(lines) else ""
        # Allow class definition context is not a Call; only Call nodes reach here.
        hits.append((line_no, line))
    return hits


def test_no_bare_llm_router_outside_factory() -> None:
    """Production modules must not construct LLMRouter directly."""
    offenders: List[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(SRC_ROOT).as_posix()
        if rel in ALLOWED_FILES:
            continue
        if "/tests/" in rel or rel.startswith("tests/"):
            continue
        for line_no, line in _bare_llm_router_calls(path):
            offenders.append(f"{rel}:{line_no}: {line}")
    assert (
        not offenders
    ), "Bare LLMRouter() found; use create_router() instead:\n" + "\n".join(offenders)
