"""
Job Raider - RAG Ranker

Re-ranks job candidates using semantic similarity from vector embeddings.
Combines heuristic scores with RAG-based semantic matching for hybrid scoring.

Author: Job Raider
Date: 2026-04-26
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..llm.embedding_client import EmbeddingClient, EmbeddingError
from ..models.job_listing import JobListing
from ..models.user_profile import UserProfile
from ..scoring.matcher import MatchScore
from .bm25_retriever import BM25Retriever
from .chunker import TextChunk, TextChunker
from .config import RAGConfig
from .cross_encoder import CrossEncoderReranker
from .rrf_fusion import reciprocal_rank_fusion
from .vector_store import ChromaStore

logger = logging.getLogger("job_raider.rag")


@dataclass
class RAGMatchScore:
    """Combined score from heuristic and semantic analysis.

    Attributes:
        job: The job listing being scored.
        heuristic_score: Score from the heuristic matcher (0-100).
        semantic_score: Score in 0.0-1.0: the fused dense and BM25 score, or the
            cosine similarity when BM25 is off.
        combined_score: Weighted combination of heuristic and semantic.
        heuristic_breakdown: Per-category breakdown from heuristic scoring.
        matched_keywords: Keywords that matched between job and profile.
        missing_skills: Skills the job requires but the profile lacks.
        recommendation: Action recommendation ("apply", "maybe", "skip").
        reasoning: Human-readable explanation of the score.
        passed_threshold: Whether the combined score meets the threshold.
    """

    job: JobListing
    heuristic_score: int
    semantic_score: float
    combined_score: float
    heuristic_breakdown: Dict[str, int]
    matched_keywords: List[str]
    missing_skills: List[str]
    recommendation: str
    reasoning: str
    passed_threshold: bool


class RAGRanker:
    """Re-ranks job candidates using semantic similarity.

    Takes jobs that passed heuristic scoring and re-ranks them using
    RAG-based semantic similarity against the user profile embeddings
    stored in ChromaDB.
    """

    def __init__(
        self,
        config: RAGConfig,
        embedding_client: EmbeddingClient,
        vector_store: ChromaStore,
        chunker: TextChunker,
        bm25_retriever: Optional[BM25Retriever] = None,
        cross_encoder: Optional[CrossEncoderReranker] = None,
    ):
        """Initialize the RAG ranker.

        Args:
            config: Complete RAG pipeline configuration.
            embedding_client: Client for generating embeddings.
            vector_store: ChromaDB vector store for similarity queries.
            chunker: Text chunker for breaking down documents.
            bm25_retriever: Optional BM25 retriever for hybrid search.
                When None, falls back to dense-only retrieval.
            cross_encoder: Optional cross-encoder reranker.
                When None, reranking is skipped.
        """
        self.config = config
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.chunker = chunker
        self.bm25_retriever = bm25_retriever
        self.cross_encoder = cross_encoder

    def index_jobs(self, jobs: List[JobListing]) -> Dict[str, Any]:
        """Index job listings into the vector store.

        Chunks job descriptions, generates embeddings, and stores them
        in ChromaDB. Skips jobs that are already indexed.

        Args:
            jobs: Job listings to index.

        Returns:
            Dict with indexing statistics.
        """
        new_jobs = []
        new_chunks_all: List[List[TextChunk]] = []

        for job in jobs:
            if self.vector_store.job_exists(job.job_id):
                continue
            chunks = self.chunker.chunk_job(job)
            if chunks:
                new_jobs.append(job)
                new_chunks_all.append(chunks)

        if not new_jobs:
            return {"indexed": 0, "skipped": len(jobs), "total_chunks": 0}

        # Generate embeddings for all new chunks
        all_embeddings: List[List[List[float]]] = []
        for chunks in new_chunks_all:
            texts = [c.content for c in chunks]
            embeddings = self.embedding_client.embed_batch(texts)
            # Filter out empty embeddings (failed)
            valid = [(c, e) for c, e in zip(chunks, embeddings) if e]
            if valid:
                valid_chunks, valid_embeddings = zip(*valid)
                all_embeddings.append(list(valid_embeddings))
            else:
                all_embeddings.append([])

        # Store in ChromaDB
        valid_jobs = []
        valid_chunks: List[List[TextChunk]] = []
        valid_embeddings: List[List[List[float]]] = []

        for job, chunks, embeddings in zip(new_jobs, new_chunks_all, all_embeddings):
            if embeddings:
                valid_jobs.append(job)
                valid_chunks.append(chunks)
                valid_embeddings.append(embeddings)

        if valid_jobs:
            self.vector_store.add_jobs_batch(
                job_ids=[j.job_id for j in valid_jobs],
                all_chunks=valid_chunks,
                all_embeddings=valid_embeddings,
            )

        total_chunks = sum(len(c) for c in valid_chunks)
        return {
            "indexed": len(valid_jobs),
            "skipped": len(jobs) - len(valid_jobs),
            "total_chunks": total_chunks,
        }

    def index_profile(
        self,
        profile: UserProfile,
        profile_id: str = "default",
    ) -> Dict[str, Any]:
        """Index user profile into the vector store.

        Always re-indexes since profiles change frequently.

        Args:
            profile: User profile to index.
            profile_id: Profile identifier.

        Returns:
            Dict with indexing statistics.
        """
        chunks = self.chunker.chunk_profile(profile)
        if not chunks:
            return {"indexed": False, "chunk_count": 0}

        texts = [c.content for c in chunks]
        embeddings = self.embedding_client.embed_batch(texts)

        # Filter out failed embeddings
        valid = [(c, e) for c, e in zip(chunks, embeddings) if e]
        if not valid:
            return {"indexed": False, "chunk_count": 0}

        valid_chunks, valid_embeddings = zip(*valid)
        self.vector_store.add_profile(
            profile_id=profile_id,
            chunks=list(valid_chunks),
            embeddings=list(valid_embeddings),
        )

        return {
            "indexed": True,
            "chunk_count": len(valid_chunks),
        }

    def re_rank(
        self,
        scored_listings: List[Tuple[JobListing, MatchScore]],
        profile: UserProfile,
    ) -> List[RAGMatchScore]:
        """Re-rank scored listings using semantic similarity.

        Takes the output of Stage 5 (heuristic scoring) and produces
        a new ranking based on combined heuristic + semantic scores.

        Args:
            scored_listings: Output from Stage 5 (job, heuristic score) tuples.
            profile: User profile for comparison.

        Returns:
            List of RAGMatchScore sorted by combined_score descending.
        """
        if not scored_listings:
            return []

        try:
            # Ensure profile is indexed
            self.index_profile(profile)
        except EmbeddingError:
            logger.warning("Profile indexing failed, using heuristic-only scoring")
            return self._fallback_to_heuristic(scored_listings)

        # Get profile embeddings from store
        profile_embeddings = self.vector_store.get_profile_embeddings("default")
        if not profile_embeddings:
            logger.warning("No profile embeddings found, using heuristic-only scoring")
            return self._fallback_to_heuristic(scored_listings)

        # Ensure jobs are indexed
        jobs = [job for job, _ in scored_listings]
        try:
            index_stats = self.index_jobs(jobs)
            logger.info(
                "Job indexing: %d new, %d cached, %d total chunks",
                index_stats["indexed"],
                index_stats["skipped"],
                index_stats["total_chunks"],
            )
        except EmbeddingError as e:
            logger.warning("Job indexing failed: %s, using heuristic-only", e)
            return self._fallback_to_heuristic(scored_listings)

        # Every candidate gets one score: the fused score when BM25 is on,
        # otherwise the dense similarity. A job with no score gets 0.0.
        semantic_scores = self._dense_scores(profile_embeddings, jobs)
        use_hybrid = (
            self.bm25_retriever is not None
            and self.config.bm25.enabled
            and self.config.rrf.enabled
        )
        if use_hybrid:
            semantic_scores = self._hybrid_retrieve(profile, jobs, semantic_scores)

        rag_scores: List[RAGMatchScore] = []

        for job, match_score in scored_listings:
            semantic_sim = semantic_scores.get(job.job_id, 0.0)

            combined = self._compute_combined_score(
                match_score.total_score, semantic_sim
            )

            recommendation = self._determine_recommendation(combined)

            rag_scores.append(
                RAGMatchScore(
                    job=job,
                    heuristic_score=match_score.total_score,
                    semantic_score=semantic_sim,
                    combined_score=combined,
                    heuristic_breakdown=match_score.breakdown,
                    matched_keywords=match_score.matched_keywords,
                    missing_skills=match_score.missing_skills,
                    recommendation=recommendation,
                    reasoning=self._build_reasoning(
                        match_score, semantic_sim, combined
                    ),
                    passed_threshold=combined
                    >= self.config.re_ranking.similarity_threshold,
                )
            )

        # Sort by combined score descending
        rag_scores.sort(key=lambda x: x.combined_score, reverse=True)

        # Apply final limit
        limit = self.config.re_ranking.final_limit
        if limit and len(rag_scores) > limit:
            rag_scores = rag_scores[:limit]

        return rag_scores

    def semantic_search(
        self,
        query: str,
        n_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search jobs by semantic similarity to a text query.

        Args:
            query: Natural language search query.
            n_results: Maximum results to return.

        Returns:
            List of matching jobs with similarity scores and metadata.
        """
        try:
            query_embedding = self.embedding_client.embed(query)
        except EmbeddingError:
            return []

        results = self.vector_store.query_similar(
            query_embedding=query_embedding,
            collection="jobs",
            n_results=n_results,
        )

        # Convert cosine similarity to readable format
        return [
            {
                "job_id": r["metadata"].get("job_id", ""),
                "section": r["metadata"].get("section", ""),
                "similarity": r["similarity"],
                "content_snippet": r["document"][:200] if r["document"] else "",
            }
            for r in results
            if r["similarity"] >= self.config.re_ranking.similarity_threshold
        ]

    def _dense_scores(
        self,
        profile_embeddings: List[List[float]],
        jobs: List[JobListing],
    ) -> Dict[str, float]:
        """Compute the dense similarity of each candidate job.

        Args:
            profile_embeddings: List of profile chunk embeddings.
            jobs: Candidate job listings.

        Returns:
            Dict mapping job_id to similarity. A job without embeddings is
            not in the dict.
        """
        scores: Dict[str, float] = {}
        for job in jobs:
            job_embeddings = self.vector_store.get_job_embeddings(job.job_id)
            if job_embeddings:
                scores[job.job_id] = self._compute_semantic_similarity(
                    profile_embeddings, job_embeddings
                )
        return scores

    def _bm25_job_scores(self, query: str, jobs: List[JobListing]) -> Dict[str, float]:
        """Score the candidate jobs with BM25, by the best chunk of each job.

        Builds the in-memory index again from the chunks of the candidates, so
        the index holds these jobs only: also the jobs that ``index_jobs``
        skips because they are in the vector store from an earlier run.

        Args:
            query: The BM25 query text.
            jobs: Candidate job listings.

        Returns:
            Dict mapping job_id to its best chunk score. A job with no query
            term is not in the dict.
        """
        retriever = self.bm25_retriever
        if retriever is None:
            return {}

        chunk_ids: List[str] = []
        chunk_texts: List[str] = []
        chunk_metadata: List[Dict[str, Any]] = []
        for job in jobs:
            for chunk in self.chunker.chunk_job(job):
                chunk_ids.append(f"{job.job_id}_chunk_{chunk.chunk_index}")
                chunk_texts.append(chunk.content)
                chunk_metadata.append({"job_id": job.job_id})
        retriever.index_documents(chunk_ids, chunk_texts, chunk_metadata)

        scores: Dict[str, float] = {}
        for result in retriever.query(query, n_results=retriever.doc_count):
            job_id = result.metadata["job_id"]
            if result.score > scores.get(job_id, 0.0):
                scores[job_id] = result.score
        return scores

    @staticmethod
    def _ranked_results(
        scores: Dict[str, float],
        documents: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """Order job scores best first as a result list for RRF.

        Args:
            scores: Job ID to score.
            documents: Job ID to the job's text.

        Returns:
            One result for each job, with ties in job ID order.
        """
        ordered = sorted(scores, key=lambda job_id: (-scores[job_id], job_id))
        return [{"doc_id": job_id, "document": documents[job_id]} for job_id in ordered]

    def _hybrid_retrieve(
        self,
        profile: UserProfile,
        jobs: List[JobListing],
        dense_scores: Dict[str, float],
    ) -> Dict[str, float]:
        """Fuse the dense and BM25 rankings of the candidate jobs.

        Each job is at most once in each ranking, so RRF gives a job one score
        from both rankings. An optional cross-encoder then reranks the fused
        jobs. The final scores are scaled to 0-1 over the fused jobs, so they
        are all on one scale.

        Args:
            profile: User profile to match against.
            jobs: Candidate job listings.
            dense_scores: Job ID to dense similarity, for the jobs that have
                embeddings.

        Returns:
            Dict mapping job_id to normalized score (0-1). A job without
            embeddings and without a BM25 term match is not in the dict.
        """
        profile_query_text = self._build_profile_query_text(profile)
        documents = {job.job_id: job.description or job.title for job in jobs}

        sparse_scores: Dict[str, float] = {}
        try:
            sparse_scores = self._bm25_job_scores(profile_query_text, jobs)
        except Exception as e:
            logger.warning("BM25 retrieval failed: %s", e)

        # RRF fusion
        rrf_config = self.config.rrf
        fused = reciprocal_rank_fusion(
            dense_results=self._ranked_results(dense_scores, documents),
            sparse_results=self._ranked_results(sparse_scores, documents),
            k=rrf_config.k,
            dense_weight=rrf_config.dense_weight,
            sparse_weight=rrf_config.sparse_weight,
        )

        # Optional cross-encoder reranking
        if self.cross_encoder and self.cross_encoder.is_available:
            rerank_input = [
                {"doc_id": r.doc_id, "document": r.document, "metadata": r.metadata}
                for r in fused
            ]
            reranked = self.cross_encoder.rerank(
                query=profile_query_text,
                results=rerank_input,
                top_k=self.config.cross_encoder.top_k,
            )
            # Rebuild fused from reranked results
            fused = [
                type(fused[0])(
                    doc_id=r["doc_id"],
                    rrf_score=r.get("cross_encoder_score", 0.0),
                    document=r.get("document", ""),
                    metadata=r.get("metadata", {}),
                )
                for r in reranked
            ]

        # Normalize the scores to 0-1 over the fused jobs
        if not fused:
            return {}

        max_score = max(r.rrf_score for r in fused)
        min_score = min(r.rrf_score for r in fused)
        score_range = max_score - min_score

        job_scores = {
            r.doc_id: (
                (r.rrf_score - min_score) / score_range
                if score_range > 0
                else (1.0 if r.rrf_score > 0 else 0.0)
            )
            for r in fused
        }

        logger.info(
            "Hybrid retrieval: %d dense + %d sparse -> %d jobs scored",
            len(dense_scores),
            len(sparse_scores),
            len(job_scores),
        )
        return job_scores

    def _build_profile_query_text(self, profile: UserProfile) -> str:
        """Build a text query from the user profile for BM25 retrieval.

        Joins the summary, the skill names, and the target keywords.

        Args:
            profile: User profile to extract query terms from.

        Returns:
            Space-separated query string.
        """
        parts: List[str] = [profile.summary] if profile.summary else []
        parts.extend(skill.name for skill in profile.skills)
        parts.extend(profile.targets.keywords)
        return " ".join(parts)

    def _compute_semantic_similarity(
        self,
        profile_embeddings: List[List[float]],
        job_embeddings: List[List[float]],
    ) -> float:
        """Compute semantic similarity between profile and job chunks.

        Uses average of max-similarities: for each profile chunk, find the
        most similar job chunk, then average those scores. This captures the
        best matching aspects of the job for each aspect of the profile.

        Args:
            profile_embeddings: List of profile chunk embeddings.
            job_embeddings: List of job chunk embeddings.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if not profile_embeddings or not job_embeddings:
            return 0.0

        profile_array = np.array(profile_embeddings)
        job_array = np.array(job_embeddings)

        # Normalize vectors for cosine similarity
        profile_norms = np.linalg.norm(profile_array, axis=1, keepdims=True)
        job_norms = np.linalg.norm(job_array, axis=1, keepdims=True)

        # Avoid division by zero
        profile_norms = np.where(profile_norms == 0, 1, profile_norms)
        job_norms = np.where(job_norms == 0, 1, job_norms)

        profile_normalized = profile_array / profile_norms
        job_normalized = job_array / job_norms

        # Compute similarity matrix: (n_profile, n_job)
        similarity_matrix = np.dot(profile_normalized, job_normalized.T)

        # For each profile chunk, find the max similarity to any job chunk
        max_similarities = np.max(similarity_matrix, axis=1)

        # Average the max similarities
        return float(np.mean(max_similarities))

    def _compute_combined_score(
        self,
        heuristic_score: int,
        semantic_score: float,
    ) -> float:
        """Compute weighted combined score.

        Normalizes heuristic to 0-1 range, then applies configured weights.

        Args:
            heuristic_score: Heuristic score (0-100).
            semantic_score: Semantic similarity (0-1).

        Returns:
            Combined score (0-1).
        """
        heuristic_weight = self.config.re_ranking.weights.get("heuristic", 0.4)
        semantic_weight = self.config.re_ranking.weights.get("semantic", 0.6)

        heuristic_normalized = heuristic_score / 100.0

        return (
            heuristic_weight * heuristic_normalized + semantic_weight * semantic_score
        )

    def _determine_recommendation(self, combined_score: float) -> str:
        """Determine action recommendation based on combined score.

        Args:
            combined_score: Combined heuristic + semantic score (0-1).

        Returns:
            Recommendation string: "apply", "maybe", or "skip".
        """
        if combined_score >= 0.7:
            return "apply"
        elif combined_score >= 0.5:
            return "maybe"
        else:
            return "skip"

    def _build_reasoning(
        self,
        match_score: MatchScore,
        semantic_sim: float,
        combined: float,
    ) -> str:
        """Build human-readable reasoning for a RAG match score.

        Args:
            match_score: Original heuristic match score.
            semantic_sim: Semantic similarity score.
            combined: Combined score.

        Returns:
            Reasoning string.
        """
        parts = [match_score.reasoning]

        if semantic_sim >= 0.7:
            parts.append(
                "Strong semantic alignment between profile and job description."
            )
        elif semantic_sim >= 0.5:
            parts.append("Moderate semantic similarity detected.")
        elif semantic_sim >= 0.3:
            parts.append("Partial semantic overlap with job requirements.")
        else:
            parts.append("Low semantic similarity between profile and job.")

        return " ".join(parts)

    def _fallback_to_heuristic(
        self,
        scored_listings: List[Tuple[JobListing, MatchScore]],
    ) -> List[RAGMatchScore]:
        """Gracefully degrade to heuristic-only scoring.

        Wraps heuristic MatchScore objects into RAGMatchScore objects
        with semantic_score=0.0.

        Args:
            scored_listings: Original heuristic-scored listings.

        Returns:
            List of RAGMatchScore with heuristic-only scoring.
        """
        results = [
            RAGMatchScore(
                job=job,
                heuristic_score=match_score.total_score,
                semantic_score=0.0,
                combined_score=match_score.total_score / 100.0,
                heuristic_breakdown=match_score.breakdown,
                matched_keywords=match_score.matched_keywords,
                missing_skills=match_score.missing_skills,
                recommendation=match_score.recommendation,
                reasoning=match_score.reasoning + " (RAG unavailable, heuristic-only)",
                passed_threshold=match_score.passed_threshold,
            )
            for job, match_score in scored_listings
        ]
        results.sort(key=lambda x: x.combined_score, reverse=True)
        return results
