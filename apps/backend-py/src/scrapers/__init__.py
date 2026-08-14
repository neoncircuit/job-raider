"""
Job Raider - Scrapers Module

This module provides job board scrapers for LinkedIn, JSearch, and
MyCareersFuture.

Author: Job Raider
Date: 2026-04-20
"""

from .base import (
    AuthenticationError,
    BaseScraper,
    RateLimitError,
    ScraperError,
    ScrapingException,
    SearchParams,
)
from .jsearch_scraper import JSearchScraper
from .linkedin_scraper import LinkedInScraper
from .manager import ScraperManager
from .mycareersfuture_scraper import MyCareersFutureScraper, mcf_enabled
from .storage import JobListingStorage

__all__ = [
    # Base
    "BaseScraper",
    "SearchParams",
    "ScraperError",
    "RateLimitError",
    "AuthenticationError",
    "ScrapingException",
    # Scrapers
    "LinkedInScraper",
    "JSearchScraper",
    "MyCareersFutureScraper",
    "mcf_enabled",
    # Manager
    "ScraperManager",
    # Storage
    "JobListingStorage",
]
