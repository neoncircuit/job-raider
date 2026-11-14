"""
Job Raider - Ollama Client

This module implements the Ollama client for local model inference,
with GPU monitoring, VRAM tracking, and CPU fallback support.

Author: Job Raider
Date: 2026-04-20
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..utils.logger import Components, get_logger
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


logger = get_logger(Components.LLM)

# Seconds to wait for Ollama to load a model into memory. A cold load with low
# free RAM can take longer than the chat timeout; a separate, longer timeout
# keeps the chat retry loop from cancelling a slow load and starting it again.
DEFAULT_LOAD_TIMEOUT = 600


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
        load_timeout: int = DEFAULT_LOAD_TIMEOUT,
        **kwargs,
    ):
        """
        Initialize the Ollama client.

        Args:
            config: LLM configuration
            host: Ollama host (defaults to OLLAMA_HOST env var or localhost)
            port: Ollama port (defaults to OLLAMA_PORT env var or 11434)
            load_timeout: Seconds to wait for Ollama to load the model before
                a chat request, when the model is not loaded (default 600).
            **kwargs: Additional parameters. ``keep_alive`` is sent with each
                chat request; ``one_model_at_a_time`` (default False) unloads
                any other loaded model before each chat request.
        """
        super().__init__(config, provider="ollama", **kwargs)

        self.load_timeout = load_timeout
        self.keep_alive = kwargs.get("keep_alive")
        self.one_model_at_a_time = bool(kwargs.get("one_model_at_a_time", False))

        raw_host = host or os.getenv("OLLAMA_HOST", "localhost")
        if ":" in raw_host:
            self.host, port_str = raw_host.rsplit(":", 1)
            self.port = int(port_str)
        else:
            self.host = raw_host
            self.port = int(port or os.getenv("OLLAMA_PORT", "11434"))
        self.base_url = f"http://{self.host}:{self.port}"

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

    def _loaded_models(self) -> Optional[List[str]]:
        """
        Ask Ollama which models are loaded in memory (``/api/ps``).

        Returns:
            The names of the loaded models, or ``None`` when Ollama does not
            answer or the answer cannot be read.
        """
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=5)
            response.raise_for_status()
            return [
                str(item.get("name") or item.get("model") or "")
                for item in (response.json().get("models") or [])
            ]
        except (requests.RequestException, ValueError) as exc:
            logger.debug(f"Could not list loaded Ollama models: {exc}")
            return None

    def _unload_other_models(self, loaded: List[str]) -> None:
        """
        Unload every loaded Ollama model except this client's model.

        Sends each other model a request with ``keep_alive: 0``, which unloads
        it. Errors are logged and ignored: the chat request goes on either way.

        Args:
            loaded: The loaded model names (from ``_loaded_models``).
        """
        for name in loaded:
            if not name or name == self.config.model:
                continue
            try:
                requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": name, "keep_alive": 0},
                    timeout=30,
                ).raise_for_status()
                logger.info(f"Unloaded Ollama model {name} before {self.config.model}")
            except requests.RequestException as exc:
                logger.debug(f"Could not unload Ollama model {name}: {exc}")

    def _ensure_loaded(self, loaded: List[str], keep_alive: Any) -> None:
        """
        Load this client's model before the chat request, when it is not loaded.

        Sends ``/api/generate`` with the model and no prompt, so Ollama only
        loads the model. The request uses ``load_timeout``, not the chat
        timeout, so a slow cold load is not cancelled and started again by the
        chat retry loop. Errors and timeouts are logged as warnings and
        ignored: the chat request then works as before.

        Args:
            loaded: The loaded model names (from ``_loaded_models``).
            keep_alive: The keep_alive of the chat request, or ``None`` for the
                Ollama default.
        """
        model = self.config.model
        if model in loaded:
            return
        body: Dict[str, Any] = {"model": model}
        if keep_alive is not None:
            body["keep_alive"] = keep_alive
        logger.info(f"Loading Ollama model {model} (timeout {self.load_timeout} s)")
        start = time.time()
        try:
            requests.post(
                f"{self.base_url}/api/generate",
                json=body,
                timeout=self.load_timeout,
            ).raise_for_status()
        except requests.RequestException as exc:
            logger.warning(
                f"Could not load Ollama model {model} before the chat request"
                f" after {time.time() - start:.0f} s: {exc}"
            )
            return
        logger.info(f"Loaded Ollama model {model} in {time.time() - start:.1f} s")

    def generate(self, messages: List[Message], **kwargs) -> LLMResponse:
        """
        Generate a response synchronously.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional generation parameters. Notable keys:
                ``temperature``, ``max_tokens``, ``top_p``, ``timeout``,
                ``stop_sequences``, and optional ``think`` (passed through to
                Ollama ``/api/chat`` only when explicitly provided so other
                callers keep Ollama's default thinking behavior). Optional
                ``num_ctx`` goes to ``options.num_ctx``, and optional
                ``response_schema`` (a JSON schema) goes to ``format``.

        Returns:
            LLMResponse with generated content and metadata
        """
        self.validate_messages(messages)

        keep_alive = kwargs.get("keep_alive", self.keep_alive)

        # One /api/ps call serves both steps. When it fails, both are skipped
        # and the chat request runs as before.
        loaded = self._loaded_models()
        if loaded is not None:
            # Keep one model in GPU memory: unload any other loaded model first.
            if self.one_model_at_a_time:
                self._unload_other_models(loaded)
            # Load this model with the long load timeout, so the chat timeout
            # applies to the answer only.
            self._ensure_loaded(loaded, keep_alive)

        # Build request payload. Do not set ``think`` unless the caller asked;
        # cover-letter writing passes think=False for Gemma 4 blank-output.
        payload: Dict[str, Any] = {
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
        if kwargs.get("num_ctx"):
            payload["options"]["num_ctx"] = int(kwargs["num_ctx"])
        if kwargs.get("response_schema"):
            payload["format"] = kwargs["response_schema"]

        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

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

                prompt_tokens, completion_tokens, tokens_estimated = (
                    self._tokens_from_chat(data, messages, content)
                )

                # Update stats
                self._total_tokens_used += prompt_tokens + completion_tokens

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider="ollama",
                    tokens_used=prompt_tokens + completion_tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost=0.0,  # Local models are free
                    latency_ms=latency_ms,
                    cached=False,
                    tokens_estimated=tokens_estimated,
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

    def _tokens_from_chat(
        self,
        data: Dict[str, Any],
        messages: List[Message],
        content: str,
    ) -> Tuple[int, int, bool]:
        """
        Read token counts from an Ollama ``/api/chat`` response.

        When ``prompt_eval_count`` or ``eval_count`` is missing, that value
        uses the length estimate (characters / 4) and the result is marked
        estimated.

        Args:
            data: Parsed ``/api/chat`` JSON body.
            messages: Prompt messages.
            content: Assistant text.

        Returns:
            Prompt tokens, completion tokens, and whether any count is an
            estimate.
        """
        estimated = False
        prompt_raw = data.get("prompt_eval_count")
        if prompt_raw is None:
            prompt_tokens = sum(len(msg.content) // 4 for msg in messages)
            estimated = True
        else:
            prompt_tokens = int(prompt_raw)
        eval_raw = data.get("eval_count")
        if eval_raw is None:
            completion_tokens = len(content) // 4
            estimated = True
        else:
            completion_tokens = int(eval_raw)
        return prompt_tokens, completion_tokens, estimated

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
