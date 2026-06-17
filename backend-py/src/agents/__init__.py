"""
Job Raider Multi-Agent System

This package provides intelligent agent coordination for job matching,
career coaching, and personalized recommendations.
"""

from .base import AgentCapability, BaseAgent, Task, TaskResult, TaskType
from .career_coach import CareerCoachAgent
from .communication import AgentCommunicationBus, AgentMessage, MessageType
from .config_loader import AgentConfig, get_agent_config, reset_agent_config
from .coordinator import AgentCoordinator
from .error_handlers import (
    AgentError,
    ErrorCategory,
    ErrorHandler,
    ErrorSeverity,
    create_error_response,
    handle_task_execution_error,
    is_recoverable_error,
    log_agent_error,
    validate_request_data,
    wrap_agent_error,
)

__all__ = [
    "BaseAgent",
    "AgentCapability",
    "Task",
    "TaskResult",
    "TaskType",
    "AgentCommunicationBus",
    "AgentMessage",
    "MessageType",
    "AgentCoordinator",
    "CareerCoachAgent",
    "AgentError",
    "ErrorCategory",
    "ErrorSeverity",
    "ErrorHandler",
    "create_error_response",
    "handle_task_execution_error",
    "is_recoverable_error",
    "log_agent_error",
    "validate_request_data",
    "wrap_agent_error",
    "AgentConfig",
    "get_agent_config",
    "reset_agent_config",
]
