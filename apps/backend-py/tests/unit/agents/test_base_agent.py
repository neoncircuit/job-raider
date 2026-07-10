"""
Unit tests for BaseAgent functionality.

Tests the core agent behavior including task execution, performance tracking,
and state management.
"""

import asyncio

import pytest

from src.agents.base import (
    AgentCapability,
    AgentPerformance,
    AgentState,
    BaseAgent,
    Task,
    TaskResult,
    TaskType,
)


class MockAgent(BaseAgent):
    """Mock implementation of BaseAgent for testing."""

    async def execute_task(self, task: Task, context: dict) -> TaskResult:
        """Mock task execution."""
        await asyncio.sleep(0.01)  # Simulate work

        return TaskResult(
            task_id=task.task_id,
            success=True,
            data={"result": "mock_result"},
            confidence=0.9,
        )

    async def validate_task(self, task: Task) -> bool:
        """Mock task validation."""
        return task.type in [TaskType.ANALYSIS, TaskType.CAREER_PATH_ANALYSIS]


@pytest.fixture
def mock_capability():
    """Fixture for mock agent capability."""
    return AgentCapability(
        task_types=[TaskType.ANALYSIS, TaskType.CAREER_PATH_ANALYSIS],
        parallel_execution=True,
        max_concurrent_tasks=3,
    )


@pytest.fixture
def mock_agent(mock_capability):
    """Fixture for mock agent instance."""
    return MockAgent(agent_id="test_agent", capabilities=mock_capability)


@pytest.fixture
def sample_task():
    """Fixture for sample task."""
    return Task(type=TaskType.ANALYSIS, data={"test_data": "value"}, priority=5)


class TestBaseAgent:
    """Test suite for BaseAgent functionality."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_agent):
        """Test agent initializes correctly."""
        assert mock_agent.agent_id == "test_agent"
        assert mock_agent.state == AgentState.INITIALIZING
        assert mock_agent.performance is not None
        assert mock_agent.performance.agent_id == "test_agent"

    @pytest.mark.asyncio
    async def test_agent_start_stop(self, mock_agent):
        """Test agent can start and stop."""
        await mock_agent.start()
        assert mock_agent.state == AgentState.READY
        assert mock_agent._running is True

        await mock_agent.stop()
        assert mock_agent.state == AgentState.IDLE
        assert mock_agent._running is False

    @pytest.mark.asyncio
    async def test_submit_task(self, mock_agent, sample_task):
        """Test task submission to agent queue."""
        await mock_agent.start()
        task_id = await mock_agent.submit_task(sample_task)

        assert task_id == sample_task.task_id
        assert task_id in mock_agent.performance.current_tasks

    @pytest.mark.asyncio
    async def test_task_execution(self, mock_agent, sample_task):
        """Test task execution updates performance metrics."""
        await mock_agent.start()

        result = await mock_agent.execute_task(sample_task, {})

        assert result.success is True
        assert result.task_id == sample_task.task_id
        assert result.data == {"result": "mock_result"}
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_task_validation(self, mock_agent):
        """Test task validation logic."""
        valid_task = Task(type=TaskType.ANALYSIS, data={})
        invalid_task = Task(type=TaskType.RESUME_PARSING, data={})

        assert await mock_agent.validate_task(valid_task) is True
        assert await mock_agent.validate_task(invalid_task) is False

    @pytest.mark.asyncio
    async def test_performance_tracking(self, mock_agent, sample_task):
        """Test performance metrics are tracked correctly."""
        await mock_agent.start()

        initial_completed = mock_agent.performance.tasks_completed
        initial_time = mock_agent.performance.total_execution_time

        result = await mock_agent.execute_task(sample_task, {})
        execution_time = 0.1
        mock_agent.performance.update_execution(result, execution_time)

        assert mock_agent.performance.tasks_completed == initial_completed + 1
        assert (
            mock_agent.performance.total_execution_time == initial_time + execution_time
        )
        assert mock_agent.performance.average_execution_time > 0

    @pytest.mark.asyncio
    async def test_health_check(self, mock_agent):
        """Test agent health check."""
        # Not started - should be unhealthy
        assert await mock_agent.health_check() is False

        await mock_agent.start()
        # Started - should be healthy
        assert await mock_agent.health_check() is True

        await mock_agent.stop()
        # Stopped - should be unhealthy
        assert await mock_agent.health_check() is False

    @pytest.mark.asyncio
    async def test_get_capabilities(self, mock_agent, mock_capability):
        """Test getting agent capabilities."""
        capabilities = mock_agent.get_capabilities()

        assert capabilities == mock_capability
        assert TaskType.ANALYSIS in capabilities.task_types
        assert capabilities.parallel_execution is True

    @pytest.mark.asyncio
    async def test_get_status(self, mock_agent):
        """Test getting agent status."""
        await mock_agent.start()
        status = mock_agent.get_status()

        assert status["agent_id"] == "test_agent"
        assert status["state"] == "ready"
        assert "capabilities" in status
        assert "performance" in status

    @pytest.mark.asyncio
    async def test_communication_callback(self, mock_agent, sample_task):
        """Test communication callback is called on task completion."""
        callback_called = asyncio.Event()
        callback_results = {}

        async def mock_callback(agent_id, result):
            callback_results["agent_id"] = agent_id
            callback_results["result"] = result
            callback_called.set()

        mock_agent.set_communication_callback(mock_callback)
        await mock_agent.start()

        await mock_agent.submit_task(sample_task)

        # Wait for task processing
        await asyncio.sleep(0.1)

        # Callback should have been called
        assert callback_called.is_set()


class TestAgentCapability:
    """Test suite for AgentCapability functionality."""

    def test_can_handle_task(self):
        """Test task capability checking."""
        capability = AgentCapability(
            task_types=[TaskType.ANALYSIS, TaskType.CAREER_PATH_ANALYSIS]
        )

        assert capability.can_handle_task(TaskType.ANALYSIS) is True
        assert capability.can_handle_task(TaskType.CAREER_PATH_ANALYSIS) is True
        assert capability.can_handle_task(TaskType.RESUME_PARSING) is False

    def test_get_resource_score(self):
        """Test resource requirement scoring."""
        low_resources = AgentCapability(
            task_types=[TaskType.ANALYSIS],
            resource_requirements={"memory": "low", "cpu": "low"},
        )
        high_resources = AgentCapability(
            task_types=[TaskType.ANALYSIS],
            resource_requirements={"memory": "high", "cpu": "high"},
        )

        low_score = low_resources.get_resource_score()
        high_score = high_resources.get_resource_score()

        assert low_score < high_score
        assert 0 <= low_score <= 1
        assert 0 <= high_score <= 1


class TestTask:
    """Test suite for Task functionality."""

    def test_task_creation(self):
        """Test task creation with defaults."""
        task = Task(type=TaskType.ANALYSIS, data={"test": "data"})

        assert task.type == TaskType.ANALYSIS
        assert task.data == {"test": "data"}
        assert task.priority == 5  # Default
        assert task.deadline is None
        assert task.dependencies == []

    def test_task_equality(self):
        """Test task equality based on task_id."""
        task1 = Task(type=TaskType.ANALYSIS, data={"test": "data"})
        task2 = Task(type=TaskType.ANALYSIS, data={"test": "data"})

        # Different IDs, so not equal
        assert task1 != task2

        # Same ID should be equal
        task2.task_id = task1.task_id
        assert task1 == task2

    def test_task_hash(self):
        """Test task is hashable (can be used in sets/dicts)."""
        task = Task(type=TaskType.ANALYSIS, data={})

        # Should not raise error
        task_set = {task}
        assert task in task_set


class TestTaskResult:
    """Test suite for TaskResult functionality."""

    def test_result_creation(self):
        """Test result creation."""
        result = TaskResult(
            task_id="test_id", success=True, data={"output": "result"}, confidence=0.85
        )

        assert result.task_id == "test_id"
        assert result.success is True
        assert result.data == {"output": "result"}
        assert result.confidence == 0.85
        assert result.execution_time == 0.0  # Default

    def test_result_to_dict(self):
        """Test result serialization to dictionary."""
        result = TaskResult(
            task_id="test_id", success=True, data={"output": "result"}, confidence=0.85
        )

        result_dict = result.to_dict()

        assert result_dict["task_id"] == "test_id"
        assert result_dict["success"] is True
        assert result_dict["confidence"] == 0.85
        assert "timestamp" in result_dict


class TestAgentPerformance:
    """Test suite for AgentPerformance functionality."""

    def test_performance_initialization(self):
        """Test performance metrics initialization."""
        performance = AgentPerformance(agent_id="test_agent")

        assert performance.agent_id == "test_agent"
        assert performance.tasks_completed == 0
        assert performance.tasks_failed == 0
        assert performance.success_rate == 1.0
        assert performance.current_tasks == []

    def test_update_execution(self):
        """Test performance update after task execution."""
        performance = AgentPerformance(agent_id="test_agent")

        result = TaskResult(task_id="test_id", success=True)
        performance.update_execution(result, 1.5)

        assert performance.tasks_completed == 1
        assert performance.total_execution_time == 1.5
        assert performance.average_execution_time == 1.5
        assert performance.last_execution_time is not None

    def test_update_execution_with_failure(self):
        """Test performance update with failed task."""
        performance = AgentPerformance(agent_id="test_agent")

        result = TaskResult(task_id="test_id", success=False)
        performance.update_execution(result, 1.0)

        assert performance.tasks_completed == 1
        assert performance.tasks_failed == 1
        assert performance.success_rate == 0.0

    def test_add_remove_current_task(self):
        """Test adding and removing current tasks."""
        performance = AgentPerformance(agent_id="test_agent")

        performance.add_current_task("task1")
        assert "task1" in performance.current_tasks

        performance.remove_current_task("task1")
        assert "task1" not in performance.current_tasks

    def test_get_utilization(self):
        """Test utilization calculation."""
        performance = AgentPerformance(agent_id="test_agent")

        # No tasks - zero utilization
        assert performance.get_utilization() == 0.0

        # Add some tasks
        performance.add_current_task("task1")
        performance.add_current_task("task2")

        utilization = performance.get_utilization()
        assert 0.0 < utilization <= 1.0

    def test_to_dict(self):
        """Test performance serialization."""
        performance = AgentPerformance(agent_id="test_agent")
        performance.add_current_task("task1")

        perf_dict = performance.to_dict()

        assert perf_dict["agent_id"] == "test_agent"
        assert perf_dict["tasks_completed"] == 0
        assert "utilization" in perf_dict
