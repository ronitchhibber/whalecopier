"""
Orchestrator Agent - Multi-Agent System Coordinator
Part of Hybrid MAS Architecture (HYBRID_MAS_ARCHITECTURE.md)

This is the master coordinator for the entire multi-agent trading system.

Core Responsibilities:
1. Task delegation and coordination across all agents
2. Agent health monitoring (heartbeats, liveness checks)
3. Circuit breaker management for fault tolerance
4. Conflict resolution when agents disagree
5. State checkpointing and recovery
6. Event routing and message passing
7. Performance monitoring and alerting

Coordination Strategy:
- Event-driven architecture (Kafka/NATS messaging)
- LangGraph for task graph construction
- Parallel execution when possible
- Sequential execution when dependencies exist
- Circuit breaker pattern for failing agents

Message Contracts:
- Subscribes: ALL agent events
- Publishes: TaskAssigned, TaskCompleted, OrchestratorDecision, AgentHealthAlert

Performance Targets:
- 99.9% system uptime
- <45s end-to-end decision latency
- <5s agent health check interval
- Auto-restart failed agents within 30s

Author: Whale Trader v2.0 MAS
Date: November 2025
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Callable, Any
from collections import defaultdict, deque
import time

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RESTARTING = "restarting"
    STOPPED = "stopped"


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests (agent failing)
    HALF_OPEN = "half_open"  # Testing recovery


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1  # Risk checks, emergency deleveraging
    HIGH = 2  # Whale discovery, trade execution
    NORMAL = 3  # Attribution, performance tracking
    LOW = 4  # Analytics, reporting


@dataclass
class OrchestratorConfig:
    """Configuration for Orchestrator Agent"""

    # Agent health monitoring
    heartbeat_interval_seconds: int = 30  # Agent heartbeat frequency
    health_check_timeout_seconds: int = 10  # Max time for health check response
    max_missed_heartbeats: int = 3  # Trigger failure after N missed beats
    auto_restart_enabled: bool = True  # Auto-restart failed agents

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5  # Open after N failures
    circuit_breaker_success_threshold: int = 2  # Close after N successes
    circuit_breaker_timeout_seconds: int = 60  # Time in OPEN before HALF_OPEN

    # Task execution
    max_parallel_tasks: int = 10  # Max concurrent tasks
    task_timeout_seconds: int = 300  # 5 minutes
    max_retry_attempts: int = 3

    # Performance
    decision_latency_sla_ms: int = 45000  # 45 seconds SLA
    enable_performance_monitoring: bool = True

    # State management
    checkpoint_interval_seconds: int = 300  # 5 minutes
    enable_event_sourcing: bool = True


@dataclass
class AgentHealth:
    """Health status for a single agent"""

    agent_name: str
    status: AgentStatus
    last_heartbeat: datetime
    missed_heartbeats: int
    total_tasks_assigned: int
    total_tasks_completed: int
    total_tasks_failed: int
    average_task_duration_ms: float
    circuit_breaker_state: CircuitBreakerState
    last_error: Optional[str] = None
    restart_count: int = 0


@dataclass
class Task:
    """Represents a task to be executed by an agent"""

    task_id: str
    task_type: str  # e.g., "process_whale_candidate", "approve_trade"
    agent_name: str  # Target agent
    priority: TaskPriority
    payload: Dict
    dependencies: List[str] = field(default_factory=list)  # Task IDs
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class CircuitBreaker:
    """Circuit breaker for an agent"""

    agent_name: str
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.now)


class OrchestratorAgent:
    """
    Master coordinator for the multi-agent trading system.

    Implements:
    - Event-driven task delegation
    - Agent health monitoring with auto-restart
    - Circuit breaker pattern for fault tolerance
    - Conflict resolution
    - State checkpointing
    """

    def __init__(self, config: OrchestratorConfig = None):
        """
        Initialize Orchestrator Agent.

        Args:
            config: Configuration object
        """
        self.config = config or OrchestratorConfig()

        # Agent registry
        self.agents: Dict[str, AgentHealth] = {}
        self.agent_instances: Dict[str, Any] = {}  # Actual agent objects

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Task management
        self.task_queue: deque = deque()  # Priority queue
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.task_counter: int = 0

        # Event bus (placeholder - would use Kafka/NATS in production)
        self.event_bus: List[Dict] = []
        self.event_subscribers: Dict[str, List[Callable]] = defaultdict(list)

        # Performance tracking
        self.orchestrator_stats = {
            'total_decisions': 0,
            'total_conflicts_resolved': 0,
            'total_agents_restarted': 0,
            'total_circuit_breakers_opened': 0,
            'avg_decision_latency_ms': 0.0,
            'system_uptime_pct': 100.0,
            'last_checkpoint_time': None
        }

        # State checkpoint
        self.state_snapshots: List[Dict] = []

        logger.info("OrchestratorAgent initialized")

    def register_agent(self, agent_name: str, agent_instance: Any):
        """
        Register an agent with the orchestrator.

        Args:
            agent_name: Unique agent identifier
            agent_instance: Agent object instance
        """
        self.agents[agent_name] = AgentHealth(
            agent_name=agent_name,
            status=AgentStatus.HEALTHY,
            last_heartbeat=datetime.now(),
            missed_heartbeats=0,
            total_tasks_assigned=0,
            total_tasks_completed=0,
            total_tasks_failed=0,
            average_task_duration_ms=0.0,
            circuit_breaker_state=CircuitBreakerState.CLOSED
        )

        self.agent_instances[agent_name] = agent_instance

        self.circuit_breakers[agent_name] = CircuitBreaker(
            agent_name=agent_name
        )

        logger.info(f"✅ Registered agent: {agent_name}")

    async def orchestration_loop(self):
        """
        Main orchestration loop.

        Runs continuously to:
        1. Monitor agent health
        2. Process task queue
        3. Handle events
        4. Checkpoint state
        """
        logger.info("🎯 Starting orchestration loop")

        while True:
            try:
                loop_start = time.time()

                # 1. Check agent health
                await self._check_agent_health()

                # 2. Process task queue
                await self._process_task_queue()

                # 3. Handle pending events
                await self._process_events()

                # 4. Checkpoint state (every 5 minutes)
                if self._should_checkpoint():
                    await self._checkpoint_state()

                # Sleep to maintain loop interval
                loop_duration = time.time() - loop_start
                sleep_time = max(1.0 - loop_duration, 0.1)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in orchestration loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _check_agent_health(self):
        """
        Check health of all registered agents.

        Sends heartbeat requests and tracks responses.
        Auto-restarts failed agents if enabled.
        """
        current_time = datetime.now()

        for agent_name, health in self.agents.items():
            # Check if heartbeat is overdue
            time_since_heartbeat = (current_time - health.last_heartbeat).total_seconds()

            if time_since_heartbeat > self.config.heartbeat_interval_seconds:
                health.missed_heartbeats += 1

                if health.missed_heartbeats >= self.config.max_missed_heartbeats:
                    # Agent is failing!
                    if health.status != AgentStatus.FAILED:
                        logger.error(
                            f"🚨 Agent {agent_name} FAILED | "
                            f"Missed {health.missed_heartbeats} heartbeats"
                        )
                        health.status = AgentStatus.FAILED

                        # Open circuit breaker
                        await self._open_circuit_breaker(agent_name)

                        # Auto-restart if enabled
                        if self.config.auto_restart_enabled:
                            await self._restart_agent(agent_name)

                elif health.status == AgentStatus.HEALTHY:
                    health.status = AgentStatus.DEGRADED
                    logger.warning(
                        f"⚠️  Agent {agent_name} DEGRADED | "
                        f"Missed {health.missed_heartbeats} heartbeats"
                    )

            # Request heartbeat
            await self._request_heartbeat(agent_name)

    async def _request_heartbeat(self, agent_name: str):
        """Request heartbeat from agent"""
        # Placeholder - would send heartbeat request via message bus
        # In production: publish "heartbeat_request" event, agent responds
        pass

    def receive_heartbeat(self, agent_name: str):
        """
        Receive heartbeat from agent.

        Called by agents to report they're alive.

        Args:
            agent_name: Agent identifier
        """
        if agent_name in self.agents:
            health = self.agents[agent_name]
            health.last_heartbeat = datetime.now()
            health.missed_heartbeats = 0

            # Restore to healthy if was degraded
            if health.status == AgentStatus.DEGRADED:
                health.status = AgentStatus.HEALTHY
                logger.info(f"✅ Agent {agent_name} recovered to HEALTHY")

    async def _open_circuit_breaker(self, agent_name: str):
        """
        Open circuit breaker for failing agent.

        Args:
            agent_name: Agent identifier
        """
        if agent_name in self.circuit_breakers:
            cb = self.circuit_breakers[agent_name]
            cb.state = CircuitBreakerState.OPEN
            cb.last_failure_time = datetime.now()
            cb.last_state_change = datetime.now()

            # Update agent health
            if agent_name in self.agents:
                self.agents[agent_name].circuit_breaker_state = CircuitBreakerState.OPEN

            # Publish alert
            self._publish_event('AgentHealthAlert', {
                'agent_name': agent_name,
                'alert_type': 'circuit_breaker_opened',
                'message': f"Circuit breaker OPENED for {agent_name}",
                'timestamp': datetime.now().isoformat()
            })

            self.orchestrator_stats['total_circuit_breakers_opened'] += 1

            logger.error(f"🔴 Circuit breaker OPENED for {agent_name}")

    async def _restart_agent(self, agent_name: str):
        """
        Restart a failed agent.

        Args:
            agent_name: Agent identifier
        """
        if agent_name in self.agents:
            health = self.agents[agent_name]
            health.status = AgentStatus.RESTARTING
            health.restart_count += 1

            logger.info(f"🔄 Restarting agent: {agent_name} (attempt {health.restart_count})")

            try:
                # Restart agent (placeholder - would use Kubernetes API or process manager)
                # In production: kubectl rollout restart deployment/{agent_name}
                await asyncio.sleep(2)  # Simulate restart

                # Reset health
                health.status = AgentStatus.HEALTHY
                health.missed_heartbeats = 0
                health.last_heartbeat = datetime.now()

                # Reset circuit breaker
                if agent_name in self.circuit_breakers:
                    self.circuit_breakers[agent_name].state = CircuitBreakerState.HALF_OPEN
                    self.agents[agent_name].circuit_breaker_state = CircuitBreakerState.HALF_OPEN

                self.orchestrator_stats['total_agents_restarted'] += 1

                logger.info(f"✅ Agent {agent_name} restarted successfully")

            except Exception as e:
                logger.error(f"Failed to restart {agent_name}: {e}")
                health.status = AgentStatus.FAILED

    async def _process_task_queue(self):
        """
        Process pending tasks from the queue.

        Executes tasks in priority order, respecting dependencies.
        """
        # Get up to N tasks (based on concurrency limit)
        available_slots = self.config.max_parallel_tasks - len(self.active_tasks)

        if available_slots <= 0:
            return  # All slots occupied

        # Sort queue by priority
        sorted_queue = sorted(
            self.task_queue,
            key=lambda t: (t.priority.value, t.created_at)
        )

        tasks_to_execute = []

        for task in sorted_queue[:available_slots]:
            # Check if dependencies are met
            if self._are_dependencies_met(task):
                tasks_to_execute.append(task)

        # Execute tasks
        for task in tasks_to_execute:
            self.task_queue.remove(task)
            await self._execute_task(task)

    def _are_dependencies_met(self, task: Task) -> bool:
        """
        Check if all task dependencies are completed.

        Args:
            task: Task to check

        Returns:
            True if dependencies are met
        """
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False  # Dependency not yet completed
        return True

    async def _execute_task(self, task: Task):
        """
        Execute a task by delegating to the appropriate agent.

        Args:
            task: Task to execute
        """
        decision_start = time.time()

        # Check circuit breaker
        if task.agent_name in self.circuit_breakers:
            cb = self.circuit_breakers[task.agent_name]

            if cb.state == CircuitBreakerState.OPEN:
                # Check if timeout elapsed (try HALF_OPEN)
                time_since_failure = (datetime.now() - cb.last_failure_time).total_seconds()

                if time_since_failure > self.config.circuit_breaker_timeout_seconds:
                    cb.state = CircuitBreakerState.HALF_OPEN
                    cb.last_state_change = datetime.now()
                    logger.info(f"🟡 Circuit breaker HALF_OPEN for {task.agent_name}")
                else:
                    # Circuit still open, fail task immediately
                    task.error = f"Circuit breaker OPEN for {task.agent_name}"
                    self.completed_tasks[task.task_id] = task
                    logger.warning(f"⚠️  Task {task.task_id} failed due to open circuit breaker")
                    return

        # Mark task as active
        task.started_at = datetime.now()
        self.active_tasks[task.task_id] = task

        # Update agent stats
        if task.agent_name in self.agents:
            self.agents[task.agent_name].total_tasks_assigned += 1

        # Publish task assignment event
        self._publish_event('TaskAssigned', {
            'task_id': task.task_id,
            'task_type': task.task_type,
            'agent_name': task.agent_name,
            'priority': task.priority.value,
            'timestamp': datetime.now().isoformat()
        })

        try:
            # Execute task (call agent method)
            agent_instance = self.agent_instances.get(task.agent_name)

            if agent_instance:
                # Call agent method based on task type
                method_name = f"process_{task.task_type}"
                if hasattr(agent_instance, method_name):
                    method = getattr(agent_instance, method_name)
                    result = await method(task.payload)
                    task.result = result
                else:
                    raise AttributeError(f"Agent {task.agent_name} has no method {method_name}")
            else:
                raise ValueError(f"Agent {task.agent_name} not found")

            # Task succeeded
            task.completed_at = datetime.now()
            self.completed_tasks[task.task_id] = task
            del self.active_tasks[task.task_id]

            # Update agent stats
            if task.agent_name in self.agents:
                health = self.agents[task.agent_name]
                health.total_tasks_completed += 1

                # Update average duration
                duration_ms = (task.completed_at - task.started_at).total_seconds() * 1000
                n = health.total_tasks_completed
                health.average_task_duration_ms = (
                    (health.average_task_duration_ms * (n - 1) + duration_ms) / n
                )

            # Handle circuit breaker success
            await self._handle_task_success(task)

            # Publish task completed event
            self._publish_event('TaskCompleted', {
                'task_id': task.task_id,
                'agent_name': task.agent_name,
                'duration_ms': duration_ms,
                'timestamp': datetime.now().isoformat()
            })

            # Track decision latency
            decision_latency_ms = (time.time() - decision_start) * 1000
            self._update_decision_latency(decision_latency_ms)

            logger.debug(
                f"✅ Task completed | "
                f"ID: {task.task_id} | "
                f"Agent: {task.agent_name} | "
                f"Duration: {duration_ms:.0f}ms"
            )

        except Exception as e:
            # Task failed
            task.error = str(e)
            task.retry_count += 1

            # Retry or fail
            if task.retry_count < self.config.max_retry_attempts:
                # Retry
                logger.warning(
                    f"⚠️  Task {task.task_id} failed, retrying "
                    f"({task.retry_count}/{self.config.max_retry_attempts})"
                )
                task.started_at = None
                self.task_queue.append(task)
                del self.active_tasks[task.task_id]
            else:
                # Fail permanently
                task.completed_at = datetime.now()
                self.completed_tasks[task.task_id] = task
                del self.active_tasks[task.task_id]

                if task.agent_name in self.agents:
                    self.agents[task.agent_name].total_tasks_failed += 1

                # Handle circuit breaker failure
                await self._handle_task_failure(task)

                logger.error(
                    f"❌ Task {task.task_id} failed permanently: {e}"
                )

    async def _handle_task_success(self, task: Task):
        """
        Handle successful task completion (circuit breaker logic).

        Args:
            task: Completed task
        """
        if task.agent_name in self.circuit_breakers:
            cb = self.circuit_breakers[task.agent_name]

            if cb.state == CircuitBreakerState.HALF_OPEN:
                cb.success_count += 1

                if cb.success_count >= self.config.circuit_breaker_success_threshold:
                    # Close circuit breaker
                    cb.state = CircuitBreakerState.CLOSED
                    cb.failure_count = 0
                    cb.success_count = 0
                    cb.last_state_change = datetime.now()

                    if task.agent_name in self.agents:
                        self.agents[task.agent_name].circuit_breaker_state = CircuitBreakerState.CLOSED

                    logger.info(f"🟢 Circuit breaker CLOSED for {task.agent_name}")

    async def _handle_task_failure(self, task: Task):
        """
        Handle task failure (circuit breaker logic).

        Args:
            task: Failed task
        """
        if task.agent_name in self.circuit_breakers:
            cb = self.circuit_breakers[task.agent_name]
            cb.failure_count += 1
            cb.last_failure_time = datetime.now()

            if cb.failure_count >= self.config.circuit_breaker_failure_threshold:
                # Open circuit breaker
                await self._open_circuit_breaker(task.agent_name)

    async def _process_events(self):
        """Process pending events from the event bus"""
        # Placeholder - would consume from Kafka/NATS
        # Events like: WhaleDiscovered, ApprovedTrade, AnomalyAlert, etc.
        pass

    def _should_checkpoint(self) -> bool:
        """Check if state checkpoint is needed"""
        last_checkpoint = self.orchestrator_stats.get('last_checkpoint_time')

        if not last_checkpoint:
            return True

        time_since_checkpoint = (datetime.now() - last_checkpoint).total_seconds()
        return time_since_checkpoint >= self.config.checkpoint_interval_seconds

    async def _checkpoint_state(self):
        """Save state snapshot for recovery"""
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'agents': {
                name: {
                    'status': health.status.value,
                    'total_tasks_completed': health.total_tasks_completed,
                    'circuit_breaker_state': health.circuit_breaker_state.value
                }
                for name, health in self.agents.items()
            },
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'orchestrator_stats': self.orchestrator_stats
        }

        self.state_snapshots.append(snapshot)

        # Keep only last 10 snapshots
        if len(self.state_snapshots) > 10:
            self.state_snapshots.pop(0)

        self.orchestrator_stats['last_checkpoint_time'] = datetime.now()

        logger.debug(f"💾 State checkpoint saved | Active tasks: {len(self.active_tasks)}")

    def submit_task(
        self,
        task_type: str,
        agent_name: str,
        payload: Dict,
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: List[str] = None
    ) -> str:
        """
        Submit a task to the orchestrator.

        Args:
            task_type: Type of task (e.g., "process_whale_candidate")
            agent_name: Target agent
            payload: Task data
            priority: Task priority
            dependencies: List of task IDs that must complete first

        Returns:
            Task ID
        """
        self.task_counter += 1
        task_id = f"task_{self.task_counter}_{int(time.time())}"

        task = Task(
            task_id=task_id,
            task_type=task_type,
            agent_name=agent_name,
            priority=priority,
            payload=payload,
            dependencies=dependencies or []
        )

        self.task_queue.append(task)

        logger.debug(
            f"📝 Task submitted | "
            f"ID: {task_id} | "
            f"Type: {task_type} | "
            f"Agent: {agent_name}"
        )

        return task_id

    def _publish_event(self, event_type: str, payload: Dict):
        """Publish event to message bus"""
        event = {
            'event_type': event_type,
            'payload': payload,
            'agent': 'OrchestratorAgent',
            'timestamp': datetime.now().isoformat()
        }

        self.event_bus.append(event)

        # Notify subscribers
        if event_type in self.event_subscribers:
            for callback in self.event_subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in event subscriber: {e}")

    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to an event type"""
        self.event_subscribers[event_type].append(callback)

    def _update_decision_latency(self, latency_ms: float):
        """Update average decision latency"""
        n = self.orchestrator_stats['total_decisions']
        current_avg = self.orchestrator_stats['avg_decision_latency_ms']

        self.orchestrator_stats['total_decisions'] += 1
        self.orchestrator_stats['avg_decision_latency_ms'] = (
            (current_avg * n + latency_ms) / (n + 1)
        )

    def get_orchestrator_stats(self) -> Dict:
        """Get orchestrator statistics"""
        return {
            'total_agents_registered': len(self.agents),
            'healthy_agents': sum(
                1 for h in self.agents.values() if h.status == AgentStatus.HEALTHY
            ),
            'degraded_agents': sum(
                1 for h in self.agents.values() if h.status == AgentStatus.DEGRADED
            ),
            'failed_agents': sum(
                1 for h in self.agents.values() if h.status == AgentStatus.FAILED
            ),
            'open_circuit_breakers': sum(
                1 for cb in self.circuit_breakers.values() if cb.state == CircuitBreakerState.OPEN
            ),
            'active_tasks': len(self.active_tasks),
            'queued_tasks': len(self.task_queue),
            'completed_tasks': len(self.completed_tasks),
            'total_decisions': self.orchestrator_stats['total_decisions'],
            'avg_decision_latency_ms': self.orchestrator_stats['avg_decision_latency_ms'],
            'decision_latency_sla_ms': self.config.decision_latency_sla_ms,
            'sla_compliance_pct': (
                100.0 if self.orchestrator_stats['avg_decision_latency_ms'] <= self.config.decision_latency_sla_ms
                else (self.config.decision_latency_sla_ms / self.orchestrator_stats['avg_decision_latency_ms']) * 100
            ),
            'total_agents_restarted': self.orchestrator_stats['total_agents_restarted'],
            'total_circuit_breakers_opened': self.orchestrator_stats['total_circuit_breakers_opened'],
            'system_uptime_pct': self.orchestrator_stats['system_uptime_pct']
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        # Initialize orchestrator
        orchestrator = OrchestratorAgent()

        # Mock agents
        class MockAgent:
            def __init__(self, name):
                self.name = name

            async def process_example_task(self, payload):
                await asyncio.sleep(0.5)  # Simulate work
                return {"status": "success", "data": payload}

        # Register mock agents
        for agent_name in ["WhaleDiscovery", "RiskManagement", "Execution"]:
            orchestrator.register_agent(agent_name, MockAgent(agent_name))

        # Start orchestration loop
        orchestration_task = asyncio.create_task(orchestrator.orchestration_loop())

        # Submit some tasks
        for i in range(5):
            orchestrator.submit_task(
                task_type="example_task",
                agent_name="WhaleDiscovery",
                payload={"data": f"test_{i}"},
                priority=TaskPriority.HIGH
            )

        # Simulate heartbeats
        async def heartbeat_loop():
            while True:
                for agent_name in orchestrator.agents:
                    orchestrator.receive_heartbeat(agent_name)
                await asyncio.sleep(10)

        heartbeat_task = asyncio.create_task(heartbeat_loop())

        # Run for 30 seconds
        await asyncio.sleep(30)

        # Print stats
        stats = orchestrator.get_orchestrator_stats()
        print(f"\n📊 Orchestrator Stats:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    # Run
    asyncio.run(main())
