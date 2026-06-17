"""
Agent Communication System for Job Raider Multi-Agent System

Provides message passing infrastructure for inter-agent communication,
message queuing, and coordination.
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .base import Task, TaskType
from .config_loader import get_agent_config

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be sent between agents."""

    # Task Management
    TASK_ASSIGNMENT = "task_assignment"
    TASK_COMPLETION = "task_completion"
    TASK_FAILURE = "task_failure"

    # Dependencies
    DEPENDENCY_REQUEST = "dependency_request"
    DEPENDENCY_RESPONSE = "dependency_response"

    # Recommendations
    RECOMMENDATION = "recommendation"
    CONFLICT_RESOLUTION = "conflict_resolution"

    # State Management
    STATE_UPDATE = "state_update"
    STATUS_REQUEST = "status_request"
    STATUS_RESPONSE = "status_response"

    # Coordination
    BROADCAST = "broadcast"
    DIRECT_MESSAGE = "direct_message"

    # Performance
    PERFORMANCE_UPDATE = "performance_update"


@dataclass
class AgentMessage:
    """Represents a message sent between agents."""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType = MessageType.DIRECT_MESSAGE
    sender: str = ""
    receiver: str = ""  # Empty string for broadcast messages
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1-10, 10 being highest
    reply_to: Optional[str] = None  # Message ID this is replying to
    requires_response: bool = False
    response_timeout: float = 30.0  # seconds

    def __hash__(self):
        return hash(self.message_id)

    def __eq__(self, other):
        if not isinstance(other, AgentMessage):
            return False
        return self.message_id == other.message_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "type": self.type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
            "reply_to": self.reply_to,
            "requires_response": self.requires_response,
            "response_timeout": self.response_timeout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create message from dictionary."""
        return cls(
            message_id=data["message_id"],
            type=MessageType(data["type"]),
            sender=data["sender"],
            receiver=data["receiver"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=data["priority"],
            reply_to=data.get("reply_to"),
            requires_response=data["requires_response"],
            response_timeout=data["response_timeout"],
        )


@dataclass
class MessageHandler:
    """Represents a message handler for a specific message type."""

    message_type: MessageType
    handler: Callable
    agent_id: str
    priority: int = 5

    async def handle(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Handle the message.

        Args:
            message: The message to handle

        Returns:
            Optional response message
        """
        try:
            return await self.handler(message)
        except Exception as e:
            logger.error(f"Error in message handler for {self.agent_id}: {e}")
            return None


class AgentCommunicationBus:
    """
    Central communication hub for multi-agent system.

    Manages message passing, agent registry, and communication
    coordination between agents.
    """

    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize the communication bus.

        Args:
            max_queue_size: Maximum size of message queues per agent
        """
        self.agent_registry: Dict[str, bool] = {}
        self.message_queues: Dict[str, asyncio.Queue] = defaultdict(
            lambda: asyncio.Queue(maxsize=max_queue_size)
        )
        self.message_handlers: Dict[str, List[MessageHandler]] = defaultdict(list)
        self.message_history: List[AgentMessage] = []
        self.pending_responses: Dict[str, asyncio.Future] = {}
        self.message_filters: Dict[str, Callable[[AgentMessage], bool]] = {}
        self.statistics: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        self._running = False
        self._processing_tasks: Dict[str, asyncio.Task] = {}

        # Load configuration from external config file
        self.config = get_agent_config()
        comm_config = self.config.get_communication_config()

        # Security and resource limits from config
        self.max_message_size = comm_config.get(
            "max_message_size", 1024 * 1024
        )  # 1MB default
        self.max_history_size = comm_config.get("max_history_size", 5000)

        # Parse message TTL from config (supports hours)
        ttl_config = comm_config.get("message_ttl", {})
        ttl_hours = ttl_config.get("hours", 24)
        self.message_ttl = timedelta(hours=ttl_hours)

        logger.info("Agent communication bus initialized")

    def register_agent(self, agent_id: str) -> bool:
        """
        Register an agent with the communication bus.

        Args:
            agent_id: Unique identifier for the agent

        Returns:
            True if registration successful
        """
        if agent_id in self.agent_registry:
            logger.warning(f"Agent {agent_id} already registered")
            return False

        self.agent_registry[agent_id] = True
        # Access the queue to create it in the defaultdict
        _ = self.message_queues[agent_id]
        logger.info(f"Agent {agent_id} registered with communication bus")

        return True

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent from the communication bus.

        Args:
            agent_id: Unique identifier for the agent

        Returns:
            True if unregistration successful
        """
        if agent_id not in self.agent_registry:
            logger.warning(f"Agent {agent_id} not registered")
            return False

        # Stop processing task if running
        if agent_id in self._processing_tasks:
            self._processing_tasks[agent_id].cancel()
            del self._processing_tasks[agent_id]

        # Clean up
        del self.agent_registry[agent_id]
        if agent_id in self.message_queues:
            del self.message_queues[agent_id]
        if agent_id in self.message_handlers:
            del self.message_handlers[agent_id]
        if agent_id in self.statistics:
            del self.statistics[agent_id]

        logger.info(f"Agent {agent_id} unregistered from communication bus")
        return True

    def register_handler(
        self,
        agent_id: str,
        message_type: MessageType,
        handler: Callable,
        priority: int = 5,
    ):
        """
        Register a message handler for a specific message type.

        Args:
            agent_id: Agent identifier
            message_type: Type of message to handle
            handler: Async callable that handles the message
            priority: Handler priority (higher = called first)
        """
        message_handler = MessageHandler(
            message_type=message_type,
            handler=handler,
            agent_id=agent_id,
            priority=priority,
        )

        self.message_handlers[agent_id].append(message_handler)
        # Sort by priority (higher first)
        self.message_handlers[agent_id].sort(key=lambda h: h.priority, reverse=True)

        logger.debug(f"Registered handler for {message_type.value} in agent {agent_id}")

    def set_message_filter(
        self, agent_id: str, filter_func: Callable[[AgentMessage], bool]
    ):
        """
        Set a message filter for an agent.

        Args:
            agent_id: Agent identifier
            filter_func: Function that returns True if message should be processed
        """
        self.message_filters[agent_id] = filter_func

    async def start(self):
        """Start the communication bus and begin processing messages."""
        if self._running:
            logger.warning("Communication bus already running")
            return

        self._running = True
        logger.info("Communication bus started")

        # Start processing tasks for each registered agent
        for agent_id in self.agent_registry:
            self._processing_tasks[agent_id] = asyncio.create_task(
                self._process_agent_messages(agent_id)
            )

    async def stop(self):
        """Stop the communication bus."""
        if not self._running:
            return

        self._running = False

        # Cancel all processing tasks
        for task in self._processing_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._processing_tasks.values(), return_exceptions=True)

        self._processing_tasks.clear()
        logger.info("Communication bus stopped")

    def _validate_message(self, message: AgentMessage) -> tuple[bool, Optional[str]]:
        """
        Validate message before processing.

        Args:
            message: The message to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check message size
        try:
            content_str = str(len(str(message.content)))  # Approximate size check
            if content_str and int(content_str) > self.max_message_size:
                return (
                    False,
                    f"Message content too large (max {self.max_message_size} bytes)",
                )
        except (ValueError, TypeError):
            return False, "Unable to validate message size"

        # Validate message structure
        if not message.message_id:
            return False, "Message ID is required"

        if not message.sender:
            return False, "Message sender is required"

        # For non-broadcast messages, validate receiver
        if message.receiver and message.receiver not in self.agent_registry:
            return False, f"Receiver {message.receiver} not registered"

        return True, None

    def _add_message_to_history(self, message: AgentMessage) -> None:
        """
        Add message to history with TTL cleanup.

        Args:
            message: The message to add to history
        """
        self.message_history.append(message)

        # Remove old messages beyond TTL
        cutoff = datetime.now() - self.message_ttl
        self.message_history = [m for m in self.message_history if m.timestamp > cutoff]

        # Enforce size limit
        if len(self.message_history) > self.max_history_size:
            self.message_history = self.message_history[-self.max_history_size :]

    async def send_message(self, message: AgentMessage) -> bool:
        """
        Send a message to a specific agent.

        Args:
            message: The message to send

        Returns:
            True if message sent successfully
        """
        # Validate message first
        is_valid, error_msg = self._validate_message(message)
        if not is_valid:
            logger.error(f"Message validation failed: {error_msg}")
            return False

        # Check if message requires response
        if message.requires_response:
            future = asyncio.Future()
            self.pending_responses[message.message_id] = future

        # Add to receiver's queue
        try:
            await asyncio.wait_for(
                self.message_queues[message.receiver].put(message), timeout=5.0
            )

            # Update statistics
            self.statistics[message.sender]["messages_sent"] += 1
            self.statistics[message.receiver]["messages_received"] += 1

            # Add to history with TTL cleanup
            self._add_message_to_history(message)

            logger.debug(
                f"Message {message.message_id} sent from {message.sender} to {message.receiver}"
            )
            return True

        except asyncio.TimeoutError:
            logger.error(f"Timeout sending message to {message.receiver}")
            if (
                message.requires_response
                and message.message_id in self.pending_responses
            ):
                del self.pending_responses[message.message_id]
            return False

    async def broadcast_message(
        self, sender: str, message_type: MessageType, content: Dict[str, Any]
    ) -> List[str]:
        """
        Broadcast a message to all registered agents.

        Args:
            sender: Sender agent ID
            message_type: Type of message to broadcast
            content: Message content

        Returns:
            List of agent IDs that received the message
        """
        message = AgentMessage(
            type=message_type,
            sender=sender,
            receiver="",  # Empty for broadcast
            content=content,
            priority=5,
        )

        successful_receivers = []

        for agent_id in self.agent_registry:
            if agent_id != sender:  # Don't send to self
                message.receiver = agent_id
                if await self.send_message(message):
                    successful_receivers.append(agent_id)

        logger.info(f"Broadcast message sent to {len(successful_receivers)} agents")
        return successful_receivers

    async def wait_for_response(
        self, message_id: str, timeout: float = 30.0
    ) -> Optional[AgentMessage]:
        """
        Wait for a response to a message.

        Args:
            message_id: ID of the message to wait for response
            timeout: Maximum time to wait

        Returns:
            Response message or None if timeout
        """
        if message_id not in self.pending_responses:
            logger.warning(f"No pending response for message {message_id}")
            return None

        try:
            response = await asyncio.wait_for(
                self.pending_responses[message_id], timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to message {message_id}")
            return None
        finally:
            del self.pending_responses[message_id]

    async def _process_agent_messages(self, agent_id: str):
        """
        Process messages for a specific agent.

        Args:
            agent_id: Agent identifier
        """
        logger.info(f"Started processing messages for agent {agent_id}")

        while self._running and agent_id in self.agent_registry:
            try:
                # Get message with timeout
                message = await asyncio.wait_for(
                    self.message_queues[agent_id].get(), timeout=1.0
                )

                # Process message
                await self._handle_message(agent_id, message)

            except asyncio.TimeoutError:
                continue  # No message, continue loop
            except Exception as e:
                logger.error(f"Error processing message for agent {agent_id}: {e}")

        logger.info(f"Stopped processing messages for agent {agent_id}")

    async def _handle_message(self, agent_id: str, message: AgentMessage):
        """
        Handle an incoming message for an agent.

        Args:
            agent_id: Agent identifier
            message: The message to handle
        """
        # Apply message filter if exists
        if agent_id in self.message_filters:
            if not self.message_filters[agent_id](message):
                logger.debug(f"Message filtered for agent {agent_id}")
                return

        # Get handlers for this message type
        handlers = self.message_handlers.get(agent_id, [])
        relevant_handlers = [h for h in handlers if h.message_type == message.type]

        if not relevant_handlers:
            logger.debug(
                f"No handler for message type {message.type.value} in agent {agent_id}"
            )
            return

        # Call handlers in priority order
        for handler in relevant_handlers:
            try:
                response = await handler.handle(message)

                # Send response if required
                if response and message.reply_to:
                    await self.send_message(response)

                # Update statistics
                self.statistics[agent_id]["messages_handled"] += 1

            except Exception as e:
                logger.error(f"Error in handler for agent {agent_id}: {e}")
                self.statistics[agent_id]["handler_errors"] += 1

    def get_statistics(self) -> Dict[str, Dict[str, int]]:
        """
        Get communication statistics for all agents.

        Returns:
            Dictionary of statistics per agent
        """
        return dict(self.statistics)

    def get_agent_statistics(self, agent_id: str) -> Dict[str, int]:
        """
        Get statistics for a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Statistics dictionary
        """
        return dict(self.statistics.get(agent_id, {}))

    def get_message_history(
        self, agent_id: Optional[str] = None, limit: int = 100
    ) -> List[AgentMessage]:
        """
        Get message history with TTL filtering.

        Args:
            agent_id: Optional agent ID to filter by
            limit: Maximum number of messages to return

        Returns:
            List of messages
        """
        # Apply TTL filtering to all history queries
        cutoff = datetime.now() - self.message_ttl
        filtered_history = [m for m in self.message_history if m.timestamp > cutoff]

        # Filter by agent if specified
        if agent_id:
            filtered_history = [
                m
                for m in filtered_history
                if m.sender == agent_id or m.receiver == agent_id
            ]

        # Return most recent messages up to limit
        return filtered_history[-limit:]

    def clear_message_history(self):
        """Clear message history."""
        self.message_history.clear()
        logger.info("Message history cleared")

    def is_healthy(self) -> bool:
        """
        Check if communication bus is healthy.

        Returns:
            True if healthy
        """
        return self._running and len(self.agent_registry) > 0

    def __repr__(self) -> str:
        registered_count = len(self.agent_registry)
        handler_count = sum(
            len(handlers) for handlers in self.message_handlers.values()
        )
        return f"AgentCommunicationBus(agents={registered_count}, handlers={handler_count})"
