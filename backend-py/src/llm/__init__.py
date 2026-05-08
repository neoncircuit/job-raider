"""
Job Raider - LLM Client Module

This module provides LLM client implementations for various providers:
- Anthropic Claude API
- Ollama local models
- Intelligent routing between providers

Author: Job Raider
Date: 2026-04-20
"""

from .base import (
    BaseLLMClient,
    LLMConfig,
    LLMResponse,
    Message,
    MessageType,
    TokenUsage,
    CostEstimate,
    LLMClientError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError,
    TimeoutError,
    InvalidRequestError,
)

from .claude_client import ClaudeClient
from .ollama_client import OllamaClient
from .router import (
    LLMRouter,
    TaskType,
    RouteConfig,
    create_router,
)
from .gpu_monitor import (
    GPUMonitor,
    GPUInfo,
    get_gpu_monitor,
)

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
