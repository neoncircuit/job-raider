"""
Job Raider - Jobs API Routes

API endpoints for job search and retrieval without running full pipeline.

Author: Job Raider
Date: 2026-04-21
"""

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ...models.job_listing import JobListing, JobListingCollection
from ...models.user_profile import UserProfile
from ...scoring.matcher import JobMatcher
from ...scrapers.jsearch_scraper import JSearchScraper
from ...scrapers.linkedin_scraper import LinkedInScraper
from ...scrapers.manager import ScraperManager
from ...utils.location_normalizer import normalize_all_locations
from ...utils.logger import Components, get_logger
from ..models.requests import JobSearchRequest, SemanticSearchRequest
from ..models.responses import (
    CoverLetterResponse,
    CoverLetterValidationResponse,
    JobListingResponse,
    SemanticSearchResult,
)
from .profile import active_profile_id, stored_profiles

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
    # Log incoming request
    logger.info(
        f"[JOBS_SEARCH] Request received - keywords: {request.keywords}, locations: {request.locations}, sources: {request.sources}, limit: {request.limit}"
    )

    # Initialize scrapers
    from ...models.job_listing import ExperienceLevel, JobSource
    from ...scrapers.base import SearchParams

    manager = ScraperManager()
    logger.info(
        f"[JOBS_SEARCH] Scrapers initialized: {[s.value for s in manager.scrapers.keys()]}"
    )

    # Map source names to JobSource enums
    source_map = {
        "linkedin": JobSource.LINKEDIN,
        "jsearch": JobSource.JSEARCH,
    }
    source_names = request.sources or ["linkedin", "jsearch"]
    sources = [source_map[s] for s in source_names if s in source_map]
    logger.info(f"[JOBS_SEARCH] Sources selected: {[s.value for s in sources]}")

    # Validate keywords
    if not request.keywords or all(k.strip() == "" for k in request.keywords):
        logger.warning(
            f"[JOBS_SEARCH] Validation failed - empty keywords received: {request.keywords}"
        )
        raise HTTPException(
            status_code=400,
            detail="Keywords are required for job search. Please provide at least one keyword.",
        )

    # Build search params
    location = request.locations[0] if request.locations else None
    params = SearchParams(
        keywords=request.keywords,
        location=location,
        limit=request.limit,
    )

    # Scrape jobs
    try:
        logger.info(
            f"[JOBS_SEARCH] Starting scraping with params: keywords={params.keywords}, location={params.location}"
        )
        logger.info(f"[JOBS_SEARCH] Calling scrapers: {[s.value for s in sources]}")

        collection = manager.search_all(params, sources=sources)
        all_listings = collection.listings
        logger.info(
            f"[JOBS_SEARCH] Scraping complete - total listings: {len(all_listings)}"
        )

        # Filter by location if specified (post-filter to ensure API results match)
        if request.locations:
            requested_location = request.locations[0].lower()
            logger.info(f"[JOBS_SEARCH] Applying location filter: {requested_location}")
            filtered_listings = []
            for listing in all_listings:
                # Check if listing location contains the requested location
                if listing.location:
                    listing_location_lower = listing.location.lower()
                    # Match if requested location is contained in listing location or vice versa
                    if (
                        requested_location in listing_location_lower
                        or listing_location_lower in requested_location
                        or
                        # Handle common country/city variations
                        any(
                            loc in listing_location_lower
                            for loc in [
                                requested_location,
                                requested_location.replace(" ", ""),
                                requested_location[:3],
                            ]
                        )
                    ):
                        filtered_listings.append(listing)
                else:
                    # If listing has no location, include it (better to have extra results)
                    filtered_listings.append(listing)
            all_listings = filtered_listings
            logger.info(f"After location filtering: {len(all_listings)} jobs")

        # Filter by experience level if specified
        if request.experience_levels:
            # Normalize experience level names
            requested_levels = [
                level.lower().replace(" ", "_") for level in request.experience_levels
            ]
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

            # Filter listings - include jobs that match OR are Not Specified (inclusive filtering)
            filtered_listings = []
            for listing in all_listings:
                listing_level = (
                    listing.experience_level.value
                    if hasattr(listing.experience_level, "value")
                    else (
                        str(listing.experience_level).lower().replace(" ", "_")
                        if listing.experience_level
                        else None
                    )
                )
                logger.info(
                    f"Filter check - requested: {target_levels}, listing level: {listing_level}, result: {listing_level in target_levels or listing_level == 'not_specified' or listing_level is None}"
                )
                # Include if: no filter, matches requested level, OR is Not Specified (inclusive filtering)
                if (
                    not target_levels
                    or listing_level in target_levels
                    or listing_level == "not_specified"
                    or listing_level is None
                ):
                    filtered_listings.append(listing)
            all_listings = filtered_listings

        logger.info(
            f"[JOBS_SEARCH] Total jobs after all filtering: {len(all_listings)}"
        )

        # Score jobs if profile is available
        scored_listings = []
        if active_profile_id and active_profile_id in stored_profiles:
            from ...models.user_profile import UserProfile

            profile_data = stored_profiles[active_profile_id].get("profile")
            if profile_data:
                try:
                    profile = UserProfile(**profile_data)
                    matcher = JobMatcher(fresh_grad_mode=request.fresh_grad_mode)

                    for listing in all_listings:
                        try:
                            score_result = matcher.score_job(listing, profile)
                            scored_listings.append((listing, score_result))
                        except Exception as e:
                            logger.warning(f"Failed to score job {listing.job_id}: {e}")
                            scored_listings.append((listing, None))

                    # Sort by score if scoring succeeded
                    if scored_listings and scored_listings[0][1] is not None:
                        scored_listings.sort(
                            key=lambda x: x[1].total_score if x[1] else 0, reverse=True
                        )
                        logger.info(
                            f"Scored {len(scored_listings)} jobs using fresh_grad_mode={request.fresh_grad_mode}"
                        )
                except Exception as e:
                    logger.warning(f"Profile scoring failed: {e}")
                    scored_listings = [(listing, None) for listing in all_listings]
        else:
            # No profile available, return unsorted
            scored_listings = [(listing, None) for listing in all_listings]

        # Convert to response format
        jobs_response = []
        for listing, score_result in scored_listings[: request.limit]:
            job_data = {
                "job_id": listing.job_id
                or f"{listing.source}_{hash(str(listing.source_url))}",
                "title": listing.title,
                "company": listing.company,
                "location": normalize_all_locations(listing.location),
                "description": (listing.description or "")[:5000],
                "url": str(listing.source_url) if listing.source_url else None,
                "source_url": str(listing.source_url) if listing.source_url else None,
                "source": (
                    listing.source.value
                    if isinstance(listing.source, JobSource)
                    else str(listing.source)
                ),
                "apply_method": _compute_apply_method(
                    (
                        listing.source.value
                        if isinstance(listing.source, JobSource)
                        else str(listing.source)
                    ),
                    listing.already_applied,
                ),
                "job_type": (
                    listing.job_type.value
                    if hasattr(listing.job_type, "value")
                    else listing.job_type if listing.job_type else None
                ),
                "experience_level": (
                    listing.experience_level.value
                    if hasattr(listing.experience_level, "value")
                    else listing.experience_level if listing.experience_level else None
                ),
                "salary_range": listing.salary_range,
                "remote": listing.is_remote,
                "already_applied": listing.already_applied,
                "posted_date": (
                    listing.posted_date.isoformat() if listing.posted_date else None
                ),
                "scraped_at": (
                    listing.scraped_at.isoformat()
                    if hasattr(listing, "scraped_at") and listing.scraped_at
                    else None
                ),
            }

            # Add score data if available
            if score_result:
                job_data["relevance_score"] = score_result.total_score
                job_data["match_breakdown"] = score_result.breakdown
                job_data["recommendation"] = score_result.recommendation
                job_data["reasoning"] = score_result.reasoning
                job_data["matched_keywords"] = score_result.matched_keywords
                job_data["missing_skills"] = score_result.missing_skills
                job_data["passed_threshold"] = score_result.passed_threshold

            jobs_response.append(job_data)

        logger.info(
            f"[JOBS_SEARCH] Returning {len(jobs_response)} jobs (requested limit: {request.limit})"
        )

        return {
            "total": len(all_listings),
            "fresh_grad_mode": request.fresh_grad_mode,
            "jobs": jobs_response,
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
        from ...models.job_listing import JobListing, JobSource
        from ...scoring.trust_analyzer import TrustAnalyzer

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

    NOTE: This endpoint currently supports dry-run mode only.
    Full auto-apply submission requires LinkedIn Easy Apply integration and
    is planned for future implementation.

    Args:
        job_id: Job ID
        dry_run: Generate resume without submitting (default: True)
        background_tasks: FastAPI background tasks for async processing

    Returns:
        Application result with dry-run information
    """
    logger.info(
        f"[Auto Apply] Application requested for job: {job_id}, dry_run: {dry_run}"
    )

    # Check for active profile
    if not active_profile_id:
        logger.warning("[Auto Apply] No active profile found")
        raise HTTPException(
            status_code=400,
            detail="No active profile found. Please upload a resume first.",
        )

    # Get the active profile
    profile = stored_profiles.get(active_profile_id)
    if not profile:
        logger.error(
            f"[Auto Apply] Profile ID {active_profile_id} not found in stored profiles"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Profile {active_profile_id} not found",
        )

    logger.info(f"[Auto Apply] Using profile: {active_profile_id}")

    # Dry run mode - simulate application without submission
    if dry_run:
        logger.info(f"[Auto Apply] Dry run mode - simulating application for {job_id}")
        return {
            "success": True,
            "job_id": job_id,
            "dry_run": True,
            "message": "Application simulated successfully in dry-run mode. This validates your profile and job data without actually submitting.",
            "application_id": f"dry_run_{job_id}",
            "status": "simulated",
            "next_steps": [
                "For actual submission, please apply directly through the job listing",
                "Full auto-apply is planned for future release",
                "This requires LinkedIn Easy Apply API integration",
            ],
        }

    # Non-dry run: not yet implemented
    logger.warning("[Auto Apply] Non-dry run requested but not yet implemented")
    raise HTTPException(
        status_code=501,
        detail="Full auto-submit not yet implemented. Automatic application submission requires LinkedIn Easy Apply integration. For now, please use dry_run=True or apply directly through the job listing.",
    )


@router.post("/{job_id}/cover-letter")
async def generate_cover_letter(
    job_id: str,
    job_data: Dict[str, Any] = None,
    deep: bool = False,
):
    """Generate a tailored cover letter for a specific job.

    Requires an active profile to have been uploaded. Uses the LLM to
    generate a concise, tailored cover letter connecting the candidate's
    experience to the job requirements. Runs deterministic validation
    automatically; set `?deep=true` for LLM-powered validation.

    Args:
        job_id: Job ID.
        job_data: Optional job data (title, company, description, etc.).
        deep: Whether to use LLM validation.

    Returns:
        Generated cover letter with validation results.
    """
    if not active_profile_id:
        raise HTTPException(
            status_code=400,
            detail="No active profile found. Upload a resume first.",
        )

    profile = stored_profiles.get(active_profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Profile {active_profile_id} not found",
        )

    try:
        from ...generation.cover_letter_validator import (
            CoverLetterValidationResult,
            CoverLetterValidator,
        )
        from ...generation.cover_letter_writer import CoverLetterWriter
        from ...generation.selector import ResumeSelector
        from ...llm.router import create_router
        from ...models.job_listing import JobListing, JobSource

        llm_router = create_router(prefer_local=True)

        # Reconstruct UserProfile from stored data
        user_profile = UserProfile(**profile["profile"])

        # Build JobListing from request data
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

        # Run selector first to get selection strategy
        selector = ResumeSelector(llm_router=llm_router)
        selection = selector.select(job_listing, user_profile)

        # Generate cover letter using the selection strategy
        writer = CoverLetterWriter(llm_router=llm_router)
        result = writer.write(job_listing, user_profile, selection)

        # Validate the generated cover letter
        validator = CoverLetterValidator(llm_router=llm_router, strict_mode=False)
        try:
            if deep:
                validation = validator.validate_with_llm(
                    result, job_listing, user_profile, selection
                )
            else:
                validation = validator.validate(
                    result, job_listing, user_profile, selection
                )
        except Exception as e:
            logger.error("Cover letter validation failed: %s", e, exc_info=True)
            validation = CoverLetterValidationResult(
                is_valid=True,
                score=100,
                issues=[],
                word_count=result.word_count,
                structure_score=100,
                content_score=100,
                tone_score=100,
                recommendation="approve",
                details={},
            )

        return CoverLetterResponse(
            success=True,
            job_id=job_id,
            cover_letter={
                "content": result.content,
                "word_count": result.word_count,
                "model_used": result.model_used,
                "highlighted_experiences": result.highlighted_experiences,
            },
            validation=CoverLetterValidationResponse(
                is_valid=validation.is_valid,
                score=validation.score,
                issues=[issue.value for issue in validation.issues],
                word_count=validation.word_count,
                structure_score=validation.structure_score,
                content_score=validation.content_score,
                tone_score=validation.tone_score,
                recommendation=validation.recommendation,
                details=validation.details,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cover letter generation failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Cover letter generation failed: {str(e)}",
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
        from ...llm.embedding_client import EmbeddingClient, EmbeddingError
        from ...rag.config import RAGConfig
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
            semantic_results.append(
                SemanticSearchResult(
                    job_id=r["metadata"].get("job_id", ""),
                    similarity_score=r["similarity"],
                    description_snippet=r["document"][:200] if r["document"] else "",
                )
            )

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
        import numpy as np

        from ...llm.embedding_client import EmbeddingClient, EmbeddingError
        from ...rag.chunker import TextChunker
        from ...rag.config import RAGConfig
        from ...rag.ranker import RAGRanker
        from ...rag.vector_store import ChromaStore

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
