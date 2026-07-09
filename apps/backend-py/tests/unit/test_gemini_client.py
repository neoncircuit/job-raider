"""
Unit tests for GeminiClient with mocked SDK responses.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.base import (
    AuthenticationError,
    CostEstimate,
    LLMClientError,
    LLMConfig,
    LLMResponse,
    Message,
    MessageType,
    ModelNotFoundError,
    TokenUsage,
)
from src.llm.gemini_client import MODEL_PRICING, GeminiClient


@pytest.fixture
def mock_config():
    """Create a basic LLM config for Gemini."""
    return LLMConfig(model="gemini-2.5-flash", max_retries=2, retry_delay=0.01)


@pytest.fixture
def messages():
    """Create a list of test messages."""
    return [
        Message(role=MessageType.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageType.USER, content="Hello, world!"),
    ]


def _make_response(text="Generated text", prompt_tokens=10, completion_tokens=20):
    """Create a mock Gemini response object."""
    usage = SimpleNamespace(
        prompt_token_count=prompt_tokens,
        candidates_token_count=completion_tokens,
    )
    return SimpleNamespace(text=text, usage_metadata=usage)


class TestGeminiClientInit:
    """Tests for GeminiClient initialization."""

    @patch("src.llm.gemini_client.genai.Client")
    def test_init_with_api_key(self, mock_client_cls, mock_config):
        """Test initialization with explicit API key."""
        client = GeminiClient(config=mock_config, api_key="test-key")
        assert client.provider_name == "gemini"
        assert client.api_key == "test-key"
        mock_client_cls.assert_called_once_with(api_key="test-key")

    @patch("src.llm.gemini_client.genai.Client")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"})
    def test_init_with_env_key(self, mock_client_cls, mock_config):
        """Test initialization with environment variable key."""
        client = GeminiClient(config=mock_config)
        assert client.api_key == "env-key"

    def test_init_no_key_raises(self, mock_config):
        """Test that missing API key raises AuthenticationError."""
        with patch.dict("os.environ", {}, clear=True):
            import os

            os.environ.pop("GEMINI_API_KEY", None)
            with pytest.raises(AuthenticationError, match="GEMINI_API_KEY"):
                GeminiClient(config=mock_config)

    def test_init_invalid_model_raises(self, mock_config):
        """Test that invalid model raises ModelNotFoundError."""
        bad_config = LLMConfig(model="gemini-nonexistent")
        with pytest.raises(ModelNotFoundError, match="not available"):
            GeminiClient(config=bad_config, api_key="test-key")

    @patch("src.llm.gemini_client.genai.Client")
    def test_available_models(self, mock_client_cls, mock_config):
        """Test that available models list is correct."""
        client = GeminiClient(config=mock_config, api_key="test-key")
        assert "gemini-2.5-flash" in client.available_models
        assert "gemini-2.5-pro" in client.available_models
        assert "gemini-2.0-flash" in client.available_models


class TestGeminiClientGenerate:
    """Tests for synchronous generation."""

    @patch("src.llm.gemini_client.genai.Client")
    def test_generate_basic(self, mock_client_cls, mock_config, messages):
        """Test basic synchronous generation."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_response(
            text="Hello back!", prompt_tokens=15, completion_tokens=5
        )
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        response = client.generate(messages)

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello back!"
        assert response.model == "gemini-2.5-flash"
        assert response.prompt_tokens == 15
        assert response.completion_tokens == 5
        assert response.cached is False
        assert response.latency_ms is not None
        assert response.cost is not None
        assert response.cost > 0

    @patch("src.llm.gemini_client.genai.Client")
    def test_generate_tracks_usage(self, mock_client_cls, mock_config, messages):
        """Test that token usage and cost are tracked."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_response(
            prompt_tokens=100, completion_tokens=50
        )
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        client.generate(messages)

        assert client.total_tokens_used == 150
        assert client.total_cost > 0

    @patch("src.llm.gemini_client.genai.Client")
    def test_generate_with_kwargs_overrides(
        self, mock_client_cls, mock_config, messages
    ):
        """Test that kwargs override config parameters."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_response()
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        client.generate(messages, temperature=0.1, max_tokens=100)

        call_args = mock_client.models.generate_content.call_args
        config_arg = call_args.kwargs["config"]
        assert config_arg.temperature == 0.1
        assert config_arg.max_output_tokens == 100

    @patch("src.llm.gemini_client.genai.Client")
    def test_generate_retries_on_rate_limit(
        self, mock_client_cls, mock_config, messages
    ):
        """Test retry logic on rate limit errors."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [
            Exception("Rate limit exceeded"),
            _make_response(text="Success after retry"),
        ]
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        response = client.generate(messages)

        assert response.content == "Success after retry"
        assert mock_client.models.generate_content.call_count == 2

    @patch("src.llm.gemini_client.genai.Client")
    def test_generate_raises_on_auth_error(
        self, mock_client_cls, mock_config, messages
    ):
        """Test that auth errors are not retried."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API key invalid")
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        with pytest.raises(AuthenticationError, match="auth failed"):
            client.generate(messages)

    @patch("src.llm.gemini_client.genai.Client")
    def test_generate_raises_after_max_retries(
        self, mock_client_cls, mock_config, messages
    ):
        """Test that LLMClientError is raised after max retries."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Server error")
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        with pytest.raises(LLMClientError, match="Failed after"):
            client.generate(messages)


class TestGeminiClientGenerateAsync:
    """Tests for asynchronous generation."""

    @patch("src.llm.gemini_client.genai.Client")
    @pytest.mark.asyncio
    async def test_generate_async_basic(self, mock_client_cls, mock_config, messages):
        """Test basic async generation."""
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.models = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=_make_response(text="Async response")
        )
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        response = await client.generate_async(messages)

        assert isinstance(response, LLMResponse)
        assert response.content == "Async response"

    @patch("src.llm.gemini_client.genai.Client")
    @pytest.mark.asyncio
    async def test_generate_async_retries(self, mock_client_cls, mock_config, messages):
        """Test async retry on rate limit."""
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=[
                Exception("Rate limit hit"),
                _make_response(text="Retry success"),
            ]
        )
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        response = await client.generate_async(messages)

        assert response.content == "Retry success"


class TestGeminiClientTokenCounting:
    """Tests for token counting."""

    @patch("src.llm.gemini_client.genai.Client")
    def test_count_tokens_api(self, mock_client_cls, mock_config):
        """Test token counting via Gemini API."""
        mock_client = MagicMock()
        mock_client.models.count_tokens.return_value = SimpleNamespace(total_tokens=42)
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        count = client.count_tokens("Hello, world!")

        assert count == 42
        mock_client.models.count_tokens.assert_called_once()

    @patch("src.llm.gemini_client.genai.Client")
    def test_count_tokens_fallback(self, mock_client_cls, mock_config):
        """Test fallback token counting when API fails."""
        mock_client = MagicMock()
        mock_client.models.count_tokens.side_effect = Exception("API error")
        mock_client_cls.return_value = mock_client

        client = GeminiClient(config=mock_config, api_key="test-key")
        count = client.count_tokens("Hello, world!")

        assert count == 3


class TestGeminiClientCostEstimation:
    """Tests for cost estimation."""

    @patch("src.llm.gemini_client.genai.Client")
    def test_estimate_cost_known_model(self, mock_client_cls, mock_config):
        """Test cost estimation for a known model."""
        client = GeminiClient(config=mock_config, api_key="test-key")
        cost = client.estimate_cost(1_000_000, 1_000_000)

        assert isinstance(cost, CostEstimate)
        assert cost.input_cost == 0.15
        assert cost.output_cost == 0.60
        assert cost.total_cost == 0.75
        assert cost.currency == "USD"

    @patch("src.llm.gemini_client.genai.Client")
    def test_estimate_cost_unknown_model(self, mock_client_cls):
        """Test cost estimation for gemini-2.0-flash."""
        config = LLMConfig(model="gemini-2.0-flash")
        client = GeminiClient(config=config, api_key="test-key")
        cost = client.estimate_cost(1_000_000, 1_000_000)

        assert cost.input_cost == 0.10
        assert cost.output_cost == 0.40
        assert cost.total_cost == 0.50

    @patch("src.llm.gemini_client.genai.Client")
    def test_estimate_cost_zero_tokens(self, mock_client_cls, mock_config):
        """Test cost estimation with zero tokens."""
        client = GeminiClient(config=mock_config, api_key="test-key")
        cost = client.estimate_cost(0, 0)

        assert cost.total_cost == 0.0


class TestGeminiClientMessageConversion:
    """Tests for message format conversion."""

    @patch("src.llm.gemini_client.genai.Client")
    def test_convert_messages_with_system(self, mock_client_cls, mock_config, messages):
        """Test that system messages are extracted as system_instruction."""
        client = GeminiClient(config=mock_config, api_key="test-key")
        system_inst, contents = client._convert_messages(messages)

        assert system_inst == "You are a helpful assistant."
        assert len(contents) == 1
        assert contents[0].role == "user"

    @patch("src.llm.gemini_client.genai.Client")
    def test_convert_messages_assistant_role(self, mock_client_cls, mock_config):
        """Test that assistant messages map to 'model' role."""
        client = GeminiClient(config=mock_config, api_key="test-key")
        msgs = [
            Message(role=MessageType.USER, content="Question"),
            Message(role=MessageType.ASSISTANT, content="Answer"),
            Message(role=MessageType.USER, content="Follow-up"),
        ]
        system_inst, contents = client._convert_messages(msgs)

        assert system_inst is None
        assert len(contents) == 3
        assert contents[0].role == "user"
        assert contents[1].role == "model"
        assert contents[2].role == "user"
