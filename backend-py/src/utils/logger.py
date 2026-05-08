"""
Job Raider - Logger

This module provides structured logging configuration and utilities
for the Job Raider application.

Author: Job Raider
Date: 2026-04-20
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


# Component names for structured logging
class Components:
    """Logger names for different components."""
    ROOT = "job_raider"
    SCRAPERS = "job_raider.scrapers"
    LLM = "job_raider.llm"
    LLM_TOKENS = "job_raider.llm.tokens"
    SCORING = "job_raider.scoring"
    GENERATION = "job_raider.generation"
    PIPELINE = "job_raider.pipeline"
    SUBMISSION = "job_raider.submission"


def setup_logging(
    config_path: Optional[Path] = None,
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    console_output: bool = True,
) -> None:
    """
    Set up logging configuration for the application.

    Args:
        config_path: Path to logging config YAML file
        log_level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        console_output: Whether to output to console
    """
    # Create log directory if it doesn't exist
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

    # Try to load config from YAML file
    if config_path and config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            # Update paths in config
            if "handlers" in config:
                for handler_name, handler_config in config["handlers"].items():
                    if "filename" in handler_config and log_dir:
                        filename = handler_config["filename"]
                        # Convert relative paths to use log_dir
                        if not Path(filename).is_absolute():
                            handler_config["filename"] = str(log_dir / Path(filename).name)

            logging.config.dictConfig(config)
            return
        except Exception as e:
            print(f"Failed to load logging config from {config_path}: {e}", file=sys.stderr)

    # Fall back to basic configuration
    setup_basic_logging(log_level, log_dir, console_output)


def setup_basic_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    console_output: bool = True,
) -> None:
    """
    Set up basic logging configuration.

    Args:
        log_level: Default log level
        log_dir: Directory for log files
        console_output: Whether to output to console
    """
    # Create log directory if needed
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Add file handler
    if log_dir:
        file_handler = logging.FileHandler(log_dir / "job_raider.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Error log file
        error_handler = logging.FileHandler(log_dir / "errors.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific component.

    Args:
        name: Logger name (use Components class for standard names)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggingMixin:
    """
    Mixin class to add logging capabilities to any class.

    Usage:
        class MyClass(LoggingMixin):
            def __init__(self):
                self.logger = self.get_logger()
    """

    @property
    def logger_name(self) -> str:
        """Return the logger name for this class."""
        return f"{Components.ROOT}.{self.__class__.__name__}"

    def get_logger(self) -> logging.Logger:
        """Get a logger instance for this class."""
        return logging.getLogger(self.logger_name)


class TokenUsageLogger:
    """Specialized logger for tracking token usage and costs."""

    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize the token usage logger.

        Args:
            log_file: Path to token usage log file
        """
        self.logger = logging.getLogger(Components.LLM_TOKENS)
        self.log_file = log_file

        # Set up file handler if specified
        if log_file:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            handler = logging.FileHandler(log_file)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
            )
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        self._total_tokens = 0
        self._total_cost = 0.0

    def log_request(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        latency_ms: int,
        cached: bool = False,
    ) -> None:
        """
        Log a token usage request.

        Args:
            provider: Provider name (anthropic, ollama)
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            cost: Cost in USD
            latency_ms: Request latency in milliseconds
            cached: Whether response was from cache
        """
        total_tokens = prompt_tokens + completion_tokens
        self._total_tokens += total_tokens
        self._total_cost += cost

        log_data = {
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "latency_ms": latency_ms,
            "cached": cached,
        }

        self.logger.info(
            f"{provider} | {model} | "
            f"tokens: {prompt_tokens}+{completion_tokens}={total_tokens} | "
            f"cost: ${cost:.6f} | "
            f"latency: {latency_ms}ms | "
            f"cached: {cached}"
        )

    @property
    def total_tokens(self) -> int:
        """Return total tokens used."""
        return self._total_tokens

    @property
    def total_cost(self) -> float:
        """Return total cost incurred."""
        return self._total_cost

    def reset(self) -> None:
        """Reset token usage statistics."""
        self._total_tokens = 0
        self._total_cost = 0.0

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of token usage.

        Returns:
            Dictionary with usage statistics
        """
        return {
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "cost_per_token": (
                self._total_cost / self._total_tokens
                if self._total_tokens > 0 else 0.0
            ),
        }


# Singleton instance for easy access
_token_logger: Optional[TokenUsageLogger] = None


def get_token_logger(log_file: Optional[Path] = None) -> TokenUsageLogger:
    """
    Get the default token usage logger instance.

    Args:
        log_file: Path to token usage log file

    Returns:
        TokenUsageLogger instance
    """
    global _token_logger
    if _token_logger is None:
        _token_logger = TokenUsageLogger(log_file=log_file)
    return _token_logger
