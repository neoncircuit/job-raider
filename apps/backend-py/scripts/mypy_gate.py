"""
Job Raider - mypy baseline gate.

Run mypy on ``src/`` and fail when it reports an error that is not in
``mypy-baseline.txt``. Errors that are already in the baseline are allowed,
so CI can block new type errors while the old ones are fixed over time.

The gate compares errors by file, error code, and message. It ignores line
numbers, so a change to unrelated lines does not break the gate. It counts
errors, so a second copy of a known error is still a new error.

Usage (from ``apps/backend-py``):

    python scripts/mypy_gate.py            # check against the baseline
    python scripts/mypy_gate.py --update   # write a new baseline

Run ``--update`` after you fix baseline errors, so that the baseline only
gets smaller. Do not use ``--update`` to accept a new error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
BASELINE_PATH = BACKEND_DIR / "mypy-baseline.txt"
MYPY_TARGETS = ["src/"]

BASELINE_HEADER = (
    "# mypy baseline: known errors in src/ that the gate allows.\n"
    "# One normalized error per line: <file>: [<code>] <message>\n"
    "# Regenerate with `python scripts/mypy_gate.py --update` only after\n"
    "# fixing errors. Do not add new errors to this file.\n"
)

ERROR_LINE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+)(?::\d+)?: error: (?P<message>.*?)"
    r"(?:\s+\[(?P<code>[a-z0-9-]+)\])?$"
)
LINE_REFERENCE = re.compile(r"\bline \d+\b")


def normalize(line: str) -> Optional[str]:
    """Turn one mypy output line into a baseline key.

    Args:
        line: One line of mypy output.

    Returns:
        ``"<file>: [<code>] <message>"`` for an error line, with line numbers
        removed from the message, or ``None`` for any other line.
    """
    match = ERROR_LINE.match(line.strip())
    if not match:
        return None
    path = match.group("path").replace("\\", "/")
    message = LINE_REFERENCE.sub("line N", match.group("message"))
    code = match.group("code") or "misc"
    return f"{path}: [{code}] {message}"


def parse_errors(output: str) -> Counter[str]:
    """Count the normalized errors in mypy output.

    Args:
        output: Full mypy stdout.

    Returns:
        Count of each normalized error.
    """
    keys = (normalize(line) for line in output.splitlines())
    return Counter(key for key in keys if key is not None)


def load_baseline(path: Path) -> Counter[str]:
    """Read the baseline file.

    Args:
        path: Baseline file path.

    Returns:
        Count of each baseline error. Empty when the file does not exist.
    """
    if not path.exists():
        return Counter()
    lines = path.read_text(encoding="utf-8").splitlines()
    return Counter(line for line in lines if line.strip() and not line.startswith("#"))


def write_baseline(path: Path, errors: Counter[str]) -> None:
    """Write errors to the baseline file in sorted order.

    Args:
        path: Baseline file path.
        errors: Count of each normalized error.
    """
    lines = sorted(errors.elements())
    path.write_text(
        BASELINE_HEADER + "".join(f"{line}\n" for line in lines),
        encoding="utf-8",
        newline="\n",
    )


def compare(
    current: Counter[str], baseline: Counter[str]
) -> Tuple[Counter[str], Counter[str]]:
    """Find new errors and fixed baseline errors.

    Args:
        current: Errors from this mypy run.
        baseline: Errors in the baseline.

    Returns:
        Tuple of (new errors, fixed baseline errors).
    """
    return current - baseline, baseline - current


def run_mypy() -> Tuple[int, str, str]:
    """Run mypy on the gate targets with the project configuration.

    Returns:
        Tuple of (exit code, stdout, stderr).
    """
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", *MYPY_TARGETS],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Check mypy output against the baseline, or rewrite the baseline.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        0 when there are no new errors, 1 when there are new errors, and 2
        when mypy itself fails to run.
    """
    parser = argparse.ArgumentParser(description="mypy baseline gate")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Write the current errors to the baseline file",
    )
    args = parser.parse_args(argv)

    code, stdout, stderr = run_mypy()
    if code not in (0, 1):
        print(stdout + stderr, file=sys.stderr)
        print(f"mypy failed to run (exit code {code}).", file=sys.stderr)
        return 2

    current = parse_errors(stdout)

    if args.update:
        write_baseline(BASELINE_PATH, current)
        print(f"Wrote {sum(current.values())} errors to {BASELINE_PATH.name}.")
        return 0

    new, fixed = compare(current, load_baseline(BASELINE_PATH))

    if fixed:
        print(
            f"{sum(fixed.values())} baseline errors are fixed. Run "
            "`python scripts/mypy_gate.py --update` to remove them."
        )

    if new:
        lines: List[str] = sorted(new.elements())
        print(f"mypy found {len(lines)} new errors that are not in the baseline:")
        for line in lines:
            print(f"  {line}")
        print("Fix them. Do not add them to the baseline.")
        return 1

    print(f"mypy gate passed: {sum(current.values())} known errors, 0 new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
