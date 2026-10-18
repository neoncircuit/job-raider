"""
Tests for the mypy baseline gate in ``scripts/mypy_gate.py``.

The gate must block new errors, allow known ones, ignore line numbers, and
count duplicates. These tests use canned mypy output, so they do not run
mypy.
"""

from collections import Counter
from pathlib import Path
from typing import Tuple

import pytest

from scripts import mypy_gate

KNOWN = 'src/a.py:10: error: "object" has no attribute "update"  [attr-defined]'
KNOWN_MOVED = 'src/a.py:42: error: "object" has no attribute "update"  [attr-defined]'
NEW = 'src/b.py:5: error: Incompatible return value type (got "int", expected "str")  [return-value]'


def test_normalize_drops_line_numbers_and_keeps_code() -> None:
    """The key holds file, code, and message, but not the line number."""
    assert mypy_gate.normalize(KNOWN) == mypy_gate.normalize(KNOWN_MOVED)
    assert mypy_gate.normalize(KNOWN) == (
        'src/a.py: [attr-defined] "object" has no attribute "update"'
    )


def test_normalize_masks_line_references_in_messages() -> None:
    """A "line N" inside a message does not change the key."""
    first = mypy_gate.normalize(
        'src/c.py:3: error: Name "x" already defined on line 1  [no-redef]'
    )
    second = mypy_gate.normalize(
        'src/c.py:9: error: Name "x" already defined on line 7  [no-redef]'
    )
    assert first == second == 'src/c.py: [no-redef] Name "x" already defined on line N'


@pytest.mark.parametrize(
    "line",
    [
        "src/a.py:10: note: See https://mypy.readthedocs.io",
        "Found 2 errors in 1 file (checked 3 source files)",
        "",
    ],
)
def test_normalize_ignores_non_error_lines(line: str) -> None:
    """Notes, summaries, and blank lines are not errors.

    Args:
        line: A mypy output line that is not an error.
    """
    assert mypy_gate.normalize(line) is None


def test_compare_reports_new_and_fixed_errors() -> None:
    """New errors and fixed baseline errors are both reported."""
    baseline = mypy_gate.parse_errors(KNOWN)
    current = mypy_gate.parse_errors("\n".join([KNOWN_MOVED, NEW]))

    new, fixed = mypy_gate.compare(current, baseline)

    assert list(new) == [mypy_gate.normalize(NEW)]
    assert not fixed


def test_a_second_copy_of_a_known_error_is_new() -> None:
    """Counts matter: one allowed error does not allow two."""
    baseline = mypy_gate.parse_errors(KNOWN)
    current = mypy_gate.parse_errors("\n".join([KNOWN, KNOWN_MOVED]))

    new, _fixed = mypy_gate.compare(current, baseline)

    assert sum(new.values()) == 1


def test_baseline_round_trip(tmp_path: Path) -> None:
    """write_baseline and load_baseline keep counts and skip the header.

    Args:
        tmp_path: Temporary directory.
    """
    errors = Counter({"src/a.py: [misc] x": 2, "src/b.py: [index] y": 1})
    path = tmp_path / "baseline.txt"

    mypy_gate.write_baseline(path, errors)

    assert mypy_gate.load_baseline(path) == errors
    assert path.read_text(encoding="utf-8").startswith("# mypy baseline")


def _gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output: str, code: int
) -> Path:
    """Point the gate at a temp baseline and a canned mypy result.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory for the baseline.
        output: Canned mypy stdout.
        code: Canned mypy exit code.

    Returns:
        Path of the temporary baseline file.
    """
    baseline = tmp_path / "mypy-baseline.txt"
    result: Tuple[int, str, str] = (code, output, "")
    monkeypatch.setattr(mypy_gate, "BASELINE_PATH", baseline)
    monkeypatch.setattr(mypy_gate, "run_mypy", lambda: result)
    return baseline


def test_main_passes_with_only_known_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Known errors at new line numbers pass the gate.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory.
    """
    baseline = _gate(monkeypatch, tmp_path, KNOWN_MOVED, 1)
    mypy_gate.write_baseline(baseline, mypy_gate.parse_errors(KNOWN))

    assert mypy_gate.main([]) == 0


def test_main_fails_on_a_new_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A new error fails the gate with exit code 1.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory.
    """
    baseline = _gate(monkeypatch, tmp_path, "\n".join([KNOWN, NEW]), 1)
    mypy_gate.write_baseline(baseline, mypy_gate.parse_errors(KNOWN))

    assert mypy_gate.main([]) == 1


def test_main_fails_when_mypy_crashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A mypy crash (exit code 2) fails the gate.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory.
    """
    _gate(monkeypatch, tmp_path, "", 2)

    assert mypy_gate.main([]) == 2


def test_update_writes_the_current_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """--update replaces the baseline with the current errors.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory.
    """
    baseline = _gate(monkeypatch, tmp_path, "\n".join([KNOWN, NEW]), 1)

    assert mypy_gate.main(["--update"]) == 0
    assert mypy_gate.load_baseline(baseline) == mypy_gate.parse_errors(
        "\n".join([KNOWN, NEW])
    )
