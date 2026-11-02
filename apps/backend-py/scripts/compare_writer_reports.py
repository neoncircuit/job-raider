#!/usr/bin/env python3
"""
Job Raider - Paired comparison of two writer reports (CLI)

Thin command-line wrapper over ``src.evaluation.writer_compare``. It reads two
JSON reports of ``eval writer`` (the baseline first) and prints the decision
rule's values. It does not change the default writer.

Usage (from apps/backend-py with .venv active):

```bash
python scripts/compare_writer_reports.py data/eval/writer/baseline.json data/eval/writer/other.json
python scripts/compare_writer_reports.py baseline.json other.json --rounds 500 --seed 1
```

Author: Job Raider
Date: 2026-11-02
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

# Allow ``from src...`` when run as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.evaluation.writer_compare import (  # noqa: E402
    DEFAULT_ROUNDS,
    DEFAULT_SEED,
    compare_reports,
    load_writer_report,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Compare two writer reports and print the result.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        Exit code: 0 when the comparison ran, 1 when a report could not be read
        or compared.
    """
    parser = argparse.ArgumentParser(
        description="Compare a writer report with the baseline, pair by pair."
    )
    parser.add_argument("baseline", help="Baseline writer report (JSON)")
    parser.add_argument("other", help="Other writer report of the same dataset (JSON)")
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_ROUNDS,
        help=f"Bootstrap resamples (default: {DEFAULT_ROUNDS})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Bootstrap seed (default: {DEFAULT_SEED})",
    )
    args = parser.parse_args(argv)
    try:
        result = compare_reports(
            load_writer_report(Path(args.baseline)),
            load_writer_report(Path(args.other)),
            rounds=args.rounds,
            seed=args.seed,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"Cannot compare the reports: {exc}")
        return 1
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
