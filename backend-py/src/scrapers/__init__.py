"""
Job Raider - Scrapers Module

This module provides job board scrapers for LinkedIn and JSearch API.

Author: Job Raider
Date: 2026-04-20
"""

from .base import (
    BaseScraper,
    SearchParams,
    ScraperError,
    RateLimitError,
    AuthenticationError,
    ScrapingException,
)

from .linkedin_scraper import LinkedInScraper
from .jsearch_scraper import JSearchScraper
from .manager import ScraperManager
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
    # Manager
    "ScraperManager",
    # Storage
    "JobListingStorage",
]
