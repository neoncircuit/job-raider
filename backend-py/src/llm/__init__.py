"""
Job Raider - LLM Client Module

This module provides LLM client implementations for various providers:
- Anthropic Claude API
- Google Gemini API
- Ollama local models
- Intelligent routing between providers

Author: Job Raider
Date: 2026-04-20
"""

from .base import (
    AuthenticationError,
    BaseLLMClient,
    CostEstimate,
    InvalidRequestError,
    LLMClientError,
    LLMConfig,
    LLMResponse,
    Message,
    MessageType,
    ModelNotFoundError,
    RateLimitError,
    TimeoutError,
    TokenUsage,
)
from .claude_client import ClaudeClient
from .gemini_client import GeminiClient
from .gpu_monitor import GPUInfo, GPUMonitor, get_gpu_monitor
from .ollama_client import OllamaClient
from .router import LLMRouter, RouteConfig, TaskType, create_router

__all__ = [
    # Base classes
    "BaseLLMClient",
    "LLMConfig",
    "LLMResponse",
    "Message",
    "MessageType",
    "TokenUsage",
    "CostEstimate",
    # Exceptions
    "LLMClientError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotFoundError",
    "TimeoutError",
    "InvalidRequestError",
    # Clients
    "ClaudeClient",
    "GeminiClient",
    "OllamaClient",
    # Router
    "LLMRouter",
    "TaskType",
    "RouteConfig",
    "create_router",
    # GPU Monitor
    "GPUMonitor",
    "GPUInfo",
    "get_gpu_monitor",
]
