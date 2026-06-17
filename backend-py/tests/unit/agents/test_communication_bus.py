"""
Unit tests for AgentCommunicationBus functionality.

Tests the communication system including message passing, agent registration,
message validation, and history tracking.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from src.agents.base import TaskType
from src.agents.communication import (
    AgentCommunicationBus,
    AgentMessage,
    MessageHandler,
    MessageType,
)


@pytest.fixture
def communication_bus():
    """Fixture for communication bus instance."""
    return AgentCommunicationBus(max_queue_size=100)


@pytest.fixture
def sample_message():
    """Fixture for sample message."""
    return AgentMessage(
        type=MessageType.DIRECT_MESSAGE,
        sender="agent_1",
        receiver="agent_2",
        content={"data": "test_data"},
        priority=5,
    )


class TestAgentCommunicationBus:
    """Test suite for AgentCommunicationBus functionality."""

    @pytest.mark.asyncio
    async def test_bus_initialization(self, communication_bus):
        """Test bus initializes correctly."""
        assert communication_bus._running is False
        assert len(communication_bus.agent_registry) == 0
        assert len(communication_bus.message_queues) == 0

    @pytest.mark.asyncio
    async def test_register_agent(self, communication_bus):
        """Test agent registration."""
        success = communication_bus.register_agent("agent_1")

        assert success is True
        assert "agent_1" in communication_bus.agent_registry
        assert "agent_1" in communication_bus.message_queues

    @pytest.mark.asyncio
    async def test_register_duplicate_agent(self, communication_bus):
        """Test duplicate agent registration fails."""
        communication_bus.register_agent("agent_1")
        success = communication_bus.register_agent("agent_1")

        assert success is False

    @pytest.mark.asyncio
    async def test_unregister_agent(self, communication_bus):
        """Test agent unregistration."""
        communication_bus.register_agent("agent_1")
        success = communication_bus.unregister_agent("agent_1")

        assert success is True
        assert "agent_1" not in communication_bus.agent_registry

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_agent(self, communication_bus):
        """Test unregistering nonexistent agent fails."""
        success = communication_bus.unregister_agent("nonexistent")

        assert success is False

    @pytest.mark.asyncio
    async def test_send_message(self, communication_bus, sample_message):
        """Test sending message between agents."""
        communication_bus.register_agent("agent_1")
        communication_bus.register_agent("agent_2")

        success = await communication_bus.send_message(sample_message)

        assert success is True
        assert len(communication_bus.message_history) > 0

    @pytest.mark.asyncio
    async def test_send_message_to_unregistered_agent(
        self, communication_bus, sample_message
    ):
        """Test sending message to unregistered agent fails."""
        communication_bus.register_agent("agent_1")
        # agent_2 not registered

        success = await communication_bus.send_message(sample_message)

        assert success is False

    @pytest.mark.asyncio
    async def test_broadcast_message(self, communication_bus):
        """Test broadcasting message to all agents."""
        communication_bus.register_agent("agent_1")
        communication_bus.register_agent("agent_2")
        communication_bus.register_agent("agent_3")

        receivers = await communication_bus.broadcast_message(
            sender="agent_1",
            message_type=MessageType.BROADCAST,
            content={"data": "broadcast_data"},
        )

        assert len(receivers) == 2  # agent_2 and agent_3
        assert "agent_1" not in receivers  # Sender excluded

    @pytest.mark.asyncio
    async def test_message_validation(self, communication_bus):
        """Test message validation."""
        communication_bus.register_agent("agent_1")
        communication_bus.register_agent("agent_2")

        # Valid message
        valid_message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE,
            sender="agent_1",
            receiver="agent_2",
            content={"data": "test"},
        )
        is_valid, error = communication_bus._validate_message(valid_message)
        assert is_valid is True
        assert error is None

        # Invalid message - missing sender
        invalid_message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE,
            sender="",  # Empty sender
            receiver="agent_2",
            content={"data": "test"},
        )
        is_valid, error = communication_bus._validate_message(invalid_message)
        assert is_valid is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_message_history_with_ttl(self, communication_bus):
        """Test message history respects TTL."""
        communication_bus.register_agent("agent_1")
        communication_bus.register_agent("agent_2")

        message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE,
            sender="agent_1",
            receiver="agent_2",
            content={"data": "test"},
        )

        # Add message to history
        await communication_bus.send_message(message)

        # Message should be in history
        history = communication_bus.get_message_history(limit=10)
        assert len(history) > 0

    @pytest.mark.asyncio
    async def test_get_statistics(self, communication_bus):
        """Test getting communication statistics."""
        communication_bus.register_agent("agent_1")
        communication_bus.register_agent("agent_2")

        message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE,
            sender="agent_1",
            receiver="agent_2",
            content={"data": "test"},
        )

        await communication_bus.send_message(message)

        stats = communication_bus.get_statistics()
        assert "agent_1" in stats
        assert "agent_2" in stats

    @pytest.mark.asyncio
    async def test_health_check(self, communication_bus):
        """Test communication bus health check."""
        # No agents - unhealthy
        assert communication_bus.is_healthy() is False

        communication_bus.register_agent("agent_1")
        await communication_bus.start()

        # Has agents and running - healthy
        assert communication_bus.is_healthy() is True

        await communication_bus.stop()

    @pytest.mark.asyncio
    async def test_register_handler(self, communication_bus):
        """Test registering message handler."""
        handler_called = asyncio.Event()

        async def mock_handler(message):
            handler_called.set()

        communication_bus.register_handler(
            agent_id="agent_1",
            message_type=MessageType.DIRECT_MESSAGE,
            handler=mock_handler,
        )

        # Handler should be registered
        assert "agent_1" in communication_bus.message_handlers


class TestAgentMessage:
    """Test suite for AgentMessage functionality."""

    def test_message_creation(self):
        """Test message creation with defaults."""
        message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE, sender="agent_1", receiver="agent_2"
        )

        assert message.type == MessageType.DIRECT_MESSAGE
        assert message.sender == "agent_1"
        assert message.receiver == "agent_2"
        assert message.priority == 5  # Default
        assert message.requires_response is False  # Default

    def test_message_to_dict(self):
        """Test message serialization to dictionary."""
        message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE,
            sender="agent_1",
            receiver="agent_2",
            content={"data": "test"},
        )

        message_dict = message.to_dict()

        assert message_dict["type"] == "direct_message"
        assert message_dict["sender"] == "agent_1"
        assert message_dict["receiver"] == "agent_2"
        assert message_dict["content"] == {"data": "test"}

    def test_message_from_dict(self):
        """Test message deserialization from dictionary."""
        message_dict = {
            "message_id": "test_id",
            "type": "direct_message",
            "sender": "agent_1",
            "receiver": "agent_2",
            "content": {"data": "test"},
            "timestamp": datetime.now().isoformat(),
            "priority": 5,
            "reply_to": None,
            "requires_response": False,
            "response_timeout": 30.0,
        }

        message = AgentMessage.from_dict(message_dict)

        assert message.message_id == "test_id"
        assert message.type == MessageType.DIRECT_MESSAGE
        assert message.sender == "agent_1"

    def test_message_equality(self):
        """Test message equality based on message_id."""
        message1 = AgentMessage(
            type=MessageType.DIRECT_MESSAGE, sender="agent_1", receiver="agent_2"
        )
        message2 = AgentMessage(
            type=MessageType.DIRECT_MESSAGE, sender="agent_1", receiver="agent_2"
        )

        # Different IDs, so not equal
        assert message1 != message2

        # Same ID should be equal
        message2.message_id = message1.message_id
        assert message1 == message2


class TestMessageHandler:
    """Test suite for MessageHandler functionality."""

    @pytest.mark.asyncio
    async def test_handler_execution(self):
        """Test handler executes correctly."""
        handler_called = asyncio.Event()
        handler_result = {"called": False}

        async def mock_handler(message):
            handler_result["called"] = True
            handler_called.set()
            return AgentMessage(
                type=MessageType.DIRECT_MESSAGE, sender="handler", receiver=""
            )

        handler = MessageHandler(
            message_type=MessageType.DIRECT_MESSAGE,
            handler=mock_handler,
            agent_id="test_agent",
        )

        message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE, sender="agent_1", receiver="test_agent"
        )

        result = await handler.handle(message)

        assert handler_result["called"] is True
        assert handler_called.is_set()

    @pytest.mark.asyncio
    async def test_handler_error_handling(self):
        """Test handler handles errors gracefully."""

        async def failing_handler(message):
            raise Exception("Handler error")

        handler = MessageHandler(
            message_type=MessageType.DIRECT_MESSAGE,
            handler=failing_handler,
            agent_id="test_agent",
        )

        message = AgentMessage(
            type=MessageType.DIRECT_MESSAGE, sender="agent_1", receiver="test_agent"
        )

        # Should not raise exception, return None instead
        result = await handler.handle(message)
        assert result is None


class TestMessageType:
    """Test suite for MessageType enumeration."""

    def test_message_types(self):
        """Test all message types are available."""
        assert MessageType.TASK_ASSIGNMENT is not None
        assert MessageType.TASK_COMPLETION is not None
        assert MessageType.DIRECT_MESSAGE is not None
        assert MessageType.BROADCAST is not None
        assert MessageType.PERFORMANCE_UPDATE is not None

    def test_message_type_values(self):
        """Test message type string values."""
        assert MessageType.TASK_ASSIGNMENT.value == "task_assignment"
        assert MessageType.TASK_COMPLETION.value == "task_completion"
        assert MessageType.DIRECT_MESSAGE.value == "direct_message"
