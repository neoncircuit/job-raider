"""
Job Raider - Anthropic Claude Client

This module implements the Anthropic Claude API client with retry logic,
error handling, and cost tracking.

Author: Job Raider
Date: 2026-04-20
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message as AnthropicMessage

from .base import (
    AuthenticationError,
    BaseLLMClient,
    CostEstimate,
    LLMClientError,
    LLMConfig,
    LLMResponse,
    Message,
    MessageType,
    ModelNotFoundError,
    TokenUsage,
)

# Claude model pricing (per 1M tokens)
MODEL_PRICING = {
    "claude-opus-4-7": {
        "input": 15.0,
        "output": 75.0,
        "context": 200000,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "context": 200000,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.8,
        "output": 4.0,
        "context": 200000,
    },
}


class ClaudeClient(BaseLLMClient):
    """
    Anthropic Claude API client implementation.

    Provides synchronous and asynchronous generation methods with
    automatic retry logic and cost tracking.
    """

    # Available Claude models
    AVAILABLE_MODELS = [
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    ]

    def __init__(self, config: LLMConfig, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the Claude client.

        Args:
            config: LLM configuration
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            **kwargs: Additional parameters (base_url, timeout, etc.)
        """
        super().__init__(config, provider="anthropic", **kwargs)

        self.enable_prompt_cache = bool(kwargs.get("enable_prompt_cache", False))

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise AuthenticationError("ANTHROPIC_API_KEY not found")

        base_url = kwargs.get("base_url")
        timeout = kwargs.get("timeout", config.timeout)

        # Initialize clients
        self.client = Anthropic(
            api_key=self.api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self.async_client = AsyncAnthropic(
            api_key=self.api_key,
            base_url=base_url,
            timeout=timeout,
        )

        # Validate model
        if config.model not in self.available_models:
            raise ModelNotFoundError(
                f"Model '{config.model}' not available. "
                f"Available: {', '.join(self.available_models)}"
            )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "anthropic"

    @property
    def available_models(self) -> List[str]:
        """Return list of available models."""
        return self.AVAILABLE_MODELS

    def _split_messages(
        self, messages: List[Message]
    ) -> Tuple[Optional[Union[str, List[Dict[str, Any]]]], List[Dict[str, str]]]:
        """Split leading system messages from conversational messages.

        Anthropic accepts system content separately. When prompt caching is
        enabled, system text is sent as a content block with ephemeral
        ``cache_control``.

        Args:
            messages: Full message list including optional system roles.

        Returns:
            Tuple of (system param or None, non-system messages for API).
        """
        system_parts: List[str] = []
        rest: List[Dict[str, str]] = []
        past_leading_system = False

        for msg in messages:
            if msg.role == MessageType.SYSTEM and not past_leading_system:
                system_parts.append(msg.content)
                continue
            past_leading_system = True
            if msg.role == MessageType.SYSTEM:
                continue
            rest.append({"role": msg.role.value, "content": msg.content})

        if not system_parts:
            return None, rest

        system_text = "\n\n".join(system_parts)
        if self.enable_prompt_cache:
            system_param: Union[str, List[Dict[str, Any]]] = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_param = system_text

        return system_param, rest

    def _extract_content(self, response: AnthropicMessage) -> str:
        """Extract text content from Anthropic response."""
        return response.content[0].text

    def _extract_usage(self, response: AnthropicMessage) -> TokenUsage:
        """Extract token usage from Anthropic response."""
        usage = response.usage
        return TokenUsage(
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
        )

    def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        """
        Generate a response synchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        self.validate_messages(messages)

        # Merge kwargs with config
        params = {
            "model": self.config.model,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stop_sequences": kwargs.get("stop_sequences", self.config.stop_sequences),
        }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        system_param, anthropic_messages = self._split_messages(messages)
        create_kwargs: Dict[str, Any] = {"messages": anthropic_messages, **params}
        if system_param is not None:
            create_kwargs["system"] = system_param

        # Retry logic
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()

                response = self.client.messages.create(**create_kwargs)

                latency_ms = int((time.time() - start_time) * 1000)
                content = self._extract_content(response)
                usage = self._extract_usage(response)
                cost = self.estimate_cost(usage.prompt_tokens, usage.completion_tokens)

                # Update stats
                self._total_tokens_used += usage.total_tokens
                self._total_cost += cost.total_cost

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    tokens_used=usage.total_tokens,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    cost=cost.total_cost,
                    latency_ms=latency_ms,
                    cached=False,
                )

            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # Don't retry on certain errors
                if error_type in ["AuthenticationError", "InvalidRequestError"]:
                    raise

                # Rate limit - wait before retry
                if "rate" in str(e).lower():
                    wait_time = self.config.retry_delay * (2**attempt)
                    time.sleep(wait_time)
                    continue

                # Other errors - retry with backoff
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2**attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    raise LLMClientError(
                        f"Failed after {self.config.max_retries} retries: {e}"
                    )

        raise LLMClientError(f"Failed to generate response: {last_error}")

    async def generate_async(self, messages: List[Message], **kwargs) -> LLMResponse:
        """
        Generate a response asynchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        self.validate_messages(messages)

        # Merge kwargs with config
        params = {
            "model": self.config.model,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stop_sequences": kwargs.get("stop_sequences", self.config.stop_sequences),
        }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        system_param, anthropic_messages = self._split_messages(messages)
        create_kwargs: Dict[str, Any] = {"messages": anthropic_messages, **params}
        if system_param is not None:
            create_kwargs["system"] = system_param

        # Retry logic
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                import asyncio

                start_time = time.time()

                response = await self.async_client.messages.create(**create_kwargs)

                latency_ms = int((time.time() - start_time) * 1000)
                content = self._extract_content(response)
                usage = self._extract_usage(response)
                cost = self.estimate_cost(usage.prompt_tokens, usage.completion_tokens)

                # Update stats
                self._total_tokens_used += usage.total_tokens
                self._total_cost += cost.total_cost

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    tokens_used=usage.total_tokens,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    cost=cost.total_cost,
                    latency_ms=latency_ms,
                    cached=False,
                )

            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # Don't retry on certain errors
                if error_type in ["AuthenticationError", "InvalidRequestError"]:
                    raise

                # Rate limit - wait before retry
                if "rate" in str(e).lower():
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                    continue

                # Other errors - retry with backoff
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay * (2**attempt))
                    continue
                else:
                    raise LLMClientError(
                        f"Failed after {self.config.max_retries} retries: {e}"
                    )

        raise LLMClientError(f"Failed to generate response: {last_error}")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Uses a simple approximation (1 token ≈ 4 characters for English text).
        For accurate counting, use tiktoken or similar library.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate number of tokens
        """
        # Simple approximation: ~4 characters per token for English
        return len(text) // 4

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> CostEstimate:
        """
        Estimate the cost for a given number of tokens.

        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion

        Returns:
            CostEstimate with cost breakdown
        """
        if self.config.model not in MODEL_PRICING:
            # Default to Sonnet pricing if model not found
            pricing = MODEL_PRICING.get(
                "claude-sonnet-4-6", {"input": 3.0, "output": 15.0}
            )
        else:
            pricing = MODEL_PRICING[self.config.model]

        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        return CostEstimate(
            input_cost=round(input_cost, 6),
            output_cost=round(output_cost, 6),
            total_cost=round(input_cost + output_cost, 6),
            currency="USD",
        )
