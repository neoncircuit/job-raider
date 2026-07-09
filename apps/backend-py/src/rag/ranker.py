"""
Job Raider - RAG Ranker

Re-ranks job candidates using semantic similarity from vector embeddings.
Combines heuristic scores with RAG-based semantic matching for hybrid scoring.

Author: Job Raider
Date: 2026-04-26
"""

import logging
from dataclasses import dataclass, field
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
        semantic_score: Cosine similarity from vector embeddings (0.0-1.0).
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

        # Also index chunks into BM25 for hybrid retrieval
        if self.bm25_retriever and self.config.bm25.enabled:
            bm25_ids = []
            bm25_docs = []
            bm25_metas = []
            for job, chunks in zip(valid_jobs, valid_chunks):
                for chunk in chunks:
                    bm25_ids.append(f"{job.job_id}_chunk_{chunk.chunk_index}")
                    bm25_docs.append(chunk.content)
                    bm25_metas.append(
                        {"job_id": job.job_id, "section": chunk.section or ""}
                    )
            if bm25_ids:
                self.bm25_retriever.add_documents(bm25_ids, bm25_docs, bm25_metas)
                logger.debug("Indexed %d chunks into BM25", len(bm25_ids))

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

        # Also index profile chunks into BM25
        if self.bm25_retriever and self.config.bm25.enabled:
            bm25_ids = [
                f"profile_{profile_id}_chunk_{c.chunk_index}" for c in valid_chunks
            ]
            bm25_docs = [c.content for c in valid_chunks]
            bm25_metas = [
                {"profile_id": profile_id, "section": c.section or ""}
                for c in valid_chunks
            ]
            self.bm25_retriever.add_documents(bm25_ids, bm25_docs, bm25_metas)

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

        # Compute semantic similarity for each job
        # Use hybrid retrieval when BM25 is available, otherwise dense-only
        use_hybrid = (
            self.bm25_retriever is not None
            and self.config.bm25.enabled
            and self.config.rrf.enabled
        )

        if use_hybrid:
            hybrid_scores = self._hybrid_retrieve(profile, jobs)
        else:
            hybrid_scores = None

        rag_scores: List[RAGMatchScore] = []

        for job, match_score in scored_listings:
            # Use hybrid score if available, otherwise compute dense-only
            if use_hybrid and hybrid_scores and job.job_id in hybrid_scores:
                semantic_sim = hybrid_scores[job.job_id]
            else:
                # Dense-only fallback for this specific job
                job_embeddings = self.vector_store.get_job_embeddings(job.job_id)
                if not job_embeddings:
                    semantic_sim = 0.0
                else:
                    semantic_sim = self._compute_semantic_similarity(
                        profile_embeddings, job_embeddings
                    )

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

    def _hybrid_retrieve(
        self,
        profile: UserProfile,
        jobs: List[JobListing],
    ) -> Dict[str, float]:
        """Perform hybrid retrieval: dense + sparse via RRF, with optional reranking.

        Builds a profile query from the user profile, runs both dense (ChromaDB)
        and sparse (BM25) retrieval, fuses via RRF, and optionally reranks with
        a cross-encoder. Returns normalized scores mapped to job IDs.

        Args:
            profile: User profile to match against.
            jobs: Job listings to score.

        Returns:
            Dict mapping job_id to normalized semantic score (0-1).
        """
        profile_query_text = self._build_profile_query_text(profile)
        n_results = self.config.bm25.n_results

        # Dense retrieval via ChromaDB
        dense_results: List[Dict[str, Any]] = []
        try:
            profile_embedding = self._get_profile_query_embedding()
            if profile_embedding:
                raw_results = self.vector_store.query_similar(
                    query_embedding=profile_embedding,
                    collection="jobs",
                    n_results=n_results,
                )
                dense_results = [
                    {
                        "doc_id": r["metadata"].get("job_id", ""),
                        "document": r["document"],
                        "metadata": r["metadata"],
                    }
                    for r in raw_results
                ]
        except Exception as e:
            logger.warning("Dense retrieval failed in hybrid mode: %s", e)

        # Sparse retrieval via BM25
        sparse_results: List[Dict[str, Any]] = []
        if self.bm25_retriever and self.bm25_retriever.doc_count > 0:
            try:
                bm25_results = self.bm25_retriever.query(
                    profile_query_text, n_results=n_results
                )
                sparse_results = [
                    {
                        "doc_id": r.doc_id,
                        "document": r.document,
                        "metadata": r.metadata,
                    }
                    for r in bm25_results
                ]
            except Exception as e:
                logger.warning("BM25 retrieval failed: %s", e)

        # RRF fusion
        rrf_config = self.config.rrf
        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
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

        # Normalize RRF scores to 0-1 and map to job IDs
        if not fused:
            return {}

        max_score = max(r.rrf_score for r in fused)
        min_score = min(r.rrf_score for r in fused)
        score_range = max_score - min_score

        job_scores: Dict[str, float] = {}
        for r in fused:
            job_id = r.metadata.get("job_id") or r.doc_id.split("_chunk_")[0]
            normalized = (
                (r.rrf_score - min_score) / score_range
                if score_range > 0
                else (1.0 if r.rrf_score > 0 else 0.0)
            )
            # Keep the highest score per job (a job may have multiple chunks)
            if job_id not in job_scores or normalized > job_scores[job_id]:
                job_scores[job_id] = normalized

        logger.info(
            "Hybrid retrieval: %d dense + %d sparse -> %d fused -> %d jobs scored",
            len(dense_results),
            len(sparse_results),
            len(fused),
            len(job_scores),
        )
        return job_scores

    def _get_profile_query_embedding(self) -> Optional[List[float]]:
        """Get a single query embedding representing the profile.

        Averages all profile chunk embeddings into a centroid vector.

        Returns:
            List of floats representing the profile query embedding,
            or None if no embeddings are available.
        """
        profile_embeddings = self.vector_store.get_profile_embeddings("default")
        if not profile_embeddings:
            return None

        profile_array = np.array(profile_embeddings)
        centroid = np.mean(profile_array, axis=0)
        return centroid.tolist()

    def _build_profile_query_text(self, profile: UserProfile) -> str:
        """Build a text query from the user profile for BM25 retrieval.

        Concatenates the most relevant profile fields into a single
        query string optimized for lexical matching.

        Args:
            profile: User profile to extract query terms from.

        Returns:
            Space-separated query string.
        """
        parts: List[str] = []

        if hasattr(profile, "professional_summary") and profile.professional_summary:
            parts.append(profile.professional_summary)

        if hasattr(profile, "skills") and profile.skills:
            if isinstance(profile.skills, list):
                skill_names = [
                    s.name if hasattr(s, "name") else str(s) for s in profile.skills
                ]
                parts.extend(skill_names)
            elif isinstance(profile.skills, dict):
                for category, skills in profile.skills.items():
                    if isinstance(skills, list):
                        parts.extend(
                            [s.name if hasattr(s, "name") else str(s) for s in skills]
                        )

        if hasattr(profile, "target_job") and profile.target_job:
            target = profile.target_job
            if hasattr(target, "keywords") and target.keywords:
                parts.extend(target.keywords)
            if hasattr(target, "title") and target.title:
                parts.append(target.title)

        return " ".join(parts) if parts else ""

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
