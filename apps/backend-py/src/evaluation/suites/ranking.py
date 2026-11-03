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
