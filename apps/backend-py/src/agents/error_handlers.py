"""
Common Error Handling Utilities for Job Raider Multi-Agent System

Provides standardized error handling, logging, and response generation
for agent operations to reduce code duplication and ensure consistency.
"""

import logging
import os
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better organization and filtering."""

    VALIDATION = "validation"
    EXECUTION = "execution"
    COMMUNICATION = "communication"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"
    AUTHENTICATION = "authentication"
    UNKNOWN = "unknown"


class AgentError(Exception):
    """
    Base exception class for agent-related errors.

    Provides structured error information with context,
    severity, and category for better error handling.
    """

    def __init__(
        self,
        message: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize agent error with comprehensive context.

        Args:
            message: Human-readable error message
            agent_id: Agent that encountered the error
            task_id: Task that failed
            severity: Error severity level
            category: Error category for classification
            context: Additional error context
            original_error: Original exception if wrapping another error
        """
        super().__init__(message)
        self.message = message
        self.agent_id = agent_id
        self.task_id = task_id
        self.severity = severity
        self.category = category
        self.context = context or {}
        self.original_error = original_error
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "message": self.message,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


def log_agent_error(
    error: Exception,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    include_stack_trace: bool = True,
) -> None:
    """
    Log agent error with standardized format and context.

    Args:
        error: The exception to log
        agent_id: Agent that encountered the error
        task_id: Task that failed
        context: Additional error context
        include_stack_trace: Whether to include full stack trace
    """
    # Determine if production environment
    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    # Sanitize error message for production
    error_message = str(error)
    if is_production and isinstance(error, AgentError):
        safe_message = f"{error.category.value.upper()}: {error.message}"
    elif is_production:
        safe_message = "Operation failed"
    else:
        safe_message = error_message

    # Build log context
    log_context = {
        "agent_id": agent_id,
        "task_id": task_id,
        "error_type": type(error).__name__,
    }

    if context:
        log_context.update(context)

    if isinstance(error, AgentError):
        log_context.update(
            {"severity": error.severity.value, "category": error.category.value}
        )

    # Log with appropriate level
    if isinstance(error, AgentError) and error.severity == ErrorSeverity.CRITICAL:
        logger.critical(safe_message, exc_info=include_stack_trace, extra=log_context)
    elif isinstance(error, AgentError) and error.severity == ErrorSeverity.HIGH:
        logger.error(safe_message, exc_info=include_stack_trace, extra=log_context)
    elif isinstance(error, AgentError) and error.severity == ErrorSeverity.MEDIUM:
        logger.warning(safe_message, exc_info=include_stack_trace, extra=log_context)
    else:
        logger.info(safe_message, exc_info=include_stack_trace, extra=log_context)


def handle_task_execution_error(
    error: Exception,
    agent_id: str,
    task_id: str,
    task_type: Optional[str] = None,
    execution_time: Optional[float] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Handle task execution errors with standardized response.

    Args:
        error: The exception that occurred
        agent_id: Agent that encountered the error
        task_id: Task that failed
        task_type: Type of task that failed
        execution_time: Time elapsed before failure

    Returns:
        Tuple of (success, error_message, error_context)
    """
    # Log the error
    log_agent_error(
        error,
        agent_id=agent_id,
        task_id=task_id,
        context={"task_type": task_type, "execution_time": execution_time},
    )

    # Determine error message
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    if is_production:
        safe_message = "Task execution failed"
    else:
        safe_message = str(error)

    # Build error context
    error_context = {
        "agent_id": agent_id,
        "task_id": task_id,
        "task_type": task_type,
        "execution_time": execution_time,
        "timestamp": datetime.now().isoformat(),
    }

    if isinstance(error, AgentError):
        error_context.update(
            {
                "severity": error.severity.value,
                "category": error.category.value,
                "context": error.context,
            }
        )

    return False, safe_message, error_context


def validate_request_data(
    data: Dict[str, Any],
    required_fields: list[str],
    field_validators: Optional[Dict[str, callable]] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate request data with required fields and custom validators.

    Args:
        data: Request data to validate
        required_fields: List of required field names
        field_validators: Optional dict of field_name -> validator function

    Returns:
        Tuple of (is_valid, error_message, validated_data)
    """
    if not isinstance(data, dict):
        return False, "Request data must be a dictionary", {}

    # Check required fields
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}", {}

    # Apply field validators
    validation_errors = []
    validated_data = data.copy()

    if field_validators:
        for field_name, validator in field_validators.items():
            if field_name in data:
                try:
                    validated_data[field_name] = validator(data[field_name])
                except (ValueError, TypeError) as e:
                    validation_errors.append(f"{field_name}: {str(e)}")

    if validation_errors:
        return False, f"Validation errors: {', '.join(validation_errors)}", {}

    return True, None, validated_data


def create_error_response(
    error: Exception,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    include_details: bool = False,
) -> Dict[str, Any]:
    """
    Create standardized error response for API endpoints.

    Args:
        error: The exception that occurred
        agent_id: Agent that encountered the error
        task_id: Task that failed
        include_details: Whether to include detailed error information

    Returns:
        Dictionary with error response structure
    """
    is_production = os.getenv("ENVIRONMENT", "development") == "production"

    if isinstance(error, AgentError):
        error_response = {
            "success": False,
            "error": {
                "message": error.message if not is_production else "Operation failed",
                "category": error.category.value,
                "severity": error.severity.value,
                "timestamp": error.timestamp.isoformat(),
            },
        }

        if include_details and not is_production:
            error_response["error"].update(
                {
                    "agent_id": error.agent_id,
                    "task_id": error.task_id,
                    "context": error.context,
                }
            )

            if error.original_error:
                error_response["error"]["original_error"] = str(error.original_error)
    else:
        error_response = {
            "success": False,
            "error": {
                "message": str(error) if not is_production else "Operation failed",
                "type": type(error).__name__,
                "timestamp": datetime.now().isoformat(),
            },
        }

        if include_details and not is_production:
            error_response["error"].update({"agent_id": agent_id, "task_id": task_id})

    return error_response


def wrap_agent_error(
    error: Exception,
    message: str,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
) -> AgentError:
    """
    Wrap an exception in an AgentError with additional context.

    Args:
        error: Original exception to wrap
        message: New error message
        agent_id: Agent that encountered the error
        task_id: Task that failed
        severity: Error severity level
        category: Error category

    Returns:
        AgentError instance wrapping the original error
    """
    return AgentError(
        message=message,
        agent_id=agent_id,
        task_id=task_id,
        severity=severity,
        category=category,
        original_error=error,
    )


def is_recoverable_error(error: Exception) -> bool:
    """
    Determine if an error is recoverable.

    Args:
        error: The exception to evaluate

    Returns:
        True if error is potentially recoverable
    """
    if isinstance(error, AgentError):
        # Critical errors are not recoverable
        if error.severity == ErrorSeverity.CRITICAL:
            return False
        # Resource and configuration errors might be recoverable
        if error.category in [ErrorCategory.RESOURCE, ErrorCategory.CONFIGURATION]:
            return True
        return False

    # Network/timeout errors are often recoverable
    error_type = type(error).__name__
    recoverable_types = [
        "TimeoutError",
        "ConnectionError",
        "HTTPError",
        "RequestException",
    ]

    return any(err_type in error_type for err_type in recoverable_types)


def calculate_retry_delay(
    attempt: int, base_delay: float = 1.0, max_delay: float = 60.0
) -> float:
    """
    Calculate retry delay with exponential backoff.

    Args:
        attempt: Current retry attempt number (1-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay time in seconds
    """
    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
    return delay


class ErrorHandler:
    """
    Context manager for standardized error handling.

    Provides automatic error logging and context management
    for agent operations.
    """

    def __init__(
        self,
        operation: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        raise_on_error: bool = True,
    ):
        """
        Initialize error handler context manager.

        Args:
            operation: Description of the operation being performed
            agent_id: Agent performing the operation
            task_id: Task being processed
            raise_on_error: Whether to re-raise exceptions after handling
        """
        self.operation = operation
        self.agent_id = agent_id
        self.task_id = task_id
        self.raise_on_error = raise_on_error
        self.error_occurred = False
        self.error: Optional[Exception] = None

    def __enter__(self):
        """Enter context manager."""
        logger.debug(f"Starting operation: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager with error handling."""
        if exc_type is not None:
            self.error_occurred = True
            self.error = exc_val

            # Log the error
            log_agent_error(
                exc_val,
                agent_id=self.agent_id,
                task_id=self.task_id,
                context={"operation": self.operation},
            )

            # Don't re-raise if configured
            if not self.raise_on_error:
                return True  # Suppress exception

        return False  # Re-raise if needed

    def get_error_summary(self) -> Optional[Dict[str, Any]]:
        """Get summary of error that occurred."""
        if not self.error_occurred or self.error is None:
            return None

        return create_error_response(
            self.error,
            agent_id=self.agent_id,
            task_id=self.task_id,
            include_details=True,
        )
