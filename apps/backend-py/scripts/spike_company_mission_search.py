#!/usr/bin/env python3
"""
Job Raider - Phase B company-mission search spike

Runs resolve_company_mission against fixture companies and writes a JSON
artifact for human review.

Usage (from apps/backend-py, with .venv active):

    python scripts/spike_company_mission_search.py
    python scripts/spike_company_mission_search.py --only summit_soft_skip_probe

Author: Job Raider
Date: 2026-08-20
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running as ``python scripts/spike_company_mission_search.py`` from backend root.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.generation.company_mission_search import (  # noqa: E402
    resolve_company_mission,
    resolve_ollama_host,
)


def _default_fixtures_path() -> Path:
    """
    Return the default spike fixtures path.

    Returns:
        Path to ``scripts/fixtures/company_mission_spike.json``.
    """
    return Path(__file__).resolve().parent / "fixtures" / "company_mission_spike.json"


def _default_output_path() -> Path:
    """
    Return the default JSON output path under scripts/output.

    Returns:
        Timestamped path under ``scripts/output/``.
    """
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return out_dir / f"company_mission_spike_{stamp}.json"


def load_fixtures(path: Path) -> List[Dict[str, Any]]:
    """
    Load spike cases from a JSON fixture file.

    Args:
        path: Path to fixtures JSON.

    Returns:
        List of case dicts.

    Raises:
        ValueError: If the file has no cases.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"No cases found in fixtures: {path}")
    return cases


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve mission for one fixture case.

    Args:
        case: Fixture case dict.

    Returns:
        Structured result dict for the spike report.
    """
    company = str(case.get("company") or "").strip()
    jd_text = str(case.get("jd_text") or "")
    jd_facts = case.get("jd_facts") or []
    expected_mode = str(case.get("expected_mode") or "")
    case_id = str(case.get("id") or company)

    resolved = resolve_company_mission(
        company,
        jd_text=jd_text,
        jd_facts=jd_facts,
        enabled=True,
    )
    return {
        "id": case_id,
        "company": company,
        "expected_mode": expected_mode,
        "query": resolved.query,
        "verify": resolved.verify,
        "paraphrase": {
            "method": resolved.paraphrase_method,
            "brief": resolved.brief,
        },
        "status": resolved.status,
        "skip_reason": resolved.skip_reason,
        "source_url": resolved.source_url,
        "elapsed_ms": resolved.elapsed_ms,
        "mission_context": resolved.to_mission_context(),
    }


def print_case_report(result: Dict[str, Any]) -> None:
    """
    Print a human-readable case summary to stdout.

    Args:
        result: Case result from ``run_case``.
    """
    status = result.get("status")
    print("=" * 72)
    print(f"CASE: {result['id']} | {result['company']}")
    print(f"expected_mode: {result['expected_mode']}")
    print(f"query: {result.get('query')}")
    print(f"status: {status}")
    if status != "pass":
        print(f"skip_reason: {result.get('skip_reason')}")
    else:
        print(f"source_url: {result.get('source_url')}")
        brief = (result.get("paraphrase") or {}).get("brief") or ""
        method = (result.get("paraphrase") or {}).get("method")
        print(f"paraphrase ({method}): {brief}")
    print(f"elapsed_ms: {result['elapsed_ms']}")


def main(argv: Optional[List[str]] = None) -> int:
    """
    CLI entrypoint for the company-mission spike.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on completion; 2 on fixture failure).
    """
    parser = argparse.ArgumentParser(description="Phase B company-mission search spike")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=_default_fixtures_path(),
        help="Path to spike fixtures JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for JSON report (default: scripts/output/…)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only case id(s); repeatable",
    )
    args = parser.parse_args(argv)

    fixtures_path = args.fixtures
    if not fixtures_path.is_file():
        print(f"Fixtures not found: {fixtures_path}", file=sys.stderr)
        return 2

    cases = load_fixtures(fixtures_path)
    if args.only:
        wanted = set(args.only)
        cases = [c for c in cases if str(c.get("id") or "") in wanted]
        if not cases:
            print(f"No fixtures matched --only {sorted(wanted)}", file=sys.stderr)
            return 2

    results: List[Dict[str, Any]] = []
    for case in cases:
        print(f"\nRunning {case.get('id') or case.get('company')} …")
        result = run_case(case)
        print_case_report(result)
        results.append(result)

    output_path = args.output or _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixtures": str(fixtures_path),
        "ollama_host": resolve_ollama_host(),
        "results": results,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("\n" + "=" * 72)
    print(f"Wrote spike report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
