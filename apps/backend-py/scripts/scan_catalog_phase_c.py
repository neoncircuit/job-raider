"""Scan catalog listings for Phase C instruction detections on real JDs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.generation.cover_letter_instructions import detect_application_instructions


def main() -> None:
    """
    Print real catalog JDs that match Phase C detection or near-phrase heuristics.

    Returns:
        None.
    """
    catalog = _BACKEND_ROOT / "data" / "listings" / "catalog.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    listings: list = []
    if isinstance(data, list):
        listings = data
    elif isinstance(data, dict):
        raw = data.get("listings")
        if isinstance(raw, dict):
            listings = list(raw.values())
        elif isinstance(raw, list):
            listings = raw
        else:
            for value in data.values():
                if isinstance(value, dict):
                    sample = next(iter(value.values()), None)
                    if isinstance(sample, dict) and "description" in sample:
                        listings = list(value.values())
                        break
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    listings = value
                    break

    print(f"listings={len(listings)}")
    hits = []
    near = []
    for item in listings:
        if not isinstance(item, dict):
            continue
        desc = item.get("description") or ""
        company = item.get("company") or item.get("company_name") or "?"
        title = item.get("title") or "?"
        job_id = item.get("job_id") or item.get("id") or "?"
        det = detect_application_instructions(desc)
        if det.has_why_interest or det.has_inclusions:
            hits.append(
                {
                    "job_id": job_id,
                    "company": company,
                    "title": title,
                    "detected": det.to_dict(),
                    "snippet": desc[:500],
                }
            )
        low = desc.lower()
        needles = (
            "why this",
            "why our",
            "excites you",
            "interests you",
            "cover letter",
            "include a link",
            "include your github",
            "2 sentences",
            "50 words",
            "few lines",
            "in a few",
            "short paragraph",
        )
        if any(p in low for p in needles):
            near.append(
                {
                    "job_id": job_id,
                    "company": company,
                    "title": title,
                    "detected": det.to_dict()
                    if (det.has_why_interest or det.has_inclusions)
                    else None,
                }
            )

    print(f"DETECTED={len(hits)}")
    for hit in hits[:20]:
        print("--- DETECTED ---")
        print(json.dumps(hit, indent=2)[:2000])
    print(f"NEAR_PHRASE={len(near)}")
    for item in near[:30]:
        print(json.dumps(item))


if __name__ == "__main__":
    main()
