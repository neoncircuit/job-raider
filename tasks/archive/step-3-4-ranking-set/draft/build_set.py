"""Build the Step 3.4 ranking set files and the label review sheet from the draft data.

Run with the backend Python, so the profiles and jobs are validated against
the app models (WSL, from the repository root):

    apps/backend-py/.venv/bin/python tasks/active/step-3-4-ranking-set/draft/build_set.py
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

DRAFT = Path(__file__).resolve().parent
ROOT = DRAFT.parents[3]
sys.path.insert(0, str(DRAFT))
sys.path.insert(0, str(ROOT / "apps" / "backend-py"))

from jobs_backend import JOBS_BACKEND  # noqa: E402
from jobs_ml import JOBS_ML  # noqa: E402
from profiles import MODES, PROFILES  # noqa: E402

from src.models.job_listing import JobListing  # noqa: E402
from src.models.user_profile import UserProfile  # noqa: E402

OUT = DRAFT / "out"
REVIEW = DRAFT.parent / "label-review.md"
LEVEL_SHORT = {
    "Internship": "Intern",
    "Entry Level": "Entry",
    "Mid Level": "Mid",
    "Senior": "Senior",
    "Lead": "Lead",
    "Principal": "Principal",
}


def main() -> None:
    """
    Validate the draft data and write the set files and the review sheet.
    """
    jobs: List[Dict[str, Any]] = JOBS_ML + JOBS_BACKEND
    ids = [j["job_id"] for j in jobs]
    assert len(ids) == len(set(ids)), "duplicate job IDs"
    for pid, data in PROFILES.items():
        UserProfile.model_validate(data)
        assert pid in MODES, pid
    rows: List[str] = []
    labels: List[Dict[str, Any]] = []
    for item in jobs:
        data = {k: v for k, v in item.items() if k != "labels"}
        JobListing.model_validate(data)
        rows.append(json.dumps(data, ensure_ascii=False))
        assert set(item["labels"]) == set(PROFILES), item["job_id"]
        for pid in PROFILES:
            label, reason = item["labels"][pid]
            assert label in (0, 1, 2), (item["job_id"], pid)
            labels.append(
                {"profile_id": pid, "job_id": item["job_id"], "label": label, "reason": reason}
            )
    OUT.mkdir(exist_ok=True)
    (OUT / "profiles.json").write_text(
        json.dumps(PROFILES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT / "modes.json").write_text(json.dumps(MODES, indent=2) + "\n", encoding="utf-8")
    (OUT / "jobs.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (OUT / "labels.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in labels) + "\n",
        encoding="utf-8",
    )
    write_review(jobs)
    for pid in PROFILES:
        counts = Counter(r["label"] for r in labels if r["profile_id"] == pid)
        print(pid, dict(sorted(counts.items())))
    print(len(jobs), "jobs,", len(labels), "labels")


def write_review(jobs: List[Dict[str, Any]]) -> None:
    """
    Write the label review sheet: one table for each profile.

    Args:
        jobs: The jobs with their draft labels.
    """
    lines = [
        "# Step 3.4 Ranking Set: Draft Labels to Check",
        "",
        "Claude drafted every label with `draft/README.md` before any ranker ran. "
        "Check each row. To change a label, write the new label and a short reason "
        "in the last column (or tell Claude the job number and the label). "
        "Labels: 2 = apply, 1 = maybe, 0 = not relevant.",
        "",
        "The job texts are in `draft/jobs_ml.py` (rk-001 to rk-035) and "
        "`draft/jobs_backend.py` (rk-036 to rk-070).",
        "",
    ]
    names = {
        "fresh_ml": "Profile fresh_ml (Rina Tan): fresh graduate, targets ML engineer, "
        "data scientist, AI; entry level; Python, PyTorch, scikit-learn, Pandas, SQL, "
        "FastAPI, LangChain, Transformers, Docker",
        "mid_backend": "Profile mid_backend (Daniel Ong): 4.4 years, targets backend "
        "engineer, platform engineer, Java; mid level; Java, Spring Boot, Go, "
        "PostgreSQL, Redis, Kafka, Docker, Kubernetes, AWS, gRPC",
    }
    for pid in PROFILES:
        lines += [f"## {names[pid]}", ""]
        lines += [
            "| Job | Title | Level | Company | Draft | Reason | Your label and reason |",
            "|-----|-------|-------|---------|-------|--------|------------------------|",
        ]
        for item in jobs:
            label, reason = item["labels"][pid]
            lines.append(
                f"| {item['job_id']} | {item['title']} | "
                f"{LEVEL_SHORT.get(item['experience_level'], item['experience_level'])} | "
                f"{item['company']} | {label} | {reason} | |"
            )
        lines.append("")
    REVIEW.write_text("\n".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
