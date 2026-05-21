"""
Job Raider - Jobs API Routes

API endpoints for job search and retrieval without running full pipeline.

Author: Job Raider
Date: 2026-04-21
"""

import asyncio
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel

from ...models.job_listing import JobListing, JobListingCollection
from ...scrapers.manager import ScraperManager
from ...scrapers.linkedin_scraper import LinkedInScraper
from ...scrapers.jsearch_scraper import JSearchScraper
from ...scoring.matcher import JobMatcher
from ...models.user_profile import UserProfile
from ...utils.logger import get_logger, Components
from ...utils.location_normalizer import normalize_all_locations
from ..models.requests import JobSearchRequest, SemanticSearchRequest
from ..models.responses import JobListingResponse, SemanticSearchResult
from .profile import stored_profiles, active_profile_id

router = APIRouter()
logger = get_logger(Components.SCRAPERS)


def _compute_apply_method(source: str, already_applied: bool) -> str:
    """Return a lightweight apply-method heuristic based on job source.

    No HTML fetching — uses source and already-applied state only.

    Args:
        source: Job source string (e.g. "linkedin", "jsearch").
        already_applied: Whether the user has already applied.

    Returns:
        One of "already_applied", "external_site", or "easy_apply".
    """
    if already_applied:
        return "already_applied"
    if source == "jsearch":
        return "external_site"
    return "easy_apply"


@router.get("/sources")
async def get_sources():
    """Return the list of available job scraper sources.

    Sources are derived from ScraperManager's registered scrapers,
    which is the single source of truth for available job boards.

    Returns:
        Dict with 'sources' list of source name strings.
    """
    manager = ScraperManager()
    return {"sources": [s.value for s in manager.scrapers.keys()]}


@router.post("/search")
async def search_jobs(
    request: JobSearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Quick job search without running full pipeline.

    Scrapes job listings from specified sources based on keywords
    and locations. Returns raw listings without scoring or filtering.

    Args:
        request: Job search parameters
        background_tasks: FastAPI background tasks

    Returns:
        List of job listings
    """
    # Initialize scrapers
    from ...scrapers.base import SearchParams
    from ...models.job_listing import JobSource, ExperienceLevel

    manager = ScraperManager()

    # Map source names to JobSource enums
    source_map = {
        "linkedin": JobSource.LINKEDIN,
        "jsearch": JobSource.JSEARCH,
    }
    source_names = request.sources or ["linkedin", "jsearch"]
    sources = [source_map[s] for s in source_names if s in source_map]

    # Build search params
    location = request.locations[0] if request.locations else None
    params = SearchParams(
        keywords=request.keywords,
        location=location,
        limit=request.limit,
    )

    # Scrape jobs
    try:
        logger.info(f"Starting job search: keywords={request.keywords}, locations={request.locations}, experience_levels={request.experience_levels}")

        collection = manager.search_all(params, sources=sources)
        all_listings = collection.listings

        # Filter by experience level if specified
        if request.experience_levels:
            # Normalize experience level names
            requested_levels = [level.lower().replace(" ", "_") for level in request.experience_levels]
            # Map frontend names to backend enum values
            level_map = {
                "entry_level": "entry_level",
                "entry level": "entry_level",
                "mid_level": "mid_level",
                "mid level": "mid_level",
                "senior": "senior",
                "lead": "lead",
                "internship": "internship",
                "not_specified": "not_specified",
            }
            target_levels = set()
            for level in requested_levels:
                normalized = level.replace(" ", "_")
                if normalized in [e.value for e in ExperienceLevel]:
                    target_levels.add(normalized)
                elif level in level_map:
                    target_levels.add(level_map[level])

            # Filter listings
            filtered_listings = []
            for listing in all_listings:
                listing_level = listing.experience_level.value if hasattr(listing.experience_level, "value") else str(listing.experience_level).lower().replace(" ", "_") if listing.experience_level else None
                if not target_levels or listing_level in target_levels or listing_level is None:
                    filtered_listings.append(listing)
            all_listings = filtered_listings

        logger.info(f"Found {len(all_listings)} jobs after filtering")

        # Convert to response format
        return {
            "total": len(all_listings),
            "jobs": [
                {
                    "job_id": listing.job_id or f"{listing.source}_{hash(str(listing.source_url))}",
                    "title": listing.title,
                    "company": listing.company,
                    "location": normalize_all_locations(listing.location),
                    "description": (listing.description or "")[:5000],
                    "url": str(listing.source_url) if listing.source_url else None,
                    "source_url": str(listing.source_url) if listing.source_url else None,
                    "source": listing.source.value if isinstance(listing.source, JobSource) else str(listing.source),
                    "apply_method": _compute_apply_method(
                        listing.source.value if isinstance(listing.source, JobSource) else str(listing.source),
                        listing.already_applied,
                    ),
                    "job_type": listing.job_type.value if hasattr(listing.job_type, "value") else listing.job_type if listing.job_type else None,
                    "experience_level": listing.experience_level.value if hasattr(listing.experience_level, "value") else listing.experience_level if listing.experience_level else None,
                    "salary_range": listing.salary_range,
                    "remote": listing.is_remote,
                    "already_applied": listing.already_applied,
                    "posted_date": listing.posted_date.isoformat() if listing.posted_date else None,
                    "scraped_at": listing.scraped_at.isoformat() if hasattr(listing, 'scraped_at') and listing.scraped_at else None,
                }
                for listing in all_listings[:request.limit]
            ],
        }

    except Exception as e:
        logger.error(f"Job search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Job search failed: {str(e)}",
        )


@router.get("/{job_id}")
async def get_job(job_id: str):
    """
    Get details for a specific job.

    Args:
        job_id: Job ID

    Returns:
        Job listing details
    """
    # TODO: Implement job storage and retrieval
    # For now, return error
    raise HTTPException(
        status_code=501,
        detail="Job retrieval not yet implemented",
    )


@router.post("/{job_id}/score")
async def score_job(job_id: str):
    """
    Get relevance score for a specific job.

    Requires active profile to be loaded.

    Args:
        job_id: Job ID

    Returns:
        Job with relevance score
    """
    if not active_profile_id:
        raise HTTPException(
            status_code=400,
            detail="No active profile found. Upload a resume first.",
        )

    # TODO: Implement job scoring
    # For now, return error
    raise HTTPException(
        status_code=501,
        detail="Job scoring not yet implemented",
    )


@router.post("/{job_id}/classify")
async def classify_job(job_id: str, job_data: Dict[str, Any] = None):
    """
    Classify a job listing with rich metadata using LLM.

    Analyzes job description to extract detailed classifications including:
    - Industry and role category
    - Company size estimation
    - Work environment (pace, team structure)
    - Detailed skill breakdown (technical, soft, domain)
    - Experience validation
    - Management level and impact scope
    - Red flags and concerns

    Args:
        job_id: Job ID
        job_data: Optional job data (title, company, description, etc.)

    Returns:
        Job classification with rich metadata
    """
    try:
        from ...classifiers.job_classifier import JobClassifier
        from ...llm.router import create_router
        from ...models.job_listing import JobListing, JobSource

        # Initialize classifier with LLM router
        llm_router = create_router(prefer_local=True)
        classifier = JobClassifier(llm_router=llm_router)

        # Create job listing from provided data
        if job_data:
            job_listing = JobListing(
                title=job_data.get("title", "Unknown"),
                company=job_data.get("company", "Unknown"),
                job_id=job_id,
                source=JobSource(job_data.get("source", "manual")),
                description=job_data.get("description", ""),
                location=job_data.get("location"),
            )
        else:
            # Default fallback if no data provided
            job_listing = JobListing(
                title="Software Engineer",
                company="Unknown",
                job_id=job_id,
                source=JobSource.MANUAL,
                description="No description provided",
            )

        result = classifier.classify(job_listing, use_llm=True)

        if not result.success or not result.classification:
            raise HTTPException(
                status_code=500,
                detail=f"Classification failed: {', '.join(result.errors)}",
            )

        # Convert classification to dict for response
        classification_dict = result.classification.model_dump()

        return {
            "success": True,
            "job_id": job_id,
            "classification": classification_dict,
            "warnings": result.warnings,
        }

    except Exception as e:
        logger.error(f"Job classification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}",
        )


@router.post("/{job_id}/trust-analysis")
async def trust_analysis(
    job_id: str,
    job_data: Dict[str, Any] = None,
    deep: bool = False,
):
    """
    Analyze trustworthiness of a job listing.

    Runs rule-based scam detection with per-category scoring and
    optional LLM-enhanced analysis for subtle signals.

    Returns a trust tier (legitimate/low_risk/moderate_risk/suspicious/likely_scam),
    confidence score, per-category breakdown, and specific reasons for the rating.

    Args:
        job_id: Job ID
        job_data: Optional job data (title, company, description, location, source)
        deep: If True, run LLM-enhanced analysis for deeper evaluation

    Returns:
        Trust analysis with tier, confidence, reasons, and category scores
    """
    try:
        from ...scoring.trust_analyzer import TrustAnalyzer
        from ...models.job_listing import JobListing, JobSource

        llm_router = None
        if deep:
            from ...llm.router import create_router

            llm_router = create_router(prefer_local=True)

        analyzer = TrustAnalyzer(llm_router=llm_router)

        if job_data:
            job_listing = JobListing(
                title=job_data.get("title", "Unknown"),
                company=job_data.get("company", "Unknown"),
                job_id=job_id,
                source=JobSource(job_data.get("source", "manual")),
                description=job_data.get("description", ""),
                location=job_data.get("location"),
            )
        else:
            job_listing = JobListing(
                title="Unknown",
                company="Unknown",
                job_id=job_id,
                source=JobSource.MANUAL,
            )

        result = analyzer.analyze(job_listing, deep=deep)

        return {
            "success": True,
            "job_id": job_id,
            "trust_analysis": {
                "tier": result.tier.value,
                "tier_display": result.tier.display_name,
                "confidence": result.confidence,
                "risk_score": result.risk_score,
                "is_scam": result.is_scam,
                "category_scores": result.category_scores,
                "indicators": [i.value for i in result.indicators],
                "reasons": result.reasons,
                "llm_summary": result.llm_summary,
                "llm_indicators": result.llm_indicators,
            },
        }

    except Exception as e:
        logger.error(f"Trust analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Trust analysis failed: {str(e)}",
        )


@router.post("/{job_id}/apply")
async def apply_to_job(
    job_id: str,
    dry_run: bool = True,
    background_tasks: BackgroundTasks = None,
):
    """
    Apply to a specific job.

    Generates tailored resume and submits application.

    Args:
        job_id: Job ID
        dry_run: Generate resume without submitting
        background_tasks: FastAPI background tasks for async processing

    Returns:
        Application result
    """
    logger.info(f"[Auto Apply] Application requested for job: {job_id}, dry_run: {dry_run}")

    # Check for active profile
    if not active_profile_id:
        logger.warning("[Auto Apply] No active profile found")
        raise HTTPException(
            status_code=400,
            detail="No active profile found. Upload a resume first.",
        )

    # Get the active profile
    profile = stored_profiles.get(active_profile_id)
    if not profile:
        logger.error(f"[Auto Apply] Profile ID {active_profile_id} not found in stored profiles")
        raise HTTPException(
            status_code=404,
            detail=f"Profile {active_profile_id} not found",
        )

    logger.info(f"[Auto Apply] Using profile: {active_profile_id}")

    # For now, return a successful response with dry-run information
    # Full implementation will include:
    # - Detect apply method (Easy Apply vs External)
    # - Parse application questions
    # - Generate answers from profile
    # - Submit application

    if dry_run:
        logger.info(f"[Auto Apply] Dry run mode - simulating application for {job_id}")
        return {
            "success": True,
            "job_id": job_id,
            "dry_run": True,
            "message": "Dry run: Application simulated successfully. Full auto-apply coming soon.",
            "application_id": f"dry_run_{job_id}",
            "status": "simulated",
            "next_steps": [
                "Full auto-apply implementation in progress",
                "Will detect Easy Apply vs External applications",
                "Will parse and answer application questions automatically",
            ]
        }

    # Non-dry run: not yet implemented
    logger.warning("[Auto Apply] Non-dry run not yet implemented")
    raise HTTPException(
        status_code=501,
        detail="Full auto-submit not yet implemented. Use dry_run=true for now.",
    )


@router.post("/search/semantic")
async def semantic_search(request: SemanticSearchRequest):
    """Search jobs by semantic similarity to a natural language query.

    Uses the RAG pipeline to find jobs matching the query intent,
    not just keywords. Requires embedding model to be available.

    Args:
        request: Semantic search query and parameters.

    Returns:
        List of jobs ranked by semantic similarity.
    """
    try:
        from ...rag.config import RAGConfig
        from ...llm.embedding_client import EmbeddingClient, EmbeddingError
        from ...rag.vector_store import ChromaStore

        rag_config = RAGConfig.from_yaml("config/rag_config.yaml")
        embedding_client = EmbeddingClient(model=rag_config.embedding.model)

        if not embedding_client.is_model_available():
            raise HTTPException(
                status_code=503,
                detail="Embedding model not available. Pull 'nomic-embed-text' first.",
            )

        # Initialize vector store
        vector_store = ChromaStore(rag_config.vector_store)
        vector_store.initialize()

        # Generate query embedding
        query_embedding = embedding_client.embed(request.query)

        # Search
        results = vector_store.query_similar(
            query_embedding=query_embedding,
            collection="jobs",
            n_results=request.n_results,
            filter_criteria=request.filters,
        )

        # Deduplicate by job_id (keep highest similarity)
        seen: dict = {}
        for r in results:
            job_id = r["metadata"].get("job_id", "")
            sim = r["similarity"]
            if sim < request.min_similarity:
                continue
            if job_id not in seen or sim > seen[job_id]["similarity"]:
                seen[job_id] = r

        # Format response
        semantic_results = []
        for r in sorted(seen.values(), key=lambda x: x["similarity"], reverse=True):
            semantic_results.append(SemanticSearchResult(
                job_id=r["metadata"].get("job_id", ""),
                similarity_score=r["similarity"],
                description_snippet=r["document"][:200] if r["document"] else "",
            ))

        return {
            "query": request.query,
            "total": len(semantic_results),
            "results": [r.model_dump() for r in semantic_results],
        }

    except HTTPException:
        raise
    except EmbeddingError as e:
        raise HTTPException(status_code=503, detail=f"Embedding service error: {e}")
    except Exception as e:
        logger.error("Semantic search failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {e}")


@router.get("/{job_id}/similarity")
async def get_job_similarity(job_id: str):
    """Get semantic similarity score for a job against the user profile.

    Args:
        job_id: Job ID to score.

    Returns:
        Similarity score and breakdown.
    """
    if not active_profile_id:
        raise HTTPException(
            status_code=400,
            detail="No active profile found. Upload a resume first.",
        )

    try:
        from ...rag.config import RAGConfig
        from ...llm.embedding_client import EmbeddingClient, EmbeddingError
        from ...rag.vector_store import ChromaStore
        from ...rag.ranker import RAGRanker
        from ...rag.chunker import TextChunker
        import numpy as np

        rag_config = RAGConfig.from_yaml("config/rag_config.yaml")
        embedding_client = EmbeddingClient(model=rag_config.embedding.model)
        vector_store = ChromaStore(rag_config.vector_store)
        vector_store.initialize()

        # Get profile embeddings
        profile_embeddings = vector_store.get_profile_embeddings("default")
        if not profile_embeddings:
            raise HTTPException(
                status_code=400,
                detail="Profile not indexed. Run the pipeline first.",
            )

        # Get job embeddings
        job_embeddings = vector_store.get_job_embeddings(job_id)
        if not job_embeddings:
            raise HTTPException(
                status_code=404,
                detail=f"Job '{job_id}' not found in vector store.",
            )

        # Compute similarity
        profile_array = np.array(profile_embeddings)
        job_array = np.array(job_embeddings)

        profile_norms = np.linalg.norm(profile_array, axis=1, keepdims=True)
        job_norms = np.linalg.norm(job_array, axis=1, keepdims=True)
        profile_norms = np.where(profile_norms == 0, 1, profile_norms)
        job_norms = np.where(job_norms == 0, 1, job_norms)

        similarity_matrix = np.dot(
            profile_array / profile_norms,
            (job_array / job_norms).T,
        )
        semantic_score = float(np.mean(np.max(similarity_matrix, axis=1)))

        return {
            "job_id": job_id,
            "semantic_score": round(semantic_score, 4),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Similarity check failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Similarity check failed: {e}")
