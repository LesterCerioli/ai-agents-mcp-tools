import asyncio

import pytest

from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.lifecycle import (
    VALID_TRANSITIONS,
    AgentState,
    HealthStatus,
    InvalidTransitionError,
)


class LifecycleStubAgent(BaseArchitectureAgent):
    name = "lifecycle_stub"
    capabilities = ["stub_capability"]

    def __init__(self, *, fail_on_init: bool = False):
        super().__init__()
        self.init_calls = 0
        self.shutdown_calls = 0
        self.fail_on_init = fail_on_init

    async def run(self, context: PipelineContext) -> PipelineContext:
        return context

    async def _on_initialize(self) -> None:
        self.init_calls += 1
        if self.fail_on_init:
            raise RuntimeError("boom")

    async def _on_shutdown(self) -> None:
        self.shutdown_calls += 1


def test_valid_transitions_cover_every_state():
    for state in AgentState:
        assert state in VALID_TRANSITIONS


def test_happy_path_lifecycle_chain():
    agent = LifecycleStubAgent()
    assert agent.state == AgentState.UNREGISTERED
    assert agent.agent_id == "lifecycle_stub"

    asyncio.run(agent.initialize())
    assert agent.state == AgentState.READY
    assert agent.init_calls == 1

    agent.activate()
    assert agent.state == AgentState.RUNNING

    agent.pause()
    assert agent.state == AgentState.PAUSED

    agent.resume()
    assert agent.state == AgentState.RUNNING

    asyncio.run(agent.shutdown())
    assert agent.state == AgentState.TERMINATED
    assert agent.shutdown_calls == 1


async def test_double_initialize_is_rejected():
    agent = LifecycleStubAgent()
    await agent.initialize()
    with pytest.raises(InvalidTransitionError):
        await agent.initialize()


async def test_invalid_transitions_raise():
    agent = LifecycleStubAgent()

    with pytest.raises(InvalidTransitionError):
        agent.pause()
    with pytest.raises(InvalidTransitionError):
        agent.activate()

    await agent.initialize()
    with pytest.raises(InvalidTransitionError):
        agent.pause()

    await agent.shutdown()
    with pytest.raises(InvalidTransitionError):
        await agent.shutdown()
    with pytest.raises(InvalidTransitionError):
        await agent.initialize()


async def test_failed_initialization_terminates_agent():
    agent = LifecycleStubAgent(fail_on_init=True)
    with pytest.raises(RuntimeError, match="boom"):
        await agent.initialize()
    assert agent.state == AgentState.TERMINATED


async def test_health_status_reflects_state():
    agent = LifecycleStubAgent()
    assert await agent.health_check() == HealthStatus.UNHEALTHY

    await agent.initialize()
    assert await agent.health_check() == HealthStatus.HEALTHY

    agent.activate()
    agent.pause()
    assert await agent.health_check() == HealthStatus.HEALTHY

    await agent.shutdown()
    assert await agent.health_check() == HealthStatus.UNHEALTHY


def test_terminal_state_accepts_no_transitions():
    assert VALID_TRANSITIONS[AgentState.TERMINATED] == frozenset()
