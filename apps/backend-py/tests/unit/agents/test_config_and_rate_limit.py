"""
Unit tests for agent configuration loader and rate limiter.

Tests configuration management, environment-specific overrides,
and API rate limiting functionality.
"""

import time
from unittest.mock import Mock

import pytest

from src.agents.config_loader import AgentConfig, get_agent_config, reset_agent_config
from src.api.rate_limiter import RateLimiter, get_rate_limiter, rate_limit


@pytest.fixture
def temp_config_file(tmp_path):
    """Fixture for temporary config file."""
    config_content = """
coordinator:
  max_concurrent_pipelines: 5
  task_timeout: 600.0
  performance_check_interval: 45.0

communication:
  max_queue_size: 2000
  max_message_size: 2097152
  max_history_size: 10000
  message_ttl:
    hours: 48

career_coach:
  analysis:
    confidence_threshold: 0.8
    max_recommendations: 15

environments:
  development:
    coordinator:
      max_concurrent_pipelines: 2
    communication:
      message_timeout: 10.0

  production:
    coordinator:
      max_concurrent_pipelines: 10
    communication:
      message_timeout: 5.0
"""
    config_file = tmp_path / "test_agent_config.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def rate_limiter():
    """Fixture for rate limiter instance."""
    return RateLimiter()


class TestAgentConfig:
    """Test suite for AgentConfig functionality."""

    def test_config_initialization(self, temp_config_file):
        """Test config initializes with file path."""
        config = AgentConfig(config_path=temp_config_file, environment="development")

        assert config.config_path == temp_config_file
        assert config.environment == "development"
        assert config._config is None  # Not loaded yet

    def test_load_config(self, temp_config_file):
        """Test configuration loads correctly."""
        config = AgentConfig(config_path=temp_config_file, environment=None)
        loaded_config = config.load_config()

        assert "coordinator" in loaded_config
        assert "communication" in loaded_config
        assert "career_coach" in loaded_config
        assert loaded_config["coordinator"]["max_concurrent_pipelines"] == 5

    def test_environment_overrides(self, temp_config_file):
        """Test environment-specific overrides are applied."""
        config = AgentConfig(config_path=temp_config_file, environment="development")
        loaded_config = config.load_config()

        # Development override should apply
        assert loaded_config["coordinator"]["max_concurrent_pipelines"] == 2

        # Production override should not apply
        config_prod = AgentConfig(
            config_path=temp_config_file, environment="production"
        )
        loaded_prod = config_prod.load_config()
        assert loaded_prod["coordinator"]["max_concurrent_pipelines"] == 10

    def test_get_coordinator_config(self, temp_config_file):
        """Test getting coordinator-specific config."""
        config = AgentConfig(config_path=temp_config_file, environment=None)
        coord_config = config.get_coordinator_config()

        assert coord_config["max_concurrent_pipelines"] == 5
        assert coord_config["task_timeout"] == 600.0
        assert coord_config["performance_check_interval"] == 45.0

    def test_get_communication_config(self, temp_config_file):
        """Test getting communication-specific config."""
        config = AgentConfig(config_path=temp_config_file)
        comm_config = config.get_communication_config()

        assert comm_config["max_queue_size"] == 2000
        assert comm_config["max_message_size"] == 2097152
        assert comm_config["max_history_size"] == 10000

    def test_get_career_coach_config(self, temp_config_file):
        """Test getting career coach-specific config."""
        config = AgentConfig(config_path=temp_config_file)
        coach_config = config.get_career_coach_config()

        assert coach_config["analysis"]["confidence_threshold"] == 0.8
        assert coach_config["analysis"]["max_recommendations"] == 15

    def test_get_value_with_path(self, temp_config_file):
        """Test getting specific config value by path."""
        config = AgentConfig(config_path=temp_config_file, environment=None)

        # Existing path
        value = config.get_value("coordinator", "max_concurrent_pipelines")
        assert value == 5

        # Non-existing path with default
        value = config.get_value("nonexistent", "path", default=42)
        assert value == 42

    def test_config_caching(self, temp_config_file):
        """Test configuration is cached after first load."""
        config = AgentConfig(config_path=temp_config_file)

        # First load
        config1 = config.load_config()
        # Second load should return cached version
        config2 = config.load_config()

        assert config1 is config2

    def test_reload_config(self, temp_config_file):
        """Test configuration can be reloaded."""
        config = AgentConfig(config_path=temp_config_file)

        config1 = config.load_config()
        config.reload()
        config2 = config.load_config()

        # Should be different objects after reload
        assert config1 is not config2

    def test_global_config_singleton(self, temp_config_file):
        """Test global config singleton works correctly."""
        reset_agent_config()  # Reset any existing global config

        config1 = get_agent_config(config_path=temp_config_file)
        config2 = get_agent_config(config_path=temp_config_file)

        # Should return same instance
        assert config1 is config2

    def test_reset_global_config(self, temp_config_file):
        """Test global config can be reset."""
        reset_agent_config()

        config1 = get_agent_config(config_path=temp_config_file)
        reset_agent_config()
        config2 = get_agent_config(config_path=temp_config_file)

        # Should be different instances after reset
        assert config1 is not config2

    def test_missing_config_file(self):
        """Test missing config file raises error."""
        config = AgentConfig(config_path="nonexistent.yaml")

        with pytest.raises(FileNotFoundError):
            config.load_config()


class TestRateLimiter:
    """Test suite for RateLimiter functionality."""

    def test_limiter_initialization(self, rate_limiter):
        """Test rate limiter initializes correctly."""
        assert rate_limiter.default_limits is not None
        assert len(rate_limiter.requests) == 0
        assert len(rate_limiter.limits) == 0

    def test_set_endpoint_limits(self, rate_limiter):
        """Test setting endpoint-specific limits."""
        rate_limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=30, requests_per_hour=500
        )

        assert "/api/test" in rate_limiter.limits
        limits = rate_limiter.get_limits("/api/test")
        assert limits["requests_per_minute"] == 30
        assert limits["requests_per_hour"] == 500

    def test_get_limits_default(self, rate_limiter):
        """Test getting default limits for unset endpoint."""
        limits = rate_limiter.get_limits("/api/nonexistent")

        assert limits == rate_limiter.default_limits
        assert limits["requests_per_minute"] == 60
        assert limits["requests_per_hour"] == 1000

    def test_check_rate_limit_allowed(self, rate_limiter):
        """Test rate limit allows requests within limits."""
        rate_limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=10, requests_per_hour=100
        )

        allowed, error = rate_limiter.check_rate_limit("client1", "/api/test")

        assert allowed is True
        assert error is None

    def test_check_rate_limit_exceeded_minute(self, rate_limiter):
        """Test rate limit blocks requests exceeding minute limit."""
        rate_limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=5, requests_per_hour=100
        )

        # Make 5 requests (at limit)
        for _ in range(5):
            allowed, error = rate_limiter.check_rate_limit("client1", "/api/test")
            assert allowed is True

        # 6th request should be blocked
        allowed, error = rate_limiter.check_rate_limit("client1", "/api/test")
        assert allowed is False
        assert error is not None
        assert "rate limit" in error.lower()

    def test_check_rate_limit_different_clients(self, rate_limiter):
        """Test rate limits are per-client."""
        rate_limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=2, requests_per_hour=10
        )

        # Client 1 makes 2 requests
        for _ in range(2):
            allowed, _ = rate_limiter.check_rate_limit("client1", "/api/test")
            assert allowed is True

        # Client 1 blocked
        allowed, _ = rate_limiter.check_rate_limit("client1", "/api/test")
        assert allowed is False

        # Client 2 still allowed
        allowed, _ = rate_limiter.check_rate_limit("client2", "/api/test")
        assert allowed is True

    def test_check_rate_limit_exceeded_hour(self, rate_limiter):
        """Test rate limit blocks requests exceeding hour limit."""
        rate_limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=100, requests_per_hour=2
        )

        # Make 2 requests (at hour limit)
        for _ in range(2):
            allowed, _ = rate_limiter.check_rate_limit("client1", "/api/test")
            assert allowed is True

        # 3rd request should be blocked
        allowed, _ = rate_limiter.check_rate_limit("client1", "/api/test")
        assert allowed is False

    def test_old_request_cleanup(self, rate_limiter):
        """Test old requests are cleaned up correctly."""
        rate_limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=5, requests_per_hour=100
        )

        # Make some requests
        for _ in range(3):
            rate_limiter.check_rate_limit("client1", "/api/test")

        # Manually add an old timestamp (more than an hour ago)
        old_timestamp = time.time() - 3700  # More than an hour
        rate_limiter.requests["client1"].append(old_timestamp)

        # Trigger cleanup by checking rate limit
        allowed, _ = rate_limiter.check_rate_limit("client1", "/api/test")

        # Old request should be cleaned up
        assert len(rate_limiter.requests["client1"]) <= 4  # 3 new + at most 1 recent

    def test_reset_client(self, rate_limiter):
        """Test client rate limit can be reset."""
        rate_limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=2, requests_per_hour=10
        )

        # Make requests at limit
        for _ in range(2):
            rate_limiter.check_rate_limit("client1", "/api/test")

        # Should be blocked
        allowed, _ = rate_limiter.check_rate_limit("client1", "/api/test")
        assert allowed is False

        # Reset client
        rate_limiter.reset_client("client1")

        # Should now be allowed again
        allowed, _ = rate_limiter.check_rate_limit("client1", "/api/test")
        assert allowed is True

    def test_global_rate_limiter_singleton(self):
        """Test global rate limiter singleton works correctly."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        # Should return same instance
        assert limiter1 is limiter2


class TestRateLimitDecorator:
    """Test suite for rate_limit decorator functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_allows_request(self):
        """Test decorator allows requests within limits."""
        limiter = get_rate_limiter()
        limiter.set_endpoint_limits(
            "/api/test", requests_per_minute=10, requests_per_hour=100
        )

        call_count = 0

        @rate_limit(requests_per_minute=10, requests_per_hour=100)
        async def mock_endpoint(request=None):
            nonlocal call_count
            call_count += 1
            return "success"

        # Mock request object
        mock_request = Mock()
        mock_request.client.host = "test_client"
        mock_request.url.path = "/api/test"

        # Should be allowed - pass request as keyword argument
        result = await mock_endpoint(request=mock_request)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_blocks_request(self):
        """Test decorator blocks requests exceeding limits."""
        limiter = get_rate_limiter()
        limiter.reset_client("test_client")  # Reset any existing state
        limiter.set_endpoint_limits(
            "/api/block", requests_per_minute=2, requests_per_hour=100
        )

        @rate_limit(requests_per_minute=2, requests_per_hour=100)
        async def mock_endpoint(request=None):
            return "success"

        # Mock request object
        mock_request = Mock()
        mock_request.client.host = "test_client"
        mock_request.url.path = "/api/block"

        # Make 2 requests (at limit) - pass request as keyword argument
        await mock_endpoint(request=mock_request)
        await mock_endpoint(request=mock_request)

        # 3rd request should be blocked
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await mock_endpoint(request=mock_request)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_without_request(self):
        """Test decorator handles missing request gracefully."""

        @rate_limit(requests_per_minute=10, requests_per_hour=100)
        async def mock_endpoint():
            return "success"

        # Should not raise exception, just skip rate limiting
        result = await mock_endpoint()
        assert result == "success"


class TestSetupAgentRateLimits:
    """Test suite for setup_agent_rate_limits function."""

    def test_setup_agent_rate_limits(self):
        """Test agent endpoint rate limits are configured."""
        from src.api.rate_limiter import setup_agent_rate_limits

        # Create mock app
        mock_app = Mock()

        # Setup limits
        setup_agent_rate_limits(mock_app)

        limiter = get_rate_limiter()

        # Check that agent endpoints have limits configured
        endpoints_to_check = [
            "/api/agents/career-analysis",
            "/api/agents/gap-analysis",
            "/api/agents/upskilling-roadmap",
            "/api/agents/career-goals",
            "/api/agents/skill-development-plan",
            "/api/agents/status",
            "/api/agents/performance",
            "/api/agents/recommendations",
            "/api/agents/health",
        ]

        for endpoint in endpoints_to_check:
            limits = limiter.get_limits(endpoint)
            assert limits["requests_per_minute"] > 0
            assert limits["requests_per_hour"] > 0

        # Career analysis endpoints should have stricter limits
        career_limits = limiter.get_limits("/api/agents/career-analysis")
        assert career_limits["requests_per_minute"] == 10
        assert career_limits["requests_per_hour"] == 100
