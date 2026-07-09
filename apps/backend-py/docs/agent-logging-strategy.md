# Agent System Logging Strategy

## Overview

This document establishes the logging strategy for the Job Raider multi-agent system to ensure consistent, maintainable, and production-ready logging across all agent components.

## Logging Levels

### Level Guidelines

| Level | Usage | Examples |
|-------|-------|----------|
| **DEBUG** | Detailed diagnostic information for development | Internal state changes, detailed processing steps, raw data dumps |
| **INFO** | Normal operational milestones | Agent startup/shutdown, task submissions, successful completions |
| **WARNING** | Unexpected but recoverable situations | Retries, fallbacks, missing non-critical data |
| **ERROR** | Errors that prevent specific operations | Task failures, API errors, validation failures |
| **CRITICAL** | System-level failures | Agent crashes, communication failures, data corruption |

### Agent-Specific Logging Guidelines

#### Coordinator (`agents.coordinator`)
- **INFO**: Agent registration/unregistration, pipeline orchestration start/completion, system status changes
- **WARNING**: Task submission failures, agent unavailable warnings, performance degradation
- **ERROR**: Coordinator startup failures, pipeline execution failures, agent communication errors
- **DEBUG**: Detailed scheduling decisions, performance tracking updates, agent selection logic

#### Communication Bus (`agents.communication`)
- **INFO**: Message sending/receiving milestones, agent registration, bus startup/shutdown
- **WARNING**: Message queue timeouts, slow message processing, duplicate registrations
- **ERROR**: Message validation failures, message sending failures, bus errors
- **DEBUG**: Message content details, handler execution tracking, queue statistics

#### Career Coach Agent (`agents.career_coach`)
- **INFO**: Task execution start/completion, analysis milestones, successful recommendations
- **WARNING**: Incomplete profile data, low-confidence results, missing market data
- **ERROR**: LLM call failures, analysis execution errors, data processing failures
- **DEBUG**: Analysis step details, intermediate results, confidence calculations

#### Base Agent (`agents.base`)
- **INFO**: Agent state changes (IDLE → READY → BUSY), task queue statistics
- **WARNING**: Task queue approaching capacity, performance degradation
- **ERROR**: Task execution failures, agent crashes, critical state inconsistencies
- **DEBUG**: Task processing details, performance metric updates, queue operations

#### API Routes (`api.routes.agents`)
- **INFO**: Successful API requests, rate limit warnings
- **WARNING**: Rate limit approaching, slow API responses, malformed requests (handled)
- **ERROR**: Request validation failures, coordinator errors, API exceptions
- **DEBUG**: Request details, response tracking, rate limiting details

## Logging Best Practices

### DO's ✅
1. **Use structured logging**: Include relevant context in log messages
   ```python
   logger.info(
       f"Task {task.task_id} submitted to agent {agent_id}",
       extra={"task_id": task.task_id, "agent_id": agent_id, "task_type": task.type.value}
   )
   ```

2. **Log at appropriate levels**: Use the guidelines above to determine correct log level

3. **Include context**: Add relevant metadata (task IDs, agent IDs, error codes)
   ```python
   logger.error(
       f"Error executing task {task.task_id}",
       exc_info=True,
       extra={"task_id": task.task_id, "task_type": task.type.value, "agent_id": self.agent_id}
   )
   ```

4. **Sanitize sensitive data**: Never log passwords, API keys, PII, or sensitive user data
   ```python
   is_production = os.getenv("ENVIRONMENT", "development") == "production"
   safe_error = "Task execution failed" if is_production else str(e)
   logger.error(f"Task failed: {safe_error}")
   ```

5. **Use consistent message formats**: Follow established patterns
   - Agent operations: "Agent {agent_id} {operation}"
   - Task operations: "Task {task_id} {operation} on agent {agent_id}"
   - Communication: "Message {message_id} {operation} from {sender} to {receiver}"

### DON'Ts ❌
1. **Don't log excessively**: Avoid spamming logs with repetitive messages
2. **Don't log in hot paths**: Minimize logging in performance-critical loops
3. **Don't expose sensitive data**: Sanitize errors in production environments
4. **Don't use console.log**: Use proper Python logging, not print statements
5. **Don't log raw exceptions without context**: Always include relevant context

## Configuration Updates

Add to `apps/backend-py/config/logging_config.yaml`:

```yaml
loggers:
  # Agent system loggers
  job_raider.agents:
    level: INFO
    handlers: [console, file_main, file_json]
    propagate: false

  job_raider.agents.coordinator:
    level: INFO
    handlers: [console, file_main, file_json]
    propagate: false

  job_raider.agents.communication:
    level: INFO
    handlers: [console, file_main, file_json]
    propagate: false

  job_raider.agents.career_coach:
    level: INFO
    handlers: [console, file_main, file_json]
    propagate: false

  job_raider.agents.base:
    level: WARNING
    handlers: [console, file_main]
    propagate: false

  job_raider.api.agents:
    level: INFO
    handlers: [console, file_main, file_json]
    propagate: false
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Error Rates**: Agent task failures, communication errors, API errors
2. **Performance**: Task execution times, queue lengths, agent utilization
3. **System Health**: Agent availability, communication bus health, coordinator status
4. **Rate Limiting**: Rate limit warnings, blocked requests, client behavior

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Agent error rate | > 5% | > 15% |
| Task execution time | > 30s | > 60s |
| Queue depth | > 100 | > 500 |
| Communication errors | > 1% | > 5% |
| Rate limit hits | > 10/min | > 50/min |

## Log Analysis

### Common Patterns to Watch

1. **Repeated Task Failures**: May indicate agent issues or data problems
2. **High Queue Depth**: May need more agent capacity or faster processing
3. **Communication Timeouts**: May indicate network issues or overloaded agents
4. **Rate Limit Warnings**: May indicate abuse or need for capacity planning

### Debugging Techniques

1. **Follow Task Flow**: Track task_id through logs to understand lifecycle
2. **Monitor Agent States**: Watch agent state transitions to identify bottlenecks
3. **Analyze Error Patterns**: Group similar errors to identify systemic issues
4. **Correlate with Metrics**: Combine logs with performance metrics for full picture

## Examples

### Good Logging Example
```python
logger.info(
    f"Agent {self.agent_id} processing task {task.task_id}",
    extra={
        "agent_id": self.agent_id,
        "task_id": task.task_id,
        "task_type": task.type.value,
        "priority": task.priority,
        "agent_state": self.state.value
    }
)

# Result in production:
# 2026-06-12 10:30:45 - agents.base - INFO - Agent career_coach processing task abc-123
# Context: {"agent_id": "career_coach", "task_id": "abc-123", "task_type": "career_analysis", "priority": 7, "agent_state": "busy"}
```

### Bad Logging Example
```python
print(f"Processing task...")  # ❌ Don't use print
logger.debug(f"Task data: {task.data}")  # ❌ Don't log raw sensitive data
logger.error(f"Error: {e}")  # ❌ Don't log without context
```

## Testing

### Log Testing Guidelines

1. **Unit Tests**: Verify log messages are generated at correct levels
2. **Integration Tests**: Verify logging across agent communication
3. **Production Tests**: Verify log rotation, file sizes, performance impact

### Example Test
```python
def test_agent_logging(caplog):
    agent = CareerCoachAgent(llm_router)
    task = Task(type=TaskType.CAREER_PATH_ANALYSIS, data={"profile": {}})

    with caplog.at_level(logging.INFO):
        result = await agent.execute_task(task, {})

    assert "Agent career_coach processing task" in caplog.text
    assert "Task execution completed" in caplog.text
    assert any(record.levelname == "INFO" for record in caplog.records)
```

## Maintenance

### Regular Reviews

1. **Quarterly**: Review log volumes and adjust levels if needed
2. **Annually**: Review logging strategy and update guidelines
3. **On Incident**: Review logs for missed information or noise

### Continuous Improvement

1. Monitor log file sizes and rotate appropriately
2. Remove obsolete logging statements
3. Add structured context for new features
4. Update documentation when adding new loggers
