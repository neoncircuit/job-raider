"""Tests for the dense and hybrid ranking methods (Step 3.4, MH-3)."""

import hashlib
import math
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

import main as cli
import src.evaluation.suites.ranking as ranking
from src.evaluation.report import EvalReport
from src.evaluation.run_metadata import build_run_metadata
from src.rag.bm25_retriever import BM25Retriever
from src.rag.config import RAGConfig
from tests.unit.test_cli import parse
from tests.unit.test_ranking_suite import job_with, profile_with


class BowEmbedder:
    """A fake embedding client: word counts hashed into 256 buckets."""

    model = "fake-bow"

    def __init__(self, available: bool = True) -> None:
        """
        Keep the availability answer.

        Args:
            available: The answer of ``is_model_available``.
        """
        self.available = available

    def is_model_available(self) -> bool:
        """
        Say whether the model is available.

        Returns:
            The availability given to the constructor.
        """
        return self.available

    def embed(self, text: str) -> List[float]:
        """
        Embed one text.

        Args:
            text: The text.

        Returns:
            A unit vector of hashed word counts.
        """
        vector = [0.0] * 256
        for word in re.findall(r"\w+", text.lower()):
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed several texts.

        Args:
            texts: The texts.

        Returns:
            One vector for each text.
        """
        return [self.embed(text) for text in texts]


def config() -> RAGConfig:
    """
    The RAG configuration of the pipeline.

    Returns:
        The configuration from ``config/rag_config.yaml``.
    """
    return RAGConfig.from_yaml(str(ranking.RAG_CONFIG_PATH))


def jobs_with_kafka() -> List[Any]:
    """
    One Kafka job and six unrelated jobs.

    Returns:
        The jobs.
    """
    return [
        job_with("j1", "Kafka Engineer", "Build Kafka streams and Kafka connectors.")
    ] + [
        job_with(f"f{n}", "Clerk", "File records and answer the phone.")
        for n in range(6)
    ]


def test_dense_ranks_the_closest_job_first() -> None:
    """The job whose chunks are closest to the profile ranks first."""
    result = ranking.dense_ranking(
        profile_with(["Kafka", "Streams"]),
        {},
        jobs_with_kafka(),
        config=config(),
        embedding_client=BowEmbedder(),
    )

    assert result[0][0] == "j1"


def test_dense_uses_the_ranker_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dense scores come from the RAG ranker's similarity, once for each job."""
    calls: List[int] = []

    def similarity(self: Any, profile: Any, job: Any) -> float:
        """Record the call and return a fixed score."""
        calls.append(len(job))
        return 0.5

    monkeypatch.setattr(ranking.RAGRanker, "_compute_semantic_similarity", similarity)
    jobs = jobs_with_kafka()

    ranking.dense_ranking(
        profile_with(["Kafka"]),
        {},
        jobs,
        config=config(),
        embedding_client=BowEmbedder(),
    )

    assert len(calls) == len(jobs)
    assert all(count > 0 for count in calls)


def test_hybrid_follows_re_rank_and_the_profile_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hybrid orders jobs by re_rank's combined score and scores with the profile mode."""
    modes: List[bool] = []
    real = ranking.JobMatcher

    def make(fresh_grad_mode: bool = False, **kwargs: Any) -> Any:
        """Record the mode and make a real matcher."""
        modes.append(fresh_grad_mode)
        return real(fresh_grad_mode=fresh_grad_mode, **kwargs)

    def re_rank(self: Any, scored: Any, profile: Any) -> List[Any]:
        """Return two jobs in a fixed order that is not the job-ID order."""
        by_id = {job.job_id: job for job, _ in scored}
        return [
            SimpleNamespace(job=by_id["j1"], combined_score=0.9),
            SimpleNamespace(job=by_id["f3"], combined_score=0.5),
        ]

    monkeypatch.setattr(ranking, "JobMatcher", make)
    monkeypatch.setattr(ranking.RAGRanker, "re_rank", re_rank)

    result = ranking.hybrid_ranking(
        profile_with(["Kafka"]),
        {"fresh_grad_mode": True},
        jobs_with_kafka(),
        config=config(),
        embedding_client=BowEmbedder(),
    )

    assert [job_id for job_id, _ in result[:3]] == ["j1", "f3", "f0"]
    assert result[2][1] == -1.0
    assert modes == [True]


def test_each_call_gets_a_new_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each ranking builds its own vector store folder."""
    folders: List[str] = []
    real = ranking.ChromaStore

    def make(store_config: Any) -> Any:
        """Record the folder and make a real store."""
        folders.append(store_config.persist_directory)
        return real(store_config)

    monkeypatch.setattr(ranking, "ChromaStore", make)
    for _ in range(2):
        ranking.dense_ranking(
            profile_with(["Kafka"]),
            {},
            jobs_with_kafka(),
            config=config(),
            embedding_client=BowEmbedder(),
        )

    assert len(folders) == 2
    assert folders[0] != folders[1]


def test_rag_ranker_is_built_like_the_pipeline(tmp_path: Path) -> None:
    """The ranker has a new BM25 index, the job chunker, and no cross-encoder."""
    ranker = ranking.rag_ranker(config(), BowEmbedder(), tmp_path)

    assert isinstance(ranker.bm25_retriever, BM25Retriever)
    assert ranker.bm25_retriever.doc_count == 0
    assert ranker.cross_encoder is None
    assert ranker.chunker.config == config().chunking.get("job_description")


def test_local_methods_need_the_embedding_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the embedding model, a local method stops with a clear error."""
    monkeypatch.setattr(ranking, "EmbeddingClient", lambda **kwargs: BowEmbedder(False))

    with pytest.raises(ValueError, match="not available"):
        ranking.run_ranking_suite(methods=["dense"])


def test_ci_methods_never_make_an_embedding_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CI methods run without the embedding model."""

    def refuse(**kwargs: Any) -> Any:
        """Fail if called."""
        raise AssertionError("embedding client made for a CI method")

    monkeypatch.setattr(ranking, "EmbeddingClient", refuse)

    report = ranking.run_ranking_suite(methods=["heuristic", "bm25"])

    assert report.metrics["bm25_ndcg_at_10"] is not None


def test_suite_runs_all_methods_with_a_given_client() -> None:
    """With an embedding client, the suite reports the dense and hybrid methods."""
    report = ranking.run_ranking_suite(
        methods=list(ranking.ALL_METHODS), embedding_client=BowEmbedder()
    )

    for method in ("dense", "hybrid"):
        for pid in ("fresh_ml", "mid_backend"):
            value = report.metrics[f"{method}_{pid}_ndcg_at_10"]
            assert value is not None and 0.0 <= value <= 1.0
    assert report.details["methods"] == ["heuristic", "bm25", "dense", "hybrid"]


def fake_report(tmp_path: Path) -> EvalReport:
    """
    A small ranking report for the command tests.

    Args:
        tmp_path: The test folder.

    Returns:
        The report.
    """
    path = tmp_path / "labels.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    return EvalReport(
        suite="ranking",
        metadata=build_run_metadata("ranking", [path], 1, repo_dir=tmp_path),
        metrics={"bm25_ndcg_at_10": 1.0},
        details={},
    )


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (["--methods", "heuristic, dense"], {"methods": ["heuristic", "dense"]}),
        ([], {}),
    ],
)
def test_eval_ranking_passes_the_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: List[str],
    expected: Dict[str, Any],
) -> None:
    """``eval ranking --methods`` gives the methods to the suite; no option gives none."""
    seen: Dict[str, Any] = {}

    def fake_suite(dataset: Path, **kwargs: Any) -> EvalReport:
        """Record the arguments and return a report."""
        seen["kwargs"] = kwargs
        return fake_report(tmp_path)

    monkeypatch.setattr(
        "src.evaluation.suites.get_suite", lambda name: (fake_suite, tmp_path)
    )
    args = parse(
        ["eval", "ranking", *extra, "--out", str(tmp_path / "out"), "--no-mlflow"]
    )

    assert cli.run_eval_command(args) == 0
    assert seen["kwargs"] == expected
