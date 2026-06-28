# Manual LLM integration tests
# These tests are excluded from the default pytest collection and only run
# when explicitly requested with the --run-llm-tests flag.

import pytest


@pytest.mark.llm
class TestLLMManual:
    """Manual integration tests that call real LLM/Ollama services."""

    @pytest.mark.skipif(
        "not config.getoption('--run-llm-tests')",
        reason="LLM tests require --run-llm-tests flag",
    )
    def test_ollama_integration(self):
        """Test Ollama integration."""
        from src.llm.base import LLMConfig, Message, MessageType
        from src.llm.ollama_client import OllamaClient

        client = OllamaClient(config=LLMConfig(model="qwen2.5:3b"))

        response = client.generate(
            messages=[Message(role=MessageType.USER, content="Say 'Hello, World!'")]
        )

        assert response.content is not None
        assert len(response.content) > 0
