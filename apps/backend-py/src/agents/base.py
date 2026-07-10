"""
Base Agent Classes for Job Raider Multi-Agent System

Provides foundation classes for implementing intelligent agents
with coordinated communication and performance tracking.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Enumeration of all task types that agents can handle."""

    # Resume and Profile Tasks
    RESUME_PARSING = "resume_parsing"
    RESUME_ANALYSIS = "resume_analysis"
    SKILL_EXTRACTION = "skill_extraction"
    GAP_ANALYSIS = "gap_analysis"

    # Job and Market Tasks
    JD_EXTRACTION = "jd_extraction"
    CLASSIFICATION = "classification"
    TRUST_ANALYSIS = "trust_analysis"
    SALARY_ANALYSIS = "salary_analysis"

    # Matching and Scoring Tasks
    JOB_MATCHING = "job_matching"
    PROFILE_SCORING = "profile_scoring"
    RANKING = "ranking"

    # Career Coaching Tasks
    CAREER_PATH_ANALYSIS = "career_path_analysis"
    UPSKILLING_ROADMAP = "upskilling_roadmap"
    CAREER_GOAL_SETTING = "career_goal_setting"
    SKILL_DEVELOPMENT_PLAN = "skill_development_plan"

    # Assessment Tasks
    ASSESSMENT_GENERATION = "assessment_generation"
    ASSESSMENT_EVALUATION = "assessment_evaluation"

    # Pipeline Tasks
    PIPELINE_ORCHESTRATION = "pipeline_orchestration"
    VALIDATION = "validation"

    # General Tasks
    ANALYSIS = "analysis"
    RECOMMENDATION = "recommendation"


@dataclass
class Task:
    """Represents a task to be executed by an agent."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType = TaskType.ANALYSIS
    data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10, 10 being highest
    deadline: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __hash__(self):
        return hash(self.task_id)

    def __eq__(self, other):
        if not isinstance(other, Task):
            return False
        return self.task_id == other.task_id


@dataclass
class TaskResult:
    """Represents the result of a task execution."""

    task_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metrics": self.metrics,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
        }


@dataclass
class AgentCapability:
    """Defines the capabilities and requirements of an agent."""

    task_types: List[TaskType]
    parallel_execution: bool = True
    dependencies: List[str] = field(default_factory=list)
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    max_concurrent_tasks: int = 3
    average_execution_time: float = 5.0  # seconds

    def can_handle_task(self, task_type: TaskType) -> bool:
        """Check if agent can handle a specific task type."""
        return task_type in self.task_types

    def get_resource_score(self) -> float:
        """Calculate resource requirement score (0-1, lower is better)."""
        # Simple scoring based on memory and CPU requirements
        memory_req = self.resource_requirements.get("memory", "medium")
        cpu_req = self.resource_requirements.get("cpu", "medium")

        memory_scores = {"low": 0.2, "medium": 0.5, "high": 0.8}
        cpu_scores = {"low": 0.2, "medium": 0.5, "high": 0.8}

        return (memory_scores.get(memory_req, 0.5) + cpu_scores.get(cpu_req, 0.5)) / 2


class AgentState(Enum):
    """Possible states of an agent."""

    IDLE = "idle"
    BUSY = "busy"
    READY = "ready"
    FAILED = "failed"
    INITIALIZING = "initializing"


@dataclass
class AgentPerformance:
    """Tracks performance metrics for an agent."""

    agent_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    success_rate: float = 1.0
    last_execution_time: Optional[datetime] = None
    current_tasks: List[str] = field(default_factory=list)

    def update_execution(self, result: TaskResult, execution_time: float):
        """Update performance metrics after task execution."""
        self.tasks_completed += 1
        self.total_execution_time += execution_time
        self.average_execution_time = self.total_execution_time / self.tasks_completed
        self.last_execution_time = result.timestamp

        if not result.success:
            self.tasks_failed += 1

        # Calculate success rate
        total_tasks = self.tasks_completed
        self.success_rate = (
            (total_tasks - self.tasks_failed) / total_tasks if total_tasks > 0 else 1.0
        )

    def add_current_task(self, task_id: str):
        """Add a task to current task list."""
        if task_id not in self.current_tasks:
            self.current_tasks.append(task_id)

    def remove_current_task(self, task_id: str):
        """Remove a task from current task list."""
        if task_id in self.current_tasks:
            self.current_tasks.remove(task_id)

    def get_utilization(self) -> float:
        """Get current utilization (0-1)."""
        max_tasks = 3  # Default max concurrent tasks
        return len(self.current_tasks) / max_tasks

    def to_dict(self) -> Dict[str, Any]:
        """Convert performance to dictionary."""
        return {
            "agent_id": self.agent_id,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "total_execution_time": self.total_execution_time,
            "average_execution_time": self.average_execution_time,
            "success_rate": self.success_rate,
            "last_execution_time": (
                self.last_execution_time.isoformat()
                if self.last_execution_time
                else None
            ),
            "current_tasks": self.current_tasks,
            "utilization": self.get_utilization(),
        }


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the Job Raider multi-agent system.

    Provides common functionality for task execution, performance tracking,
    and communication coordination.
    """

    def __init__(self, agent_id: str, capabilities: AgentCapability):
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for this agent
            capabilities: Agent capability definition
        """
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.state = AgentState.INITIALIZING
        self.performance = AgentPerformance(agent_id=agent_id)
        self.communication_callback: Optional[Callable] = None
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

        logger.info(
            f"Agent {agent_id} initialized with capabilities: {[t.value for t in capabilities.task_types]}"
        )

    @abstractmethod
    async def execute_task(self, task: Task, context: Dict[str, Any]) -> TaskResult:
        """
        Execute an assigned task.

        Args:
            task: The task to execute
            context: Additional context for task execution

        Returns:
            TaskResult containing execution results
        """
        pass

    @abstractmethod
    async def validate_task(self, task: Task) -> bool:
        """
        Validate if a task can be executed by this agent.

        Args:
            task: The task to validate

        Returns:
            True if task is valid and can be executed
        """
        pass

    def get_capabilities(self) -> AgentCapability:
        """Return agent capabilities."""
        return self.capabilities

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "capabilities": {
                "task_types": [t.value for t in self.capabilities.task_types],
                "parallel_execution": self.capabilities.parallel_execution,
                "dependencies": self.capabilities.dependencies,
                "resource_requirements": self.capabilities.resource_requirements,
            },
            "performance": self.performance.to_dict(),
        }

    async def start(self):
        """Start the agent's main processing loop."""
        if self._running:
            logger.warning(f"Agent {self.agent_id} is already running")
            return

        self._running = True
        self.state = AgentState.READY
        logger.info(f"Agent {self.agent_id} started")

        # Start processing tasks from queue
        asyncio.create_task(self._process_task_queue())

    async def stop(self):
        """Stop the agent's processing loop."""
        self._running = False
        self.state = AgentState.IDLE
        logger.info(f"Agent {self.agent_id} stopped")

    async def submit_task(self, task: Task) -> str:
        """
        Submit a task to the agent's queue.

        Args:
            task: The task to submit

        Returns:
            Task ID for tracking
        """
        await self._task_queue.put(task)
        self.performance.add_current_task(task.task_id)

        logger.info(f"Task {task.task_id} submitted to agent {self.agent_id}")
        return task.task_id

    async def _process_task_queue(self):
        """Main processing loop for handling queued tasks."""
        while self._running:
            try:
                # Wait for task with timeout
                task = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)

                # Execute task
                await self._execute_and_track(task)

            except asyncio.TimeoutError:
                continue  # No task available, continue loop
            except Exception as e:
                logger.error(
                    f"Error processing task queue for agent {self.agent_id}: {e}"
                )

    async def _execute_and_track(self, task: Task):
        """
        Execute a task and track performance metrics.

        Args:
            task: The task to execute
        """
        self.state = AgentState.BUSY
        start_time = datetime.now()

        try:
            # Validate task
            if not await self.validate_task(task):
                result = TaskResult(
                    task_id=task.task_id, success=False, error="Task validation failed"
                )
            else:
                # Execute task
                result = await self.execute_task(task, task.context)

            # Track performance
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            self.performance.update_execution(result, execution_time)

            # Notify completion
            if self.communication_callback:
                await self.communication_callback(self.agent_id, result)

        except Exception as e:
            # Enhanced error logging with context and stack trace
            logger.error(
                f"Error executing task {task.task_id} in agent {self.agent_id}",
                exc_info=True,  # Include full stack trace
                extra={
                    "task_id": task.task_id,
                    "task_type": task.type.value,
                    "agent_id": self.agent_id,
                    "agent_state": self.state.value,
                },
            )

            # Sanitize error message for production (avoid exposing sensitive data)
            import os

            is_production = os.getenv("ENVIRONMENT", "development") == "production"
            safe_error = "Task execution failed" if is_production else str(e)

            # Create failure result
            execution_time = (datetime.now() - start_time).total_seconds()
            result = TaskResult(
                task_id=task.task_id,
                success=False,
                error=safe_error,
                execution_time=execution_time,
            )
            self.performance.update_execution(result, execution_time)

            # Notify coordinator of the failure so it can persist and broadcast it.
            if self.communication_callback:
                await self.communication_callback(self.agent_id, result)

        finally:
            # Clean up
            self.performance.remove_current_task(task.task_id)
            self.state = AgentState.READY

    def set_communication_callback(self, callback: Callable):
        """
        Set callback for communication notifications.

        Args:
            callback: Async callable that receives (agent_id, result)
        """
        self.communication_callback = callback

    async def health_check(self) -> bool:
        """
        Perform health check on the agent.

        Returns:
            True if agent is healthy
        """
        return self.state in [AgentState.READY, AgentState.BUSY] and self._running

    def __repr__(self) -> str:
        return f"BaseAgent(id={self.agent_id}, state={self.state.value})"
