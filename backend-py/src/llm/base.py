"""
Job Raider - LLM Client Base Module

This module provides the abstract base class for all LLM client implementations.
All LLM clients (Anthropic, Ollama, etc.) must inherit from this base class.

Author: Job Raider
Date: 2026-04-20
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Message types for LLM interactions."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """Represents a single message in a conversation."""
    role: MessageType
    content: str

    def to_dict(self) -> Dict[str, str]:
        """Convert message to dictionary format."""
        return {"role": self.role.value, "content": self.content}


class LLMResponse(BaseModel):
    """Standard response format for all LLM clients."""
    content: str = Field(description="The generated text content")
    model: str = Field(description="The model used for generation")
    tokens_used: Optional[int] = Field(default=None, description="Total tokens used")
    prompt_tokens: Optional[int] = Field(default=None, description="Tokens in prompt")
    completion_tokens: Optional[int] = Field(default=None, description="Tokens in completion")
    cost: Optional[float] = Field(default=None, description="Cost in USD")
    latency_ms: Optional[int] = Field(default=None, description="Request latency in milliseconds")
    cached: bool = Field(default=False, description="Whether response was from cache")


class LLMConfig(BaseModel):
    """Base configuration for LLM clients."""
    model: str = Field(description="Model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=4096, gt=0, description="Maximum tokens to generate")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    top_k: Optional[int] = Field(default=None, gt=0, description="Top-k sampling parameter")
    stop_sequences: Optional[List[str]] = Field(default=None, description="Sequences that stop generation")
    stream: bool = Field(default=False, description="Whether to stream responses")
    timeout: int = Field(default=120, gt=0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.0, description="Initial retry delay in seconds")


class TokenUsage(BaseModel):
    """Token usage statistics."""
    prompt_tokens: int = Field(default=0, ge=0, description="Tokens in the prompt")
    completion_tokens: int = Field(default=0, ge=0, description="Tokens in the completion")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens used")

    def __add__(self, other: 'TokenUsage') -> 'TokenUsage':
        """Combine token usage statistics."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens
        )


class CostEstimate(BaseModel):
    """Cost estimation for LLM usage."""
    input_cost: float = Field(default=0.0, ge=0.0, description="Cost for input tokens")
    output_cost: float = Field(default=0.0, ge=0.0, description="Cost for output tokens")
    total_cost: float = Field(default=0.0, ge=0.0, description="Total cost")
    currency: str = Field(default="USD", description="Currency for cost")

    def __add__(self, other: 'CostEstimate') -> 'CostEstimate':
        """Combine cost estimates."""
        return CostEstimate(
            input_cost=self.input_cost + other.input_cost,
            output_cost=self.output_cost + other.output_cost,
            total_cost=self.total_cost + other.total_cost,
            currency=self.currency
        )


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM client implementations.

    All LLM clients must implement these methods to ensure a consistent interface
    across different providers (Anthropic, Ollama, etc.).
    """

    def __init__(self, config: LLMConfig, **kwargs):
        """
        Initialize the LLM client.

        Args:
            config: LLM configuration parameters
            **kwargs: Additional provider-specific parameters
        """
        self.config = config
        self._provider = kwargs.get('provider', 'unknown')
        self._total_tokens_used = 0
        self._total_cost = 0.0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'ollama')."""
        pass

    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """Return list of available models for this provider."""
        pass

    @abstractmethod
    async def generate_async(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response asynchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response synchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        pass

    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> CostEstimate:
        """
        Estimate the cost for a given number of tokens.

        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion

        Returns:
            CostEstimate with cost breakdown
        """
        pass

    def validate_messages(self, messages: List[Message]) -> None:
        """
        Validate that messages are properly formatted.

        Args:
            messages: List of messages to validate

        Raises:
            ValueError: If messages are invalid
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")

        if not isinstance(messages, list):
            raise ValueError("Messages must be a list")

        for i, msg in enumerate(messages):
            if not isinstance(msg, Message):
                raise ValueError(f"Message {i} is not a Message instance")

            if not msg.content:
                raise ValueError(f"Message {i} has empty content")

            # First message should typically be a system message
            if i == 0 and msg.role != MessageType.SYSTEM:
                # This is a warning, not an error
                pass

    def prepare_messages(
        self,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        conversation_history: Optional[List[Message]] = None
    ) -> List[Message]:
        """
        Prepare messages from various input formats.

        Args:
            system_prompt: Optional system prompt
            user_prompt: Optional user prompt
            conversation_history: Optional conversation history

        Returns:
            List of Message objects
        """
        messages = []

        if system_prompt:
            messages.append(Message(role=MessageType.SYSTEM, content=system_prompt))

        if conversation_history:
            messages.extend(conversation_history)

        if user_prompt:
            messages.append(Message(role=MessageType.USER, content=user_prompt))

        return messages

    @property
    def total_tokens_used(self) -> int:
        """Return total tokens used by this client."""
        return self._total_tokens_used

    @property
    def total_cost(self) -> float:
        """Return total cost incurred by this client."""
        return self._total_cost

    def reset_usage_stats(self) -> None:
        """Reset usage statistics (tokens and cost)."""
        self._total_tokens_used = 0
        self._total_cost = 0.0


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class RateLimitError(LLMClientError):
    """Raised when rate limit is exceeded."""
    pass


class AuthenticationError(LLMClientError):
    """Raised when authentication fails."""
    pass


class ModelNotFoundError(LLMClientError):
    """Raised when the requested model is not found."""
    pass


class TimeoutError(LLMClientError):
    """Raised when a request times out."""
    pass


class InvalidRequestError(LLMClientError):
    """Raised when the request is invalid."""
    pass
