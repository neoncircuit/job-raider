"""
Job Raider - API Models

Pydantic models for API request and response schemas.

Author: Job Raider
Date: 2026-04-21
"""

from .requests import JobSearchRequest, PipelineStartRequest, ProfileUpdateRequest
from .responses import (
    CoverLetterResponse,
    CoverLetterValidationResponse,
    ErrorResponse,
    HealthCheckResponse,
    JobListingResponse,
    PipelineResultResponse,
    PipelineStatusResponse,
)

__all__ = [
    "PipelineStartRequest",
    "JobSearchRequest",
    "ProfileUpdateRequest",
    "PipelineStatusResponse",
    "PipelineResultResponse",
    "JobListingResponse",
    "HealthCheckResponse",
    "ErrorResponse",
    "CoverLetterResponse",
    "CoverLetterValidationResponse",
]
