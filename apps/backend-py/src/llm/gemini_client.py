"""
Job Raider - Google Gemini Client

This module implements the Google Gemini API client using the google-genai SDK
with retry logic, error handling, and cost tracking.

Author: Job Raider
Date: 2026-05-08
"""

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from ..metrics.cost_tracker import calculate_usage_cost, get_model_price
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
    RateLimitError,
    TimeoutError,
    TokenUsage,
)

MODEL_CONTEXT = {
    "gemini-2.5-flash": 1048576,
    "gemini-2.5-pro": 1048576,
}


class GeminiClient(BaseLLMClient):
    """
    Google Gemini API client implementation.

    Provides synchronous and asynchronous generation methods using
    the google-genai SDK with automatic retry logic and cost tracking.
    """

    AVAILABLE_MODELS = list(MODEL_CONTEXT)

    def __init__(
        self,
        config: LLMConfig,
        api_key: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the Gemini client.

        Args:
            config: LLM configuration
            api_key: Google Gemini API key (defaults to GEMINI_API_KEY env var)
            **kwargs: Additional parameters
        """
        super().__init__(config, provider="gemini", **kwargs)

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise AuthenticationError("GEMINI_API_KEY not found")

        self.client = genai.Client(api_key=self.api_key)

        if config.model not in self.available_models:
            raise ModelNotFoundError(
                f"Model '{config.model}' not available. "
                f"Available: {', '.join(self.available_models)}"
            )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "gemini"

    @property
    def available_models(self) -> List[str]:
        """Return list of available models."""
        return self.AVAILABLE_MODELS

    def _convert_messages(
        self, messages: List[Message]
    ) -> tuple[Optional[str], List[types.Content]]:
        """
        Convert Message objects to Gemini format.

        Extracts the system message (if any) as system_instruction
        and converts remaining messages to Content objects.

        Args:
            messages: List of Message objects

        Returns:
            Tuple of (system_instruction, list of Content objects)
        """
        system_instruction = None
        contents: List[types.Content] = []

        for msg in messages:
            if msg.role == MessageType.SYSTEM:
                system_instruction = msg.content
            elif msg.role == MessageType.ASSISTANT:
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )
            else:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )

        return system_instruction, contents

    def _build_config(self, **kwargs) -> types.GenerateContentConfig:
        """
        Build Gemini GenerateContentConfig from merged kwargs and defaults.

        Args:
            **kwargs: Override parameters

        Returns:
            GenerateContentConfig for the API call
        """
        config_params: Dict[str, Any] = {
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
        }

        if self.config.top_k is not None:
            config_params["top_k"] = kwargs.get("top_k", self.config.top_k)

        if self.config.stop_sequences:
            config_params["stop_sequences"] = kwargs.get(
                "stop_sequences", self.config.stop_sequences
            )

        return types.GenerateContentConfig(**config_params)

    def _extract_usage(self, response: Any) -> TokenUsage:
        """
        Extract token usage from Gemini response.

        Args:
            response: Gemini generate_content response

        Returns:
            TokenUsage with token counts
        """
        usage = response.usage_metadata
        if usage:
            prompt_tokens = usage.prompt_token_count or 0
            completion_tokens = usage.candidates_token_count or 0
            thoughts = int(getattr(usage, "thoughts_token_count", 0) or 0)
            completion_tokens += thoughts
            return TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )
        return TokenUsage()

    def generate(
        self,
        messages: List[Message],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a response synchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        self.validate_messages(messages)

        system_instruction, contents = self._convert_messages(messages)
        config = self._build_config(**kwargs)
        if system_instruction:
            config.system_instruction = system_instruction

        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()

                response = self.client.models.generate_content(
                    model=self.config.model,
                    contents=contents,
                    config=config,
                )

                latency_ms = int((time.time() - start_time) * 1000)
                content = response.text or ""
                usage = self._extract_usage(response)
                return self._build_response(content, usage, latency_ms)

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "auth" in error_str or "api key" in error_str:
                    raise AuthenticationError(f"Gemini auth failed: {e}")

                if "not found" in error_str or "does not exist" in error_str:
                    raise ModelNotFoundError(f"Gemini model error: {e}")

                if "quota" in error_str or "rate" in error_str:
                    if attempt < self.config.max_retries:
                        wait_time = self.config.retry_delay * (2**attempt)
                        time.sleep(wait_time)
                        continue
                    raise RateLimitError(f"Gemini rate limit after retries: {e}")

                if "timeout" in error_str:
                    raise TimeoutError(f"Gemini request timed out: {e}")

                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2**attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    raise LLMClientError(
                        f"Failed after {self.config.max_retries} retries: {e}"
                    )

        raise LLMClientError(f"Failed to generate response: {last_error}")

    async def generate_async(
        self,
        messages: List[Message],
        **kwargs,
    ) -> LLMResponse:
        """
        Generate a response asynchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        self.validate_messages(messages)

        system_instruction, contents = self._convert_messages(messages)
        config = self._build_config(**kwargs)
        if system_instruction:
            config.system_instruction = system_instruction

        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()

                response = await self.client.aio.models.generate_content(
                    model=self.config.model,
                    contents=contents,
                    config=config,
                )

                latency_ms = int((time.time() - start_time) * 1000)
                content = response.text or ""
                usage = self._extract_usage(response)
                return self._build_response(content, usage, latency_ms)

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "auth" in error_str or "api key" in error_str:
                    raise AuthenticationError(f"Gemini auth failed: {e}")

                if "not found" in error_str or "does not exist" in error_str:
                    raise ModelNotFoundError(f"Gemini model error: {e}")

                if "quota" in error_str or "rate" in error_str:
                    if attempt < self.config.max_retries:
                        wait_time = self.config.retry_delay * (2**attempt)
                        await asyncio.sleep(wait_time)
                        continue
                    raise RateLimitError(f"Gemini rate limit after retries: {e}")

                if "timeout" in error_str:
                    raise TimeoutError(f"Gemini request timed out: {e}")

                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2**attempt)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise LLMClientError(
                        f"Failed after {self.config.max_retries} retries: {e}"
                    )

        raise LLMClientError(f"Failed to generate response: {last_error}")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Uses the Gemini token counting API for accuracy.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        try:
            result = self.client.models.count_tokens(
                model=self.config.model,
                contents=text,
            )
            return result.total_tokens
        except Exception:
            return len(text) // 4

    def _build_response(
        self, content: str, usage: TokenUsage, latency_ms: int
    ) -> LLMResponse:
        """
        Build an LLMResponse and apply the catalog price.

        Args:
            content: Generated text.
            usage: Token counts.
            latency_ms: Call latency.

        Returns:
            The response with cost fields.
        """
        cost = self.estimate_cost(usage.prompt_tokens, usage.completion_tokens)
        self._total_tokens_used += usage.total_tokens
        self._total_cost += cost.total_cost
        price = get_model_price("gemini", self.config.model)
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider="gemini",
            tokens_used=usage.total_tokens,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost=None if price is None else cost.total_cost,
            latency_ms=latency_ms,
            cached=False,
            tokens_estimated=False,
        )

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> CostEstimate:
        """
        Estimate the cost for a given number of tokens.

        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion

        Returns:
            CostEstimate with cost breakdown. Unknown models cost 0.
        """
        price = get_model_price("gemini", self.config.model)
        if price is None:
            return CostEstimate(
                input_cost=0.0, output_cost=0.0, total_cost=0.0, currency="USD"
            )
        total = calculate_usage_cost(price, prompt_tokens, completion_tokens)
        input_rate = price.input_per_million
        output_rate = price.output_per_million
        if (
            price.long_prompt_tokens is not None
            and prompt_tokens > price.long_prompt_tokens
            and price.long_input_per_million is not None
            and price.long_output_per_million is not None
        ):
            input_rate = price.long_input_per_million
            output_rate = price.long_output_per_million
        input_cost = (prompt_tokens / 1_000_000) * input_rate
        output_cost = (completion_tokens / 1_000_000) * output_rate
        return CostEstimate(
            input_cost=round(input_cost, 6),
            output_cost=round(output_cost, 6),
            total_cost=round(total, 6),
            currency="USD",
        )
