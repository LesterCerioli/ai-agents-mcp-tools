"""Lifecycle primitives shared by architecture agents and the MCP agent registry.

This module is intentionally dependency-free so it can be imported from both
``app.architecture.agents.base`` and ``app.mcp.registry`` without creating
circular imports.
"""

from __future__ import annotations

from enum import StrEnum


class AgentState(StrEnum):
    """Lifecycle states of a registered architecture agent."""

    UNREGISTERED = "unregistered"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


class HealthStatus(StrEnum):
    """Result of an agent health check."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


OPERATIONAL_STATES: frozenset[AgentState] = frozenset(
    {AgentState.READY, AgentState.RUNNING, AgentState.PAUSED}
)

STABLE_STATES: frozenset[AgentState] = OPERATIONAL_STATES

VALID_TRANSITIONS: dict[AgentState, frozenset[AgentState]] = {
    AgentState.UNREGISTERED: frozenset({AgentState.INITIALIZING}),
    AgentState.INITIALIZING: frozenset({AgentState.READY, AgentState.SHUTTING_DOWN}),
    AgentState.READY: frozenset({AgentState.RUNNING, AgentState.SHUTTING_DOWN}),
    AgentState.RUNNING: frozenset({AgentState.PAUSED, AgentState.READY, AgentState.SHUTTING_DOWN}),
    AgentState.PAUSED: frozenset({AgentState.RUNNING, AgentState.SHUTTING_DOWN}),
    AgentState.SHUTTING_DOWN: frozenset({AgentState.TERMINATED}),
    AgentState.TERMINATED: frozenset(),
}


class InvalidTransitionError(RuntimeError):
    """Raised when a lifecycle transition violates the state machine guards."""

    def __init__(self, current: AgentState, target: AgentState) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid lifecycle transition: {current.value} -> {target.value}. "
            f"Allowed targets from '{current.value}': "
            f"{sorted(s.value for s in VALID_TRANSITIONS[current])}"
        )


def can_transition(current: AgentState, target: AgentState) -> bool:
    return target in VALID_TRANSITIONS[current]


def assert_transition(current: AgentState, target: AgentState) -> None:
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)
