"""Tests for job-level hybrid fusion in the RAG ranker (Step 3.4, R5)."""

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from unittest.mock import patch

import pytest

from src.models.job_listing import JobListing
from src.models.user_profile import UserProfile
from src.rag import ranker as ranker_module
from src.rag.bm25_retriever import BM25Retriever
from src.rag.chunker import TextChunker
from src.rag.config import BM25Config, RAGConfig, RRFFusionConfig, VectorStoreConfig
from src.rag.ranker import RAGRanker
from src.rag.rrf_fusion import reciprocal_rank_fusion
from src.rag.vector_store import ChromaStore
from src.scoring.matcher import MatchScore
from tests.unit.test_ranking_suite import job_with, profile_with

MATCH = "kafka streaming engineer"
NO_MATCH = "pastry chef for a small bakery"


class FakeStore:
    """A vector store with a fixed similarity for each job."""

    def __init__(self, similarities: Dict[str, float]) -> None:
        """
        Set the similarities.

        Args:
            similarities: Job ID to the cosine similarity with the profile.
                A job that is not here has no embeddings.
        """
        self.similarities = similarities

    def job_exists(self, job_id: str) -> bool:
        """
        Report a job as stored when it has a similarity, as after an earlier run.

        Args:
            job_id: The job ID.

        Returns:
            True when the job has a similarity.
        """
        return job_id in self.similarities

    def add_jobs_batch(self, **kwargs: Any) -> None:
        """
        Accept new jobs.

        Args:
            kwargs: The store arguments.
        """

    def add_profile(self, **kwargs: Any) -> None:
        """
        Accept the profile.

        Args:
            kwargs: The store arguments.
        """

    def get_profile_embeddings(self, profile_id: str = "default") -> List[List[float]]:
        """
        One profile vector.

        Args:
            profile_id: The profile ID.

        Returns:
            The unit vector on the first axis.
        """
        return [[1.0, 0.0]]

    def get_job_embeddings(self, job_id: str) -> Optional[List[List[float]]]:
        """
        One vector with the job's similarity to the profile vector.

        Args:
            job_id: The job ID.

        Returns:
            The vector, or None when the job has no embeddings.
        """
        similarity = self.similarities.get(job_id)
        if similarity is None:
            return None
        return [[similarity, (1.0 - similarity**2) ** 0.5]]


class FakeCrossEncoder:
    """A cross-encoder that scores jobs in the given order and keeps the top_k."""

    is_available = True

    def __init__(self, order: List[str]) -> None:
        """
        Set the order.

        Args:
            order: Job IDs, best first.
        """
        self.order = order
        self.calls: List[Dict[str, Any]] = []

    def rerank(
        self, query: str, results: List[Dict[str, Any]], top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Record the call and score the results by the fixed order.

        Args:
            query: The query text.
            results: The results to rerank.
            top_k: The number of results to keep.

        Returns:
            The best results with a cross-encoder score.
        """
        self.calls.append({"query": query, "results": results, "top_k": top_k})
        scored = [
            {
                **result,
                "cross_encoder_score": -float(self.order.index(result["doc_id"])),
            }
            for result in results
        ]
        scored.sort(key=lambda item: -item["cross_encoder_score"])
        return scored[:top_k]


def make_ranker(
    store: Any,
    client: Any,
    retriever: Optional[BM25Retriever] = None,
    config: Optional[RAGConfig] = None,
    cross_encoder: Any = None,
) -> RAGRanker:
    """
    A RAG ranker with a BM25 retriever.

    Args:
        store: The vector store.
        client: The embedding client.
        retriever: The BM25 retriever (default: a new one).
        config: The RAG configuration (default: the dataclass defaults).
        cross_encoder: The optional cross-encoder.

    Returns:
        The ranker.
    """
    config = config or RAGConfig()
    return RAGRanker(
        config=config,
        embedding_client=client,
        vector_store=store,
        chunker=TextChunker(config.chunking.get("job_description")),
        bm25_retriever=retriever or BM25Retriever(),
        cross_encoder=cross_encoder,
    )


def scored(jobs: List[JobListing], total: int = 50) -> List[Tuple[JobListing, Any]]:
    """
    Give each job one heuristic score.

    Args:
        jobs: The jobs.
        total: The heuristic score.

    Returns:
        The input of ``re_rank``.
    """
    return [
        (
            job,
            MatchScore(
                job=job,
                total_score=total,
                passed_threshold=True,
                breakdown={},
                matched_keywords=[],
                missing_skills=[],
                recommendation="maybe",
                reasoning="",
            ),
        )
        for job in jobs
    ]


def jobs_by_id(results: List[Any]) -> Dict[str, Any]:
    """
    Index ``re_rank`` results by job ID.

    Args:
        results: The results.

    Returns:
        Job ID to result.
    """
    return {result.job.job_id: result for result in results}


@pytest.fixture
def fusion_calls() -> Iterator[List[Dict[str, Any]]]:
    """
    Record each call of the RRF fusion.

    Yields:
        The keyword arguments of the calls.
    """
    calls: List[Dict[str, Any]] = []

    def spy(**kwargs: Any) -> Any:
        """
        Record the call and run the real fusion.

        Args:
            kwargs: The fusion arguments.

        Returns:
            The fused results.
        """
        calls.append(kwargs)
        return reciprocal_rank_fusion(**kwargs)

    with patch.object(ranker_module, "reciprocal_rank_fusion", spy):
        yield calls


def ids_of(results: List[Dict[str, Any]]) -> List[str]:
    """
    The document IDs of a result list.

    Args:
        results: The results.

    Returns:
        The IDs in order.
    """
    return [result["doc_id"] for result in results]


# Query


def test_query_has_the_summary_the_skills_and_the_target_keywords() -> None:
    """The BM25 query reads the real profile fields."""
    profile = UserProfile.model_validate(
        {
            "name": "Test Person",
            "contact": {"email": "test@example.com", "location": "Singapore"},
            "summary": "Backend engineer",
            "skills": [{"name": "Kafka"}, {"name": "Go"}],
            "targets": {"keywords": ["platform engineer"]},
        }
    )
    query = make_ranker(None, None)._build_profile_query_text(profile)
    assert query == "Backend engineer Kafka Go platform engineer"


def test_query_without_a_summary() -> None:
    """A profile without a summary gives the other fields only."""
    query = make_ranker(None, None)._build_profile_query_text(profile_with(["Kafka"]))
    assert query == "Kafka"


# BM25 index


def test_profile_chunks_stay_out_of_the_bm25_index(mock_embedding_client: Any) -> None:
    """Only job chunks reach the BM25 index."""
    profile = profile_with(["Kafka"])
    job = job_with("a", "Engineer", MATCH)
    ranker = make_ranker(FakeStore({"a": 0.5}), mock_embedding_client)

    ranker.index_profile(profile)
    assert ranker.bm25_retriever is not None
    assert ranker.bm25_retriever.doc_count == 0

    ranker.re_rank(scored([job]), profile)
    expected = len(ranker.chunker.chunk_job(job))
    assert ranker.bm25_retriever.doc_count == expected


def test_index_jobs_leaves_the_bm25_index_alone(mock_embedding_client: Any) -> None:
    """The hybrid step owns the BM25 index, so indexing does not fill it."""
    ranker = make_ranker(FakeStore({}), mock_embedding_client)
    ranker.index_jobs([job_with("a", "Engineer", MATCH)])
    assert ranker.bm25_retriever is not None
    assert ranker.bm25_retriever.doc_count == 0


def test_jobs_already_in_the_store_get_a_bm25_rank(mock_embedding_client: Any) -> None:
    """Jobs from an earlier run skip index_jobs but still reach BM25."""
    store = FakeStore({"a": 0.5, "b": 0.5})
    jobs = [job_with("a", "Baker", NO_MATCH), job_with("b", "Engineer", MATCH)]
    ranker = make_ranker(store, mock_embedding_client)

    results = jobs_by_id(ranker.re_rank(scored(jobs), profile_with(["Kafka"])))

    assert results["b"].semantic_score > results["a"].semantic_score


def test_each_call_indexes_only_its_candidates(mock_embedding_client: Any) -> None:
    """A later call does not keep the jobs of an earlier call in the BM25 index."""
    store = FakeStore({"a": 0.5, "b": 0.5})
    ranker = make_ranker(store, mock_embedding_client)
    first = job_with("a", "Engineer", MATCH)
    second = job_with("b", "Engineer", MATCH)
    profile = profile_with(["Kafka"])

    ranker.re_rank(scored([first]), profile)
    ranker.re_rank(scored([second]), profile)

    assert ranker.bm25_retriever is not None
    assert ranker.bm25_retriever.doc_count == len(ranker.chunker.chunk_job(second))


def test_jobs_of_earlier_runs_do_not_reach_the_fusion(
    temp_chroma_dir: str,
    mock_embedding_client: Any,
    fusion_calls: List[Dict[str, Any]],
) -> None:
    """A stored job that is not a candidate gets no rank and no score."""
    store = ChromaStore(VectorStoreConfig(persist_directory=temp_chroma_dir))
    store.initialize()
    ranker = make_ranker(store, mock_embedding_client)
    ranker.index_jobs([job_with("old", "Engineer", MATCH)])
    candidates = [job_with("a", "Engineer", MATCH), job_with("b", "Baker", NO_MATCH)]

    results = ranker.re_rank(scored(candidates), profile_with(["Kafka"]))

    assert sorted(result.job.job_id for result in results) == ["a", "b"]
    assert sorted(ids_of(fusion_calls[0]["dense_results"])) == ["a", "b"]
    assert ids_of(fusion_calls[0]["sparse_results"]) == ["a"]


# Job-level fusion


def test_a_job_is_once_in_each_list(
    mock_embedding_client: Any, fusion_calls: List[Dict[str, Any]]
) -> None:
    """A job with several matching chunks has one entry in each list."""
    job = JobListing.model_validate(
        {
            "job_id": "a",
            "title": "Kafka Engineer",
            "company": "Test Co",
            "source": "other",
            "description": MATCH,
            "skills": [{"name": "Kafka"}],
            "requirements": [{"text": "Kafka experience"}],
        }
    )
    other = job_with("b", "Baker", NO_MATCH)
    ranker = make_ranker(None, mock_embedding_client)

    ranker._hybrid_retrieve(profile_with(["Kafka"]), [job, other], {"a": 0.9, "b": 0.8})

    assert ids_of(fusion_calls[0]["dense_results"]) == ["a", "b"]
    assert ids_of(fusion_calls[0]["sparse_results"]) == ["a"]


def test_a_job_gets_its_score_from_both_lists(mock_embedding_client: Any) -> None:
    """A job second in dense and first in BM25 beats the first job in dense."""
    jobs = [
        job_with("a", "Baker", NO_MATCH),
        job_with("b", "Engineer", MATCH),
        job_with("c", "Baker", NO_MATCH),
    ]
    ranker = make_ranker(None, mock_embedding_client)

    scores = ranker._hybrid_retrieve(
        profile_with(["Kafka"]), jobs, {"a": 0.9, "b": 0.8, "c": 0.7}
    )

    assert scores["b"] == 1.0
    assert scores["c"] == 0.0
    assert 0.0 < scores["a"] < 0.1


def test_the_best_chunk_gives_the_bm25_score(mock_embedding_client: Any) -> None:
    """A job keeps the score of its best chunk, not of a later chunk."""
    job = JobListing.model_validate(
        {
            "job_id": "a",
            "title": "Engineer",
            "company": "Test Co",
            "source": "other",
            "description": "kafka kafka kafka",
            "requirements": [{"text": "Long text with one kafka word in it"}],
        }
    )
    other = job_with("b", "Engineer", "one kafka word")
    filler = [job_with(f"z{i}", "Baker", NO_MATCH) for i in range(3)]
    ranker = make_ranker(None, mock_embedding_client)

    scores = ranker._bm25_job_scores("kafka", [job, other, *filler])

    assert scores["a"] == 1.0
    assert scores["b"] < 1.0


def test_a_job_with_no_term_match_has_no_bm25_score(mock_embedding_client: Any) -> None:
    """No term match gives no BM25 entry, so no rank from BM25."""
    jobs = [job_with("a", "Engineer", MATCH), job_with("b", "Baker", NO_MATCH)]
    ranker = make_ranker(None, mock_embedding_client)
    assert set(ranker._bm25_job_scores("kafka", jobs)) == {"a"}


def test_ties_follow_the_job_id() -> None:
    """The order of equal scores does not depend on the input order."""
    documents = {"a": "", "b": "", "c": ""}
    results = RAGRanker._ranked_results({"c": 0.5, "a": 0.5, "b": 0.9}, documents)
    assert ids_of(results) == ["b", "a", "c"]


def test_the_fusion_uses_the_configured_values(
    mock_embedding_client: Any, fusion_calls: List[Dict[str, Any]]
) -> None:
    """The RRF constant and weights come from the configuration."""
    config = RAGConfig(rrf=RRFFusionConfig(k=7, dense_weight=0.3, sparse_weight=0.2))
    ranker = make_ranker(None, mock_embedding_client, config=config)

    ranker._hybrid_retrieve(
        profile_with(["Kafka"]), [job_with("a", "Engineer", MATCH)], {"a": 0.5}
    )

    call = fusion_calls[0]
    assert (call["k"], call["dense_weight"], call["sparse_weight"]) == (7, 0.3, 0.2)


# One scale


def test_every_candidate_is_on_one_scale(mock_embedding_client: Any) -> None:
    """All candidates get a fused score, also past the old limit of 20 results."""
    matches = [job_with(f"m{i:02d}", "Engineer", MATCH) for i in range(30)]
    others = [job_with(f"o{i:02d}", "Baker", NO_MATCH) for i in range(40)]
    jobs = matches + others
    dense = {job.job_id: 0.9 - i / 100 for i, job in enumerate(jobs)}
    ranker = make_ranker(None, mock_embedding_client)

    scores = ranker._hybrid_retrieve(profile_with(["Kafka"]), jobs, dense)

    assert set(scores) == set(dense)
    assert max(scores.values()) == 1.0
    assert min(scores.values()) == 0.0
    assert len(ranker._bm25_job_scores("kafka", jobs)) == len(matches)


def test_a_found_job_is_not_below_the_jobs_that_retrieval_misses(
    mock_embedding_client: Any,
) -> None:
    """The job first in BM25 leads, however low its dense rank."""
    similarities = {f"j{i:02d}": 0.7 - i / 100 for i in range(24)}
    similarities["hit"] = 0.1
    jobs = [job_with(job_id, "Baker", NO_MATCH) for job_id in similarities]
    jobs[-1] = job_with("hit", "Engineer", MATCH)
    ranker = make_ranker(FakeStore(similarities), mock_embedding_client)

    results = ranker.re_rank(scored(jobs), profile_with(["Kafka"]))

    assert results[0].job.job_id == "hit"
    assert results[0].semantic_score == 1.0
    assert all(result.semantic_score < 1.0 for result in results[1:])


def test_a_job_without_embeddings_keeps_its_bm25_rank(
    mock_embedding_client: Any,
) -> None:
    """A job needs one list to get a score; a job in no list gets 0.0."""
    store = FakeStore({"a": 0.9, "b": 0.8})
    jobs = [
        job_with("a", "Baker", NO_MATCH),
        job_with("b", "Baker", NO_MATCH),
        job_with("found", "Engineer", MATCH),
        job_with("lost", "Baker", NO_MATCH),
    ]
    ranker = make_ranker(store, mock_embedding_client)

    results = jobs_by_id(ranker.re_rank(scored(jobs), profile_with(["Kafka"])))

    assert results["found"].semantic_score > 0.0
    assert results["lost"].semantic_score == 0.0
    embeddings = store.get_profile_embeddings()
    assert set(ranker._dense_scores(embeddings, jobs)) == {"a", "b"}


def test_one_candidate_gets_the_top_score(mock_embedding_client: Any) -> None:
    """With no spread, a job with a positive score gets 1.0."""
    ranker = make_ranker(None, mock_embedding_client)
    scores = ranker._hybrid_retrieve(
        profile_with(["Kafka"]), [job_with("a", "Engineer", MATCH)], {"a": 0.5}
    )
    assert scores == {"a": 1.0}


def test_no_list_gives_no_scores(mock_embedding_client: Any) -> None:
    """A job in no list gives an empty result."""
    ranker = make_ranker(None, mock_embedding_client)
    scores = ranker._hybrid_retrieve(
        profile_with(["Kafka"]), [job_with("a", "Baker", NO_MATCH)], {}
    )
    assert scores == {}


def test_the_combined_score_uses_the_fused_score(mock_embedding_client: Any) -> None:
    """The combined score is 0.4 heuristic + 0.6 fused score."""
    store = FakeStore({"a": 0.2})
    ranker = make_ranker(store, mock_embedding_client)

    result = ranker.re_rank(
        scored([job_with("a", "Engineer", MATCH)], total=50), profile_with(["Kafka"])
    )[0]

    assert result.semantic_score == 1.0
    assert result.combined_score == pytest.approx(0.8)
    assert result.recommendation == "apply"


# Failure and dense-only paths


def test_a_bm25_failure_leaves_the_dense_ranking(mock_embedding_client: Any) -> None:
    """When BM25 fails, the dense ranks alone give the scores."""

    class BrokenRetriever(BM25Retriever):
        """A retriever whose query fails."""

        def query(self, query_text: str, n_results: int = 20) -> Any:
            """
            Fail.

            Args:
                query_text: The query.
                n_results: The result limit.

            Raises:
                RuntimeError: Always.
            """
            raise RuntimeError("broken index")

    jobs = [job_with("a", "Engineer", MATCH), job_with("b", "Baker", NO_MATCH)]
    ranker = make_ranker(None, mock_embedding_client, BrokenRetriever())

    scores = ranker._hybrid_retrieve(
        profile_with(["Kafka"]), jobs, {"a": 0.2, "b": 0.8}
    )

    assert scores == {"b": 1.0, "a": 0.0}


def test_no_retriever_gives_no_bm25_scores(mock_embedding_client: Any) -> None:
    """Without a retriever there is nothing to score."""
    ranker = make_ranker(None, mock_embedding_client)
    ranker.bm25_retriever = None
    assert ranker._bm25_job_scores("kafka", [job_with("a", "Eng", MATCH)]) == {}


@pytest.mark.parametrize(
    "config",
    [
        RAGConfig(bm25=BM25Config(enabled=False)),
        RAGConfig(rrf=RRFFusionConfig(enabled=False)),
    ],
)
def test_without_hybrid_the_score_is_the_similarity(
    config: RAGConfig, mock_embedding_client: Any
) -> None:
    """With BM25 or RRF off, the score stays the cosine similarity."""
    store = FakeStore({"a": 0.8})
    jobs = [job_with("a", "Baker", NO_MATCH), job_with("none", "Baker", NO_MATCH)]
    ranker = make_ranker(store, mock_embedding_client, config=config)

    results = jobs_by_id(ranker.re_rank(scored(jobs), profile_with(["Kafka"])))

    assert results["a"].semantic_score == pytest.approx(0.8)
    assert results["none"].semantic_score == 0.0


# Cross-encoder


def test_the_cross_encoder_ranks_jobs(mock_embedding_client: Any) -> None:
    """It gets one document for each job and the jobs past its top_k get 0.0."""
    config = RAGConfig()
    config.cross_encoder.top_k = 2
    encoder = FakeCrossEncoder(["c", "a", "b"])
    store = FakeStore({"a": 0.9, "b": 0.8, "c": 0.7})
    jobs = [
        job_with("a", "Engineer", MATCH),
        job_with("b", "Engineer", "second " + MATCH),
        JobListing.model_validate(
            {"job_id": "c", "title": "Kafka Lead", "company": "Co", "source": "other"}
        ),
    ]
    ranker = make_ranker(
        store, mock_embedding_client, config=config, cross_encoder=encoder
    )

    results = jobs_by_id(ranker.re_rank(scored(jobs), profile_with(["Kafka"])))

    call = encoder.calls[0]
    assert call["query"] == "Kafka"
    assert call["top_k"] == 2
    documents = {item["doc_id"]: item["document"] for item in call["results"]}
    assert documents == {"a": MATCH, "b": "second " + MATCH, "c": "Kafka Lead"}
    assert results["c"].semantic_score == 1.0
    assert results["a"].semantic_score == 0.0
    assert results["b"].semantic_score == 0.0


def test_the_real_configuration_loads() -> None:
    """The configuration file loads without the old result limit."""
    path = Path(__file__).resolve().parents[2] / "config" / "rag_config.yaml"
    config = RAGConfig.from_yaml(str(path))
    assert config.bm25.enabled is True
    assert not hasattr(config.bm25, "n_results")
