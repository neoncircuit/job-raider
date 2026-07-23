"""
Job Raider - LLM Router

This module implements intelligent routing for LLM requests,
selecting the appropriate model/provider based on task complexity,
cost, and availability.

Author: Job Raider
Date: 2026-04-20
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .base import BaseLLMClient, LLMConfig, LLMResponse, Message
from .claude_client import ClaudeClient
from .gemini_client import GeminiClient
from .gpu_monitor import GPUMonitor
from .ollama_client import OllamaClient


class TaskType(str, Enum):
    """Types of tasks that can be routed."""

    SELECTION = "selection"  # Project/keyword selection (fast, cheap)
    SCORING = "scoring"  # Relevance scoring (fast, cheap)
    JD_EXTRACTION = "jd_extraction"  # JD parsing (medium)
    RESUME_WRITING = "resume_writing"  # Resume generation (high quality)
    RESUME_PARSING = "resume_parsing"  # Resume parsing (medium)
    RESUME_ANALYSIS = "resume_analysis"  # Resume analysis (medium)
    LINKEDIN_ANALYSIS = "linkedin_analysis"  # LinkedIn profile analysis (medium)
    CLASSIFICATION = "classification"  # Job categorization (medium)
    VALIDATION = "validation"  # Content validation (fast)
    EMBEDDING = "embedding"  # Embedding generation (RAG)
    QUESTION_ANSWERING = "question_answering"  # Answering application form questions
    TRUST_ANALYSIS = "trust_analysis"  # Analyzing job listing trustworthiness
    COVER_LETTER_WRITING = (
        "cover_letter_writing"  # Cover letter generation (high quality)
    )
    COVER_LETTER_REVIEW = (
        "cover_letter_review"  # Cover letter critique and rewrite guidance
    )
    ASSESSMENT_GENERATION = "assessment_generation"  # Generating assessment questions
    ASSESSMENT_EVALUATION = "assessment_evaluation"  # Evaluating assessment answers
    GENERAL = "general"  # General purpose tasks


@dataclass
class RouteConfig:
    """Configuration for a specific route."""

    task_type: TaskType
    primary_provider: str  # "ollama" or "anthropic"
    primary_model: str
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    max_retries: int = 1


class LLMRouter:
    """
    Intelligent router for LLM requests.

    Routes requests to appropriate models based on task type,
    with automatic fallback and cost optimization.
    """

    # Default route configurations
    DEFAULT_ROUTES: Dict[TaskType, RouteConfig] = {
        TaskType.SELECTION: RouteConfig(
            task_type=TaskType.SELECTION,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="anthropic",
            fallback_model="claude-haiku-4-5-20251001",
        ),
        TaskType.SCORING: RouteConfig(
            task_type=TaskType.SCORING,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="ollama",
            fallback_model="gemma3:4b",
        ),
        TaskType.JD_EXTRACTION: RouteConfig(
            task_type=TaskType.JD_EXTRACTION,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.RESUME_WRITING: RouteConfig(
            task_type=TaskType.RESUME_WRITING,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.RESUME_PARSING: RouteConfig(
            task_type=TaskType.RESUME_PARSING,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.RESUME_ANALYSIS: RouteConfig(
            task_type=TaskType.RESUME_ANALYSIS,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.LINKEDIN_ANALYSIS: RouteConfig(
            task_type=TaskType.LINKEDIN_ANALYSIS,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.CLASSIFICATION: RouteConfig(
            task_type=TaskType.CLASSIFICATION,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-haiku-4-5-20251001",
        ),
        TaskType.VALIDATION: RouteConfig(
            task_type=TaskType.VALIDATION,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="ollama",
            fallback_model="gemma3:4b",
        ),
        TaskType.GENERAL: RouteConfig(
            task_type=TaskType.GENERAL,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.EMBEDDING: RouteConfig(
            task_type=TaskType.EMBEDDING,
            primary_provider="ollama",
            primary_model="nomic-embed-text",
            fallback_provider=None,
            fallback_model=None,
        ),
        TaskType.QUESTION_ANSWERING: RouteConfig(
            task_type=TaskType.QUESTION_ANSWERING,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="anthropic",
            fallback_model="claude-haiku-4-5-20251001",
        ),
        TaskType.TRUST_ANALYSIS: RouteConfig(
            task_type=TaskType.TRUST_ANALYSIS,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="anthropic",
            fallback_model="claude-haiku-4-5-20251001",
        ),
        TaskType.COVER_LETTER_WRITING: RouteConfig(
            task_type=TaskType.COVER_LETTER_WRITING,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.COVER_LETTER_REVIEW: RouteConfig(
            task_type=TaskType.COVER_LETTER_REVIEW,
            primary_provider="ollama",
            primary_model="qwen2.5:3b",
            fallback_provider="ollama",
            fallback_model="gemma3:4b",
        ),
        TaskType.ASSESSMENT_GENERATION: RouteConfig(
            task_type=TaskType.ASSESSMENT_GENERATION,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
        TaskType.ASSESSMENT_EVALUATION: RouteConfig(
            task_type=TaskType.ASSESSMENT_EVALUATION,
            primary_provider="ollama",
            primary_model="qwen2.5:7b",
            fallback_provider="anthropic",
            fallback_model="claude-sonnet-4-6",
        ),
    }

    def __init__(
        self,
        routes: Optional[Dict[TaskType, RouteConfig]] = None,
        api_key: Optional[str] = None,
        ollama_host: Optional[str] = None,
        ollama_port: Optional[int] = None,
        gpu_monitor: Optional[GPUMonitor] = None,
        gemini_api_key: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the LLM router.

        Args:
            routes: Custom route configurations (defaults to DEFAULT_ROUTES)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            ollama_host: Ollama host (defaults to OLLAMA_HOST env var)
            ollama_port: Ollama port (defaults to OLLAMA_PORT env var)
            gpu_monitor: Optional GPU monitor for Ollama
            gemini_api_key: Google Gemini API key (defaults to GEMINI_API_KEY env var)
            **kwargs: Additional parameters
        """
        self.routes = routes or self.DEFAULT_ROUTES
        self.api_key = api_key
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.gpu_monitor = gpu_monitor or GPUMonitor()
        self.gemini_api_key = gemini_api_key

        # Client cache
        self._clients: Dict[str, BaseLLMClient] = {}

        # Statistics
        self._total_requests = 0
        self._primary_used = 0
        self._fallback_used = 0
        self._total_cost = 0.0

    def reload_routes_from_settings(self, settings_routes: Dict[str, Any]) -> None:
        """
        Reload routes from user settings.

        Merges user overrides into a copy of DEFAULT_ROUTES so unspecified
        tasks (e.g. embedding) keep their built-in configuration. Clears the
        client cache so new connections use the updated routes.

        Args:
            settings_routes: Dict of task_type to ModelRouting config (or
                equivalent dict) from user settings.
        """
        new_routes: Dict[TaskType, RouteConfig] = dict(self.DEFAULT_ROUTES)

        for task_type_str, routing_config in settings_routes.items():
            try:
                task_type = TaskType(task_type_str)
            except ValueError:
                continue

            if isinstance(routing_config, dict):
                primary_provider = routing_config.get("primary_provider")
                primary_model = routing_config.get("primary_model")
                fallback_provider = routing_config.get("fallback_provider")
                fallback_model = routing_config.get("fallback_model")
            else:
                primary_provider = getattr(routing_config, "primary_provider", None)
                primary_model = getattr(routing_config, "primary_model", None)
                fallback_provider = getattr(routing_config, "fallback_provider", None)
                fallback_model = getattr(routing_config, "fallback_model", None)

            if hasattr(primary_provider, "value"):
                primary_provider = primary_provider.value
            if hasattr(fallback_provider, "value"):
                fallback_provider = fallback_provider.value

            if not primary_provider or not primary_model:
                continue

            new_routes[task_type] = RouteConfig(
                task_type=task_type,
                primary_provider=str(primary_provider),
                primary_model=str(primary_model),
                fallback_provider=(
                    str(fallback_provider) if fallback_provider else None
                ),
                fallback_model=str(fallback_model) if fallback_model else None,
            )

        self.routes = new_routes
        self._clients.clear()

    def apply_user_settings(self) -> None:
        """
        Load persisted user settings and apply routing plus Ollama host.

        Silently keeps constructor defaults when settings cannot be loaded.
        """
        try:
            from ..api.ollama_models import parse_ollama_host_port
            from ..api.settings import get_storage

            settings = get_storage().load_settings()
            if settings.routing:
                self.reload_routes_from_settings(settings.routing)
            if settings.api_config and settings.api_config.ollama_host:
                host, port = parse_ollama_host_port(settings.api_config.ollama_host)
                self.ollama_host = host
                self.ollama_port = port
                self._clients.clear()
        except Exception:
            pass

    def _get_client(
        self, provider: str, model: str, config: Optional[LLMConfig] = None
    ) -> BaseLLMClient:
        """
        Get or create a client for the given provider and model.

        Args:
            provider: Provider name ("ollama" or "anthropic")
            model: Model name
            config: Optional LLM configuration

        Returns:
            BaseLLMClient instance
        """
        cache_key = f"{provider}:{model}"

        if cache_key in self._clients:
            return self._clients[cache_key]

        # Create new client
        if provider == "anthropic":
            client = ClaudeClient(
                config=config or LLMConfig(model=model),
                api_key=self.api_key,
            )
        elif provider == "ollama":
            client = OllamaClient(
                config=config or LLMConfig(model=model),
                host=self.ollama_host,
                port=self.ollama_port,
                gpu_monitor=self.gpu_monitor,
            )
        elif provider == "gemini":
            client = GeminiClient(
                config=config or LLMConfig(model=model),
                api_key=self.gemini_api_key,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

        self._clients[cache_key] = client
        return client

    def generate(
        self, messages: List[Message], task_type: TaskType = TaskType.GENERAL, **kwargs
    ) -> LLMResponse:
        """
        Generate a response using the appropriate model for the task.

        Args:
            messages: List of messages in the conversation
            task_type: Type of task (determines routing)
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        if task_type not in self.routes:
            raise ValueError(f"Unknown task type: {task_type}")

        route = self.routes[task_type]
        self._total_requests += 1

        # Try primary provider
        try:
            client = self._get_client(route.primary_provider, route.primary_model)
            response = client.generate(messages, **kwargs)
            self._primary_used += 1
            self._total_cost += response.cost or 0.0
            return response

        except Exception as e:
            # Try fallback if configured
            if route.fallback_provider and route.fallback_model:
                try:
                    client = self._get_client(
                        route.fallback_provider, route.fallback_model
                    )
                    response = client.generate(messages, **kwargs)
                    self._fallback_used += 1
                    self._total_cost += response.cost or 0.0
                    return response
                except Exception as fallback_error:
                    raise Exception(
                        f"Primary failed: {e}. Fallback also failed: {fallback_error}"
                    )

            raise

    async def generate_async(
        self, messages: List[Message], task_type: TaskType = TaskType.GENERAL, **kwargs
    ) -> LLMResponse:
        """
        Generate a response asynchronously using the appropriate model.

        Args:
            messages: List of messages in the conversation
            task_type: Type of task (determines routing)
            **kwargs: Additional generation parameters

        Returns:
            LLMResponse with generated content and metadata
        """
        if task_type not in self.routes:
            raise ValueError(f"Unknown task type: {task_type}")

        route = self.routes[task_type]
        self._total_requests += 1

        # Try primary provider
        try:
            client = self._get_client(route.primary_provider, route.primary_model)
            response = await client.generate_async(messages, **kwargs)
            self._primary_used += 1
            self._total_cost += response.cost or 0.0
            return response

        except Exception as e:
            # Try fallback if configured
            if route.fallback_provider and route.fallback_model:
                try:
                    client = self._get_client(
                        route.fallback_provider, route.fallback_model
                    )
                    response = await client.generate_async(messages, **kwargs)
                    self._fallback_used += 1
                    self._total_cost += response.cost or 0.0
                    return response
                except Exception as fallback_error:
                    raise Exception(
                        f"Primary failed: {e}. Fallback also failed: {fallback_error}"
                    )

            raise

    def add_route(self, route: RouteConfig) -> None:
        """
        Add or update a route configuration.

        Args:
            route: Route configuration to add/update
        """
        self.routes[route.task_type] = route

    def get_route(self, task_type: TaskType) -> Optional[RouteConfig]:
        """
        Get the route configuration for a task type.

        Args:
            task_type: Task type to look up

        Returns:
            RouteConfig if found, None otherwise
        """
        return self.routes.get(task_type)

    @property
    def stats(self) -> Dict[str, Any]:
        """Return routing statistics."""
        return {
            "total_requests": self._total_requests,
            "primary_used": self._primary_used,
            "fallback_used": self._fallback_used,
            "fallback_rate": (
                self._fallback_used / self._total_requests
                if self._total_requests > 0
                else 0.0
            ),
            "total_cost": self._total_cost,
        }

    def reset_stats(self) -> None:
        """Reset routing statistics."""
        self._total_requests = 0
        self._primary_used = 0
        self._fallback_used = 0
        self._total_cost = 0.0


def create_router(
    prefer_local: bool = True, api_key: Optional[str] = None, **kwargs
) -> LLMRouter:
    """
    Create an LLM router with optimized settings.

    Loads saved user routing and Ollama host from settings when available.

    Args:
        prefer_local: If True, prefer local Ollama models over API
        api_key: Anthropic API key
        **kwargs: Additional parameters

    Returns:
        Configured LLMRouter instance
    """
    if prefer_local:
        router = LLMRouter(api_key=api_key, **kwargs)
    else:
        routes = {}
        for task_type, default_route in LLMRouter.DEFAULT_ROUTES.items():
            routes[task_type] = RouteConfig(
                task_type=task_type,
                primary_provider="anthropic",
                primary_model=default_route.fallback_model or "claude-sonnet-4-6",
                fallback_provider="ollama",
                fallback_model=default_route.primary_model,
            )
        router = LLMRouter(routes=routes, api_key=api_key, **kwargs)

    router.apply_user_settings()
    return router
