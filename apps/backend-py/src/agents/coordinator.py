"""
Agent Coordinator for Job Raider Multi-Agent System

Provides central coordination for multi-agent collaboration,
task scheduling, and performance optimization.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..utils.logging_helpers import sanitize_for_log
from .base import AgentCapability, AgentState, BaseAgent, Task, TaskResult, TaskType
from .communication import AgentCommunicationBus, MessageType
from .config_loader import get_agent_config
from .task_store import TaskStore

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""

    LOW = 1
    MEDIUM = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class AgentInfo:
    """Information about a registered agent."""

    agent_id: str
    agent: BaseAgent
    registered_at: datetime = field(default_factory=datetime.now)
    state: AgentState = AgentState.INITIALIZING
    capabilities: Optional[AgentCapability] = None

    def get_utilization(self) -> float:
        """Get current utilization of the agent."""
        if self.agent:
            return self.agent.performance.get_utilization()
        return 0.0

    def is_available(self) -> bool:
        """Check if agent is available for new tasks."""
        if self.agent:
            return (
                self.agent.state == AgentState.READY
                and self.agent.performance.get_utilization() < 1.0
            )
        return False


@dataclass
class PipelineRequest:
    """Request to execute a pipeline with multiple stages."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stages: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None


@dataclass
class PipelineResult:
    """Result of pipeline execution."""

    request_id: str
    success: bool
    stage_results: Dict[str, Any] = field(default_factory=dict)
    agent_performance: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    errors: List[str] = field(default_factory=list)


class AgentCoordinator:
    """
    Central coordinator for multi-agent system.

    Manages agent registry, task scheduling, inter-agent communication,
    and performance optimization.
    """

    def __init__(self, communication_bus: Optional[AgentCommunicationBus] = None):
        """
        Initialize the agent coordinator.

        Args:
            communication_bus: Optional existing communication bus
        """
        self.communication_bus = communication_bus or AgentCommunicationBus()
        self.agents: Dict[str, AgentInfo] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.active_pipelines: Dict[str, PipelineRequest] = {}
        self.pipeline_results: Dict[str, PipelineResult] = {}

        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._performance_monitor_task: Optional[asyncio.Task] = None

        # Bounded in-memory store for task results.
        self.task_store = TaskStore()

        # Load configuration from external config file
        self.config = get_agent_config()
        coordinator_config = self.config.get_coordinator_config()
        self.max_concurrent_pipelines = coordinator_config.get(
            "max_concurrent_pipelines", 3
        )
        self.task_timeout = coordinator_config.get("task_timeout", 300.0)
        self.performance_check_interval = coordinator_config.get(
            "performance_check_interval", 30.0
        )

        logger.info("Agent coordinator initialized")

    async def start(self):
        """Start the coordinator and begin processing."""
        if self._running:
            logger.warning("Coordinator already running")
            return

        self._running = True

        # Start communication bus
        await self.communication_bus.start()

        # Start scheduler
        self._scheduler_task = asyncio.create_task(self._task_scheduler())

        # Start performance monitor
        self._performance_monitor_task = asyncio.create_task(
            self._performance_monitor()
        )

        logger.info("Agent coordinator started")

    async def stop(self):
        """Stop the coordinator and cleanup."""
        if not self._running:
            return

        self._running = False

        # Stop all agents
        for agent_info in self.agents.values():
            if agent_info.agent:
                await agent_info.agent.stop()

        # Stop communication bus
        await self.communication_bus.stop()

        # Cancel tasks
        if self._scheduler_task:
            self._scheduler_task.cancel()
        if self._performance_monitor_task:
            self._performance_monitor_task.cancel()

        # Wait for tasks to complete
        tasks = [t for t in [self._scheduler_task, self._performance_monitor_task] if t]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Agent coordinator stopped")

    def register_agent(self, agent: BaseAgent) -> bool:
        """
        Register an agent with the coordinator.

        Args:
            agent: The agent to register

        Returns:
            True if registration successful
        """
        if agent.agent_id in self.agents:
            logger.warning(f"Agent {agent.agent_id} already registered")
            return False

        # Register with communication bus
        if not self.communication_bus.register_agent(agent.agent_id):
            logger.error(
                f"Failed to register agent {agent.agent_id} with communication bus"
            )
            return False

        # Store agent info
        agent_info = AgentInfo(
            agent_id=agent.agent_id,
            agent=agent,
            state=agent.state,
            capabilities=agent.get_capabilities(),
        )

        self.agents[agent.agent_id] = agent_info

        # Set communication callback
        agent.set_communication_callback(self._handle_agent_message)

        # Start agent
        asyncio.create_task(agent.start())

        logger.info(f"Agent {agent.agent_id} registered with coordinator")
        return True

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent from the coordinator.

        Args:
            agent_id: ID of agent to unregister

        Returns:
            True if unregistration successful
        """
        if agent_id not in self.agents:
            logger.warning(f"Agent {agent_id} not registered")
            return False

        # Stop agent
        agent_info = self.agents[agent_id]
        if agent_info.agent:
            asyncio.create_task(agent_info.agent.stop())

        # Unregister from communication bus
        self.communication_bus.unregister_agent(agent_id)

        # Remove from registry
        del self.agents[agent_id]

        logger.info(f"Agent {agent_id} unregistered from coordinator")
        return True

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent status dictionary or None if not found
        """
        if agent_id not in self.agents:
            return None

        agent_info = self.agents[agent_id]
        if agent_info.agent:
            return agent_info.agent.get_status()
        return None

    def get_all_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all registered agents.

        Returns:
            Dictionary of agent statuses
        """
        statuses = {
            agent_id: self.get_agent_status(agent_id) for agent_id in self.agents.keys()
        }
        return {
            agent_id: status
            for agent_id, status in statuses.items()
            if status is not None
        }

    async def submit_task(self, task: Task, agent_id: Optional[str] = None) -> str:
        """
        Submit a task for execution.

        Args:
            task: The task to execute
            agent_id: Optional specific agent to execute the task

        Returns:
            Task ID for tracking
        """
        # If no specific agent, find best agent
        if not agent_id:
            agent_id = await self._find_best_agent(task.type)

        if not agent_id:
            logger.error(f"No available agent for task type {task.type.value}")
            # Create failed result
            return ""

        # Submit to agent
        if agent_id in self.agents:
            agent_info = self.agents[agent_id]
            if agent_info.agent:
                await agent_info.agent.submit_task(task)
                self.task_store.save(
                    task.task_id,
                    status="pending",
                    agent=agent_id,
                    task_type=task.type.value,
                )
                logger.info(f"Task {task.task_id} submitted to agent {agent_id}")
                return task.task_id

        logger.error(f"Failed to submit task {task.task_id}")
        return ""

    async def orchestrate_pipeline(self, request: PipelineRequest) -> PipelineResult:
        """
        Orchestrate a multi-stage pipeline execution.

        Args:
            request: Pipeline request with stages and context

        Returns:
            Pipeline execution results
        """
        start_time = datetime.now()

        logger.info(
            f"Starting pipeline {request.request_id} with {len(request.stages)} stages"
        )

        # Store active pipeline
        self.active_pipelines[request.request_id] = request

        try:
            # Execute stages
            stage_results: Dict[str, Any] = {}
            agent_performance: Dict[str, Any] = {}

            for stage_config in request.stages:
                stage_name = stage_config.get("name", "unknown")
                task_type = TaskType(stage_config.get("task_type", "analysis"))

                # Create task for stage
                task = Task(
                    type=task_type,
                    data=stage_config.get("data", {}),
                    context=request.context,
                    priority=request.priority,
                )

                # Execute stage
                task_id = await self.submit_task(task)
                if not task_id:
                    raise Exception(f"Failed to submit task for stage {stage_name}")

                # Wait for completion (simplified - in reality would be more complex)
                # For now, we'll just mark as submitted
                stage_results[stage_name] = {"task_id": task_id, "status": "submitted"}

            # Create result
            execution_time = (datetime.now() - start_time).total_seconds()

            result = PipelineResult(
                request_id=request.request_id,
                success=True,
                stage_results=stage_results,
                agent_performance=agent_performance,
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"Error in pipeline {request.request_id}: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()

            result = PipelineResult(
                request_id=request.request_id,
                success=False,
                execution_time=execution_time,
                errors=[str(e)],
            )

        finally:
            # Clean up
            if request.request_id in self.active_pipelines:
                del self.active_pipelines[request.request_id]

            self.pipeline_results[request.request_id] = result

        logger.info(f"Pipeline {request.request_id} completed in {execution_time:.2f}s")
        return result

    async def _find_best_agent(self, task_type: TaskType) -> Optional[str]:
        """
        Find the best available agent for a task type.

        Args:
            task_type: Type of task to execute

        Returns:
            Agent ID or None if no suitable agent found
        """
        suitable_agents = []

        for agent_id, agent_info in self.agents.items():
            # Check if agent can handle task type
            if agent_info.capabilities and agent_info.capabilities.can_handle_task(
                task_type
            ):
                # Check if agent is available
                if agent_info.is_available():
                    suitable_agents.append((agent_id, agent_info))

        if not suitable_agents:
            return None

        # Sort by utilization (lower is better) and success rate (higher is better)
        suitable_agents.sort(
            key=lambda info: (
                info[1].get_utilization(),
                -info[1].agent.performance.success_rate if info[1].agent else 0,
            )
        )

        return suitable_agents[0][0]

    async def _task_scheduler(self):
        """Main task scheduling loop."""
        logger.info("Task scheduler started")

        while self._running:
            try:
                # Check for pending tasks that need scheduling
                await asyncio.sleep(1.0)

                # Monitor active pipelines and reschedule if needed
                # This is a simplified version - real implementation would be more complex

            except Exception as e:
                logger.error(f"Error in task scheduler: {e}")

        logger.info("Task scheduler stopped")

    async def _performance_monitor(self):
        """Monitor agent performance and optimize scheduling."""
        logger.info("Performance monitor started")

        while self._running:
            try:
                await asyncio.sleep(self.performance_check_interval)

                # Collect performance metrics
                performance_data = {}
                for agent_id, agent_info in self.agents.items():
                    if agent_info.agent:
                        performance_data[agent_id] = {
                            "utilization": agent_info.get_utilization(),
                            "success_rate": agent_info.agent.performance.success_rate,
                            "tasks_completed": agent_info.agent.performance.tasks_completed,
                            "avg_execution_time": agent_info.agent.performance.average_execution_time,
                        }

                # Log performance summary
                if performance_data:
                    logger.debug(
                        "Agent performance: %s",
                        sanitize_for_log(performance_data),
                    )

                # Broadcast performance updates
                await self.communication_bus.broadcast_message(
                    sender="coordinator",
                    message_type=MessageType.PERFORMANCE_UPDATE,
                    content={"performance": performance_data},
                )

            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")

        logger.info("Performance monitor stopped")

    async def _handle_agent_message(self, agent_id: str, result: TaskResult):
        """
        Handle messages from agents.

        Stores the task result so clients can poll for it, then broadcasts a
        completion or failure message on the communication bus.

        Args:
            agent_id: Agent that sent the message
            result: Task execution result
        """
        logger.debug(
            "Received message from agent %s: task %s (success=%s)",
            agent_id,
            result.task_id,
            result.success,
        )

        # Persist the task outcome for asynchronous retrieval.
        status = "completed" if result.success else "failed"
        self.task_store.save(
            result.task_id,
            status=status,
            agent=agent_id,
            result=result.data if result.success else None,
            error=result.error if not result.success else None,
        )

        # Broadcast task completion
        await self.communication_bus.broadcast_message(
            sender=agent_id,
            message_type=(
                MessageType.TASK_COMPLETION
                if result.success
                else MessageType.TASK_FAILURE
            ),
            content={
                "task_id": result.task_id,
                "success": result.success,
                "error": result.error,
                "metrics": result.metrics,
            },
        )

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a stored task result by ID.

        Args:
            task_id: Task identifier returned by :meth:`submit_task`.

        Returns:
            Serialized task record if found, otherwise ``None``.
        """
        record = self.task_store.get(task_id)
        if record is None:
            return None
        return record.to_dict()

    def get_system_status(self) -> Dict[str, Any]:
        """
        Get overall system status.

        Returns:
            System status dictionary
        """
        agent_status = self.get_all_agent_status()

        return {
            "coordinator_running": self._running,
            "communication_healthy": self.communication_bus.is_healthy(),
            "registered_agents": len(self.agents),
            "active_pipelines": len(self.active_pipelines),
            "completed_pipelines": len(self.pipeline_results),
            "agent_status": agent_status,
            "communication_stats": self.communication_bus.get_statistics(),
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get system-wide performance metrics.

        Returns:
            Performance metrics dictionary
        """
        metrics: Dict[str, Any] = {
            "total_tasks_completed": 0,
            "total_tasks_failed": 0,
            "average_success_rate": 0.0,
            "average_execution_time": 0.0,
            "agent_utilization": {},
            "communication_stats": self.communication_bus.get_statistics(),
        }

        # Aggregate agent performance
        agent_count = 0
        for agent_id, agent_info in self.agents.items():
            if agent_info.agent:
                perf = agent_info.agent.performance
                metrics["total_tasks_completed"] += perf.tasks_completed
                metrics["total_tasks_failed"] += perf.tasks_failed
                metrics["agent_utilization"][agent_id] = agent_info.get_utilization()
                agent_count += 1

        # Calculate averages
        if agent_count > 0:
            total_success_rate = sum(
                self.agents[aid].agent.performance.success_rate
                for aid in self.agents
                if self.agents[aid].agent is not None
            )
            metrics["average_success_rate"] = total_success_rate / agent_count

            total_exec_time = sum(
                self.agents[aid].agent.performance.total_execution_time
                for aid in self.agents
                if self.agents[aid].agent is not None
            )
            metrics["average_execution_time"] = total_exec_time / agent_count

        return metrics

    async def health_check(self) -> bool:
        """
        Perform system health check.

        Returns:
            True if system is healthy
        """
        if not self._running:
            return False

        # Check communication bus
        if not self.communication_bus.is_healthy():
            return False

        # Check at least one agent is healthy
        healthy_agents = 0
        for agent_info in self.agents.values():
            if agent_info.agent and await agent_info.agent.health_check():
                healthy_agents += 1

        return healthy_agents > 0

    def __repr__(self) -> str:
        return f"AgentCoordinator(agents={len(self.agents)}, running={self._running})"
