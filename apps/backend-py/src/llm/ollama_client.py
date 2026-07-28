"""
Job Raider - Ollama Client

This module implements the Ollama client for local model inference,
with GPU monitoring, VRAM tracking, and CPU fallback support.

Author: Job Raider
Date: 2026-04-20
"""

import os
import time
from typing import Any, Dict, List, Optional

import requests

from .base import (
    BaseLLMClient,
    CostEstimate,
    LLMClientError,
    LLMConfig,
    LLMResponse,
    Message,
    ModelNotFoundError,
)


def extract_ollama_chat_content(message: Dict[str, Any]) -> str:
    """
    Extract usable assistant text from an Ollama ``/api/chat`` message.

    Returns only ``content``. Callers that need thinking disabled for a
    specific task (for example cover-letter writing with Gemma 4) should
    pass ``think=False`` on that generate call; this helper does not change
    Ollama defaults for other users of the client.

    Args:
        message: The ``message`` object from an Ollama chat response.

    Returns:
        Stripped ``content`` text, or an empty string when missing.
    """
    return (message.get("content") or "").strip()


class OllamaClient(BaseLLMClient):
    """
    Ollama client for local model inference.

    Supports GPU acceleration with automatic CPU fallback and VRAM monitoring.
    """

    def __init__(
        self,
        config: LLMConfig,
        host: Optional[str] = None,
        port: Optional[int] = None,
        gpu_monitor: Optional[Any] = None,
        **kwargs,
    ):
        """
        Initialize the Ollama client.

        Args:
            config: LLM configuration
            host: Ollama host (defaults to OLLAMA_HOST env var or localhost)
            port: Ollama port (defaults to OLLAMA_PORT env var or 11434)
            gpu_monitor: Optional GPU monitor for VRAM tracking
            **kwargs: Additional parameters
        """
        super().__init__(config, provider="ollama", **kwargs)

        raw_host = host or os.getenv("OLLAMA_HOST", "localhost")
        if ":" in raw_host:
            self.host, port_str = raw_host.rsplit(":", 1)
            self.port = int(port_str)
        else:
            self.host = raw_host
            self.port = int(port or os.getenv("OLLAMA_PORT", "11434"))
        self.base_url = f"http://{self.host}:{self.port}"
        self.gpu_monitor = gpu_monitor

        # Verify Ollama is running
        if not self._is_ollama_running():
            raise LLMClientError(
                f"Ollama is not running at {self.base_url}. "
                "Start Ollama with: ollama serve"
            )

        # Check if model is available
        if config.model not in self.available_models:
            # Try to pull the model
            if not self._pull_model(config.model):
                raise ModelNotFoundError(
                    f"Model '{config.model}' not found and could not be pulled"
                )

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "ollama"

    @property
    def available_models(self) -> List[str]:
        """Return list of available models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            raise LLMClientError(f"Failed to fetch available models: {e}")

    def _is_ollama_running(self) -> bool:
        """Check if Ollama server is running."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _pull_model(self, model: str) -> bool:
        """
        Pull a model from Ollama library.

        Args:
            model: Model name to pull

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"Pulling model {model} from Ollama...")
            response = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model, "stream": False},
                timeout=300,  # 5 minutes timeout for pulling
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to pull model {model}: {e}")
            return False

    def _check_vram_before_inference(self) -> bool:
        """
        Check if there's sufficient VRAM for GPU inference.

        Returns:
            True if GPU can be used, False if should fall back to CPU
        """
        if not self.gpu_monitor:
            return True  # No monitor, assume GPU is available

        try:
            vram_usage = self.gpu_monitor.get_vram_usage()
            if vram_usage >= 0.9:  # 90% threshold
                print(f"VRAM usage at {vram_usage:.1%}, falling back to CPU")
                return False
            return True
        except Exception as e:
            print(f"Failed to check VRAM: {e}, using GPU")
            return True

    def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        """
        Generate a response synchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters. Notable keys:
                ``temperature``, ``max_tokens``, ``top_p``, ``timeout``,
                ``stop_sequences``, and optional ``think`` (passed through to
                Ollama ``/api/chat`` only when explicitly provided so other
                callers keep Ollama's default thinking behavior).

        Returns:
            LLMResponse with generated content and metadata
        """
        self.validate_messages(messages)

        # Check VRAM before inference
        self._check_vram_before_inference()

        # Build request payload. Do not set ``think`` unless the caller asked;
        # cover-letter writing passes think=False for Gemma 4 blank-output.
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": msg.role.value, "content": msg.content} for msg in messages
            ],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": kwargs.get("top_p", self.config.top_p),
            },
        }
        if "think" in kwargs:
            payload["think"] = bool(kwargs["think"])

        # Add stop sequences if provided
        stop_seqs = kwargs.get("stop_sequences", self.config.stop_sequences)
        if stop_seqs:
            payload["options"]["stop"] = stop_seqs

        # Retry logic
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()

                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=kwargs.get("timeout", self.config.timeout),
                )
                response.raise_for_status()

                latency_ms = int((time.time() - start_time) * 1000)

                # Parse response (/api/chat returns message.content)
                data = response.json()
                message = data.get("message", {}) or {}
                content = extract_ollama_chat_content(message)
                if not content:
                    thinking_len = len((message.get("thinking") or "").strip())
                    raise LLMClientError(
                        "Ollama returned empty content"
                        f" (model={self.config.model},"
                        f" done_reason={data.get('done_reason')},"
                        f" eval_count={data.get('eval_count')},"
                        f" thinking_chars={thinking_len})"
                    )

                # Count tokens (Ollama doesn't return token count)
                prompt_tokens = sum(self.count_tokens(msg.content) for msg in messages)
                completion_tokens = self.count_tokens(content)

                # Update stats
                self._total_tokens_used += prompt_tokens + completion_tokens

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    tokens_used=prompt_tokens + completion_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost=0.0,  # Local models are free
                    latency_ms=latency_ms,
                    cached=False,
                )

            except requests.Timeout:
                last_error = TimeoutError(
                    f"Request timed out after {self.config.timeout}s"
                )
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay * (2**attempt))
                    continue
                else:
                    raise last_error

            except requests.RequestException as e:
                last_error = LLMClientError(f"Request failed: {e}")
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay * (2**attempt))
                    continue
                else:
                    raise last_error

            except LLMClientError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay * (2**attempt))
                    continue
                else:
                    raise last_error

            except Exception as e:
                raise LLMClientError(f"Unexpected error: {e}")

        raise LLMClientError(f"Failed to generate response: {last_error}")

    async def generate_async(self, messages: List[Message], **kwargs) -> LLMResponse:
        """
        Generate a response asynchronously.

        Note: Ollama's REST API doesn't natively support async.
        This method wraps the synchronous call in an async executor.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        import asyncio
        import functools

        # Run synchronous generation in executor. run_in_executor() does not
        # forward keyword arguments, so bind them with functools.partial.
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(self.generate, messages, **kwargs)
        )

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Uses a simple approximation. For accurate counting, Ollama provides
        a token endpoint that can be used.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate number of tokens
        """
        # Try to use Ollama's token endpoint for accurate counting
        try:
            response = requests.post(
                f"{self.base_url}/api/tokenize",
                json={"model": self.config.model, "content": text},
                timeout=5,
            )
            if response.status_code == 200:
                data = response.json()
                return len(data.get("tokens", []))
        except Exception:
            pass

        # Fallback to approximation (~4 characters per token)
        return len(text) // 4

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> CostEstimate:
        """
        Estimate the cost for a given number of tokens.

        Local models via Ollama are free to run after initial setup.

        Args:
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion

        Returns:
            CostEstimate with zero cost
        """
        return CostEstimate(
            input_cost=0.0,
            output_cost=0.0,
            total_cost=0.0,
            currency="USD",
        )

    def get_model_info(self, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about a specific model.

        Args:
            model: Model name (defaults to configured model)

        Returns:
            Dictionary with model information
        """
        model = model or self.config.model

        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise LLMClientError(f"Failed to get model info: {e}")
