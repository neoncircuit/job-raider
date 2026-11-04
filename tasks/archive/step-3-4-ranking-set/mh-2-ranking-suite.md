# MH-2: Ranking eval suite with the heuristic matcher and BM25

## Apply with the runner

The handoff runner applies this file: it writes the test file, runs the red command (it must fail), adds the suite and the edits, runs the "Done when" checks (they must pass), and commits. See `docs/handoff-runner.md`.

Apply this handoff (WSL, from `apps/backend-py`):

```bash
.venv/bin/python scripts/run_handoff.py ../../tasks/active/step-3-4-ranking-set/mh-2-ranking-suite.md
```

## Why

MH-1 added the ranking set. This handoff adds the `ranking` suite that scores two deterministic methods on it, so the baseline and the runs after the R4 and R5 fixes use one command:

```mermaid
flowchart LR
    S[Ranking set:<br/>2 profiles, 70 jobs,<br/>140 labels] --> H[heuristic:<br/>JobMatcher with the<br/>profile's mode]
    S --> B[bm25: RAG chunks,<br/>RAG ranker's profile query,<br/>best chunk per job]
    H --> M[NDCG@10 and recall@10<br/>for each profile and mean]
    B --> M
```

- `heuristic`: `JobMatcher.score_job` with the profile's `fresh_grad_mode` from `modes.json`, as in the pipeline's scoring stage.
- `bm25`: the job chunks of the RAG chunker (`config/rag_config.yaml`), BM25 with the RAG ranker's own profile query (`RAGRanker._build_profile_query_text`), and each job's best chunk score. The current code has no BM25-only mode; this one measures the BM25 half of the hybrid ranker, with its query.
- NDCG@10 uses the label (0, 1, 2) as the gain; recall@10 is the share of the jobs labeled 2 in the top 10. Ties are broken by job ID, so the numbers are the same on every run (they can run in CI).
- MH-3 adds the dense and hybrid methods (local; they need the embedding model).

## Files

- `apps/backend-py/src/evaluation/suites/ranking.py` (new)
- `apps/backend-py/tests/unit/test_ranking_suite.py` (new)
- `apps/backend-py/src/evaluation/suites/__init__.py` (change: the registry)
- `apps/backend-py/main.py` (change: one example in the `eval` help)
- `apps/backend-py/tests/unit/test_scam_suite.py` (change: the pinned suite names)

## Step 1: add the test file, run it, and see it fail

```python new=apps/backend-py/tests/unit/test_ranking_suite.py
"""Tests for the ranking eval suite (Step 3.4, MH-2)."""

import shutil
from pathlib import Path
from typing import Any, Dict, List

import pytest

import src.evaluation.suites.ranking as ranking
from src.evaluation.suites import SUITE_NAMES, get_suite
from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile

LABELS: Dict[str, int] = {"c": 0, "a": 2, "b": 1}


def profile_with(skills: List[str]) -> UserProfile:
    """
    A small profile with the given skills.

    Args:
        skills: Skill names.

    Returns:
        The profile.
    """
    return UserProfile.model_validate(
        {
            "name": "Test Person",
            "contact": {"email": "test@example.com", "location": "Singapore"},
            "skills": [{"name": name} for name in skills],
        }
    )


def job_with(job_id: str, title: str, description: str) -> JobListing:
    """
    A small job.

    Args:
        job_id: The job ID.
        title: The title.
        description: The description.

    Returns:
        The job.
    """
    return JobListing.model_validate(
        {
            "job_id": job_id,
            "title": title,
            "company": "Test Co",
            "source": "other",
            "description": description,
        }
    )


def test_ndcg_of_the_best_order_is_one() -> None:
    """The best order has NDCG 1, even when the labels are not in order."""
    assert ranking.ndcg_at_k(["a", "b", "c"], LABELS) == 1.0


def test_ndcg_of_the_reverse_order() -> None:
    """The reverse order gives DCG 1/log2(3) + 2/log2(4) over 2 + 1/log2(3)."""
    assert ranking.ndcg_at_k(["c", "b", "a"], LABELS) == pytest.approx(0.6199, abs=1e-4)


def test_ndcg_counts_only_the_top_k() -> None:
    """Jobs below the cut-off do not count."""
    assert ranking.ndcg_at_k(["c", "a", "b"], LABELS, k=1) == 0.0


def test_ndcg_without_a_relevant_job_is_none() -> None:
    """With no label above 0 there is no NDCG."""
    assert ranking.ndcg_at_k(["a", "b"], {"a": 0, "b": 0}) is None


def test_recall_counts_apply_labels_in_the_top_k() -> None:
    """Recall is the share of jobs labeled 2 in the top k; label 1 does not count."""
    labels = {"a": 2, "b": 1, "c": 2, "d": 0}

    assert ranking.recall_at_k(["a", "b", "d", "c"], labels, k=2) == 0.5
    assert ranking.recall_at_k(["b", "d"], {"b": 1, "d": 0}) is None


def test_ties_are_broken_by_job_id() -> None:
    """Equal scores are ordered by job ID."""
    assert ranking.sort_scores({"rk-002": 1.0, "rk-001": 1.0, "rk-003": 2.0}) == [
        ("rk-003", 2.0),
        ("rk-001", 1.0),
        ("rk-002", 1.0),
    ]


def test_heuristic_uses_the_profile_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each profile is scored with its own matcher mode."""
    seen: List[bool] = []
    real = ranking.JobMatcher

    def make(fresh_grad_mode: bool = False, **kwargs: Any) -> Any:
        """Record the mode and make a real matcher."""
        seen.append(fresh_grad_mode)
        return real(fresh_grad_mode=fresh_grad_mode, **kwargs)

    monkeypatch.setattr(ranking, "JobMatcher", make)

    ranking.run_ranking_suite(methods=["heuristic"])

    assert sorted(seen) == [False, True]


def test_bm25_uses_the_ranker_profile_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """BM25 searches with the RAG ranker's profile query."""
    monkeypatch.setattr(
        ranking.RAGRanker, "_build_profile_query_text", lambda self, profile: "zebra"
    )
    jobs = [
        job_with("j1", "Analyst", "Reports and dashboards for the sales team."),
        job_with("j2", "Keeper", "Care for the zebra herd and its enclosure."),
        job_with("j3", "Clerk", "File records and answer the phone."),
    ]

    result = ranking.bm25_ranking(profile_with(["Python"]), {}, jobs)

    assert result[0][0] == "j2"


def test_bm25_scores_a_job_by_its_best_chunk() -> None:
    """A job's short title chunk decides, not its weaker long-text chunk."""
    filler = " ".join(["Build reliable services for our customers."] * 40)
    jobs = [
        job_with("j1", "Kafka Engineer", filler),
        job_with("j2", "Backend Engineer", filler + " Kafka work with Kafka Streams."),
    ] + [
        job_with(f"f{n}", "Clerk", "File records and answer the phone.")
        for n in range(8)
    ]

    result = ranking.bm25_ranking(profile_with(["Kafka"]), {}, jobs)

    assert [job_id for job_id, _ in result[:2]] == ["j1", "j2"]


def test_suite_reports_each_method_and_profile() -> None:
    """The report has NDCG and recall for each method, each profile, and the mean."""
    report = ranking.run_ranking_suite()

    for method in ("heuristic", "bm25"):
        for pid in ("fresh_ml", "mid_backend"):
            for metric in ("ndcg_at_10", "recall_at_10"):
                value = report.metrics[f"{method}_{pid}_{metric}"]
                assert value is not None and 0.0 <= value <= 1.0
        mean = report.metrics[f"{method}_ndcg_at_10"]
        per_profile = [
            report.metrics[f"{method}_{pid}_ndcg_at_10"]
            for pid in ("fresh_ml", "mid_backend")
        ]
        assert mean == pytest.approx(sum(per_profile) / 2, abs=1e-4)
        assert len(report.details["top"][method]["fresh_ml"]) == 10
    assert report.suite == "ranking"
    assert report.metadata.case_count == 140


def test_suite_is_deterministic() -> None:
    """Two runs give the same metrics."""
    assert ranking.run_ranking_suite().metrics == ranking.run_ranking_suite().metrics


def test_unknown_method_is_refused() -> None:
    """Only known methods can run."""
    with pytest.raises(ValueError, match="unknown ranking methods"):
        ranking.run_ranking_suite(methods=["magic"])


def test_a_missing_label_is_refused(tmp_path: Path) -> None:
    """Every profile and job pair needs a label."""
    for path in ranking.DEFAULT_DATASET_DIR.iterdir():
        shutil.copy(path, tmp_path / path.name)
    labels = (tmp_path / "labels.jsonl").read_text(encoding="utf-8").splitlines()
    (tmp_path / "labels.jsonl").write_text(
        "\n".join(labels[:-1]) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="labels do not cover every job"):
        ranking.load_ranking_set(tmp_path)


def test_ranking_is_a_registered_suite() -> None:
    """The registry gives the ranking suite and its set."""
    runner, dataset_dir = get_suite("ranking")

    assert "ranking" in SUITE_NAMES
    assert runner is ranking.run_ranking_suite
    assert dataset_dir == ranking.DEFAULT_DATASET_DIR
```

Run it. It must fail (the suite does not exist yet):

```bash red cwd=apps/backend-py
.venv/bin/python -m pytest tests/unit/test_ranking_suite.py -q
```

## Step 2: add the suite

```python new=apps/backend-py/src/evaluation/suites/ranking.py
"""
Ranking suite: how well each method ranks the jobs of the ranking set (Step 3.4).

The set (``tests/fixtures/eval/ranking``) has synthetic profiles, constructed
jobs, and one label for each profile and job: 2 (apply), 1 (maybe), or 0
(not relevant). Each method ranks every job for each profile. The report
gives NDCG@10 (the gain of a job is its label) and recall@10 (the share of
the jobs labeled 2 in the top 10), for each profile and as the mean over the
profiles.

Methods:

- ``heuristic``: ``JobMatcher.score_job`` with the profile's matcher mode
  (``modes.json``), as in the pipeline's scoring stage.
- ``bm25``: BM25 over the job chunks of the RAG chunker, with the RAG
  ranker's profile query. A job's score is its best chunk score.

Both methods are deterministic and run in CI. Ties are broken by job ID, so
a ranking is the same on every run.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from ...models.job_listing import JobListing
from ...models.user_profile import UserProfile
from ...rag.bm25_retriever import BM25Retriever
from ...rag.chunker import TextChunker
from ...rag.config import RAGConfig
from ...rag.ranker import RAGRanker
from ...scoring.matcher import JobMatcher
from ..datasets import load_jsonl
from ..report import EvalReport
from ..run_metadata import BACKEND_DIR, build_run_metadata

SUITE = "ranking"
DEFAULT_DATASET_DIR = BACKEND_DIR / "tests" / "fixtures" / "eval" / "ranking"
RAG_CONFIG_PATH = BACKEND_DIR / "config" / "rag_config.yaml"
TOP_K = 10
CI_METHODS: Tuple[str, ...] = ("heuristic", "bm25")

Ranking = List[Tuple[str, float]]
"""Job ID and score, best first."""
Ranker = Callable[[UserProfile, Dict[str, bool], List[JobListing]], Ranking]


class RankingLabel(BaseModel):
    """One label of the set: how useful a job is for a profile."""

    profile_id: str
    job_id: str
    label: int = Field(ge=0, le=2)
    reason: str


@dataclass
class RankingSet:
    """The loaded ranking set."""

    profiles: Dict[str, UserProfile]
    modes: Dict[str, Dict[str, bool]]
    jobs: List[JobListing]
    labels: Dict[str, Dict[str, int]]
    files: List[Path]


def load_ranking_set(dataset_dir: Path = DEFAULT_DATASET_DIR) -> RankingSet:
    """
    Load and check the ranking set.

    Args:
        dataset_dir: The set folder.

    Returns:
        The profiles, the matcher modes, the jobs, and profile ID to job ID
        to label.

    Raises:
        ValueError: When a profile has no mode, or a profile and job pair has
            no label or more than one.
    """
    dataset_dir = Path(dataset_dir)
    files = [
        dataset_dir / name
        for name in ("profiles.json", "modes.json", "jobs.jsonl", "labels.jsonl")
    ]
    raw_profiles = json.loads(files[0].read_text(encoding="utf-8"))
    profiles = {
        pid: UserProfile.model_validate(data) for pid, data in raw_profiles.items()
    }
    modes: Dict[str, Dict[str, bool]] = json.loads(files[1].read_text(encoding="utf-8"))
    missing_modes = sorted(set(profiles) - set(modes))
    if missing_modes:
        raise ValueError(f"profiles without a matcher mode: {missing_modes}")
    jobs = load_jsonl(files[2], JobListing)
    labels: Dict[str, Dict[str, int]] = {pid: {} for pid in profiles}
    for row in load_jsonl(files[3], RankingLabel):
        if row.profile_id not in labels or row.job_id in labels[row.profile_id]:
            raise ValueError(
                f"unknown or repeated label: {row.profile_id} {row.job_id}"
            )
        labels[row.profile_id][row.job_id] = row.label
    job_ids = {job.job_id for job in jobs}
    for pid, by_job in labels.items():
        if set(by_job) != job_ids:
            raise ValueError(f"profile {pid}: labels do not cover every job exactly")
    return RankingSet(
        profiles=profiles, modes=modes, jobs=jobs, labels=labels, files=files
    )


def sort_scores(scores: Dict[str, float]) -> Ranking:
    """
    Order job scores best first, with ties broken by job ID.

    Args:
        scores: Job ID to score.

    Returns:
        The ranking.
    """
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def heuristic_ranking(
    profile: UserProfile, mode: Dict[str, bool], jobs: List[JobListing]
) -> Ranking:
    """
    Rank jobs with the heuristic matcher, as the pipeline's scoring stage does.

    Args:
        profile: The profile.
        mode: The profile's matcher settings (``fresh_grad_mode``).
        jobs: The jobs.

    Returns:
        The ranking by total score.
    """
    matcher = JobMatcher(fresh_grad_mode=bool(mode.get("fresh_grad_mode", False)))
    return sort_scores(
        {job.job_id: float(matcher.score_job(job, profile).total_score) for job in jobs}
    )


def profile_query(profile: UserProfile) -> str:
    """
    The RAG ranker's BM25 query for a profile.

    Args:
        profile: The profile.

    Returns:
        The query text of ``RAGRanker._build_profile_query_text``.
    """
    ranker = RAGRanker.__new__(RAGRanker)  # The query builder reads no ranker state.
    return ranker._build_profile_query_text(profile)


def bm25_ranking(
    profile: UserProfile,
    mode: Dict[str, bool],
    jobs: List[JobListing],
    config: Optional[RAGConfig] = None,
) -> Ranking:
    """
    Rank jobs by BM25 over their chunks, with the RAG ranker's profile query.

    Args:
        profile: The profile.
        mode: The profile's matcher settings (not used by BM25).
        jobs: The jobs.
        config: The RAG configuration (default: ``config/rag_config.yaml``).

    Returns:
        The ranking by each job's best chunk score.
    """
    config = config or RAGConfig.from_yaml(str(RAG_CONFIG_PATH))
    chunker = TextChunker(config.chunking.get("job_description"))
    retriever = BM25Retriever()
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, str]] = []
    for job in jobs:
        for chunk in chunker.chunk_job(job):
            ids.append(f"{job.job_id}_chunk_{chunk.chunk_index}")
            documents.append(chunk.content)
            metadatas.append({"job_id": job.job_id})
    retriever.add_documents(ids, documents, metadatas)
    scores = {job.job_id: 0.0 for job in jobs}
    for result in retriever.query(profile_query(profile), n_results=len(ids)):
        job_id = result.metadata["job_id"]
        scores[job_id] = max(scores[job_id], result.score)
    return sort_scores(scores)


RANKERS: Dict[str, Ranker] = {"heuristic": heuristic_ranking, "bm25": bm25_ranking}


def ndcg_at_k(
    ranked: Sequence[str], labels: Dict[str, int], k: int = TOP_K
) -> Optional[float]:
    """
    NDCG of the top k jobs, with the label as the gain.

    Args:
        ranked: Job IDs, best first.
        labels: Job ID to label (0, 1, or 2).
        k: The cut-off.

    Returns:
        DCG divided by the ideal DCG, rounded to 4 places, or None when no
        job has a label above 0.
    """
    dcg = sum(
        labels.get(job_id, 0) / math.log2(rank + 2)
        for rank, job_id in enumerate(ranked[:k])
    )
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(ideal))
    return round(dcg / idcg, 4) if idcg > 0 else None


def recall_at_k(
    ranked: Sequence[str], labels: Dict[str, int], k: int = TOP_K
) -> Optional[float]:
    """
    The share of the jobs labeled 2 that are in the top k.

    Args:
        ranked: Job IDs, best first.
        labels: Job ID to label.
        k: The cut-off.

    Returns:
        The share, rounded to 4 places, or None when no job is labeled 2.
    """
    relevant = {job_id for job_id, label in labels.items() if label == 2}
    if not relevant:
        return None
    return round(len(relevant & set(ranked[:k])) / len(relevant), 4)


def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
    """
    The mean of the values that are not None.

    Args:
        values: The values.

    Returns:
        The mean rounded to 4 places, or None when no value is set.
    """
    present = [value for value in values if value is not None]
    return round(statistics.fmean(present), 4) if present else None


def run_ranking_suite(
    dataset_dir: Path = DEFAULT_DATASET_DIR,
    *,
    methods: Sequence[str] = CI_METHODS,
    k: int = TOP_K,
) -> EvalReport:
    """
    Rank every job for each profile with each method and score the rankings.

    Args:
        dataset_dir: The ranking set folder.
        methods: The methods to run (names in ``RANKERS``).
        k: The cut-off of NDCG and recall.

    Returns:
        Report with ``<method>_ndcg_at_<k>`` and ``<method>_recall_at_<k>``
        (means over the profiles) and the same for each profile, and the top
        k jobs of each ranking with their scores and labels.

    Raises:
        ValueError: When a method is unknown or the set is not complete.
    """
    unknown = [method for method in methods if method not in RANKERS]
    if unknown:
        raise ValueError(
            f"unknown ranking methods: {unknown}; known: {sorted(RANKERS)}"
        )
    data = load_ranking_set(dataset_dir)
    metrics: Dict[str, Optional[float]] = {}
    tops: Dict[str, Dict[str, List[Dict[str, object]]]] = {}
    for method in methods:
        ndcgs: List[Optional[float]] = []
        recalls: List[Optional[float]] = []
        tops[method] = {}
        for pid, profile in data.profiles.items():
            ranking = RANKERS[method](profile, data.modes[pid], data.jobs)
            ranked_ids = [job_id for job_id, _ in ranking]
            ndcg = ndcg_at_k(ranked_ids, data.labels[pid], k)
            recall = recall_at_k(ranked_ids, data.labels[pid], k)
            metrics[f"{method}_{pid}_ndcg_at_{k}"] = ndcg
            metrics[f"{method}_{pid}_recall_at_{k}"] = recall
            ndcgs.append(ndcg)
            recalls.append(recall)
            tops[method][pid] = [
                {
                    "job_id": job_id,
                    "score": round(score, 4),
                    "label": data.labels[pid][job_id],
                }
                for job_id, score in ranking[:k]
            ]
        metrics[f"{method}_ndcg_at_{k}"] = _mean(ndcgs)
        metrics[f"{method}_recall_at_{k}"] = _mean(recalls)
    label_count = sum(len(by_job) for by_job in data.labels.values())
    metadata = build_run_metadata(SUITE, data.files, label_count)
    return EvalReport(
        suite=SUITE,
        metadata=metadata,
        metrics=metrics,
        details={"k": k, "methods": list(methods), "top": tops},
    )
```

## Step 3: register the suite

The module docstring of the registry:

```python edit=apps/backend-py/src/evaluation/suites/__init__.py
<<<<<<< OLD
Step 3.8 adds ``writer`` (local only; it needs Ollama).
Later steps add ``ranking`` and ``compare``.
=======
Step 3.8 adds ``writer`` (local only; it needs Ollama).
Step 3.4 adds ``ranking`` (heuristic and BM25 in CI).
Later steps add ``compare``.
>>>>>>> NEW
```

The suite names:

```python edit=apps/backend-py/src/evaluation/suites/__init__.py
<<<<<<< OLD
    "writer",
)
=======
    "writer",
    "ranking",
)
>>>>>>> NEW
```

The registry branch:

```python edit=apps/backend-py/src/evaluation/suites/__init__.py
<<<<<<< OLD
    raise KeyError(f"unknown eval suite: {name}")
=======
    if name == "ranking":
        from .ranking import DEFAULT_DATASET_DIR, run_ranking_suite

        return run_ranking_suite, DEFAULT_DATASET_DIR
    raise KeyError(f"unknown eval suite: {name}")
>>>>>>> NEW
```

The `eval` help example in `main.py`:

```python edit=apps/backend-py/main.py
<<<<<<< OLD
  python main.py eval writer --model qwen2.5:7b

=======
  python main.py eval writer --model qwen2.5:7b

  # Score job ranking (heuristic and BM25) on the committed labeled set
  python main.py eval ranking

>>>>>>> NEW
```

The pinned suite names in `tests/unit/test_scam_suite.py`:

```python edit=apps/backend-py/tests/unit/test_scam_suite.py
<<<<<<< OLD
            "structured",
            "writer",
        )
=======
            "structured",
            "writer",
            "ranking",
        )
>>>>>>> NEW
```

## Done when

Run the new tests and the suite, command, and set tests:

```bash check cwd=apps/backend-py
.venv/bin/python -m pytest tests/unit/test_ranking_suite.py tests/unit/test_ranking_set.py tests/unit/test_scam_suite.py tests/unit/test_cli.py tests/unit/test_dedupe_suite.py tests/unit/test_writer_command.py -q
```

Format the changed files:

```bash check cwd=apps/backend-py
.venv/bin/python -m black src/evaluation/suites/ranking.py tests/unit/test_ranking_suite.py src/evaluation/suites/__init__.py main.py tests/unit/test_scam_suite.py
```

Check the lint:

```bash check cwd=apps/backend-py
.venv/bin/python -m ruff check src/evaluation/suites/ranking.py tests/unit/test_ranking_suite.py src/evaluation/suites/__init__.py main.py tests/unit/test_scam_suite.py
```

Run the mypy gate (no new errors):

```bash check cwd=apps/backend-py
.venv/bin/python scripts/mypy_gate.py
```

Commit message:

```text commit
feat(eval): add the ranking suite with the heuristic matcher and BM25

src/evaluation/suites/ranking.py ranks the 70 jobs of the ranking set
for each profile with the heuristic matcher (the profile's matcher
mode) and with BM25 over the RAG chunks and the RAG ranker's profile
query, and reports NDCG@10 (label as gain) and recall@10 of the jobs
labeled 2, for each profile and as the mean. Deterministic, with ties
broken by job ID. main.py eval ranking runs it (Step 3.4, MH-2).
```
