import asyncio
import json

import pytest

from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.lifecycle import (
    AgentState,
    HealthStatus,
    InvalidTransitionError,
)
from app.mcp.registry import (
    AgentRegistry,
    DuplicateAgentError,
    UnknownAgentError,
)


class TrackerAgent(BaseArchitectureAgent):
    name = "tracker"
    capabilities = ["shared_capability"]

    def __init__(
        self,
        agent_id: str = "tracker",
        capabilities: list[str] | None = None,
        tracker: dict | None = None,
        fail: bool = False,
    ):
        super().__init__()
        self.name = agent_id
        if capabilities is not None:
            self.capabilities = capabilities
        self._tracker = tracker
        self._fail = fail

    async def run(self, context: PipelineContext) -> PipelineContext:
        return context

    async def _on_initialize(self) -> None:
        if self._fail:
            raise RuntimeError("init failure")
        if self._tracker is not None:
            self._tracker["active"] += 1
            self._tracker["max_active"] = max(self._tracker["max_active"], self._tracker["active"])
            self._tracker["order"].append(self.name)
            await asyncio.sleep(0.01)
            self._tracker["active"] -= 1


def make_registry(*agents: BaseArchitectureAgent, **kwargs) -> AgentRegistry:
    registry = AgentRegistry(**kwargs)
    for agent in agents:
        registry.register(agent)
    return registry


def test_register_get_and_membership():
    agent = TrackerAgent("a", ["cap_x"])
    registry = make_registry(agent)

    assert registry.get("a") is agent
    assert "a" in registry
    assert registry.agent_ids == ["a"]
    assert len(registry) == 1
    assert registry.states() == {"a": AgentState.UNREGISTERED}


def test_duplicate_registration_raises():
    registry = make_registry(TrackerAgent("a"))
    with pytest.raises(DuplicateAgentError):
        registry.register(TrackerAgent("a"))


def test_unknown_agent_raises_on_get_and_deregister():
    registry = AgentRegistry()
    with pytest.raises(UnknownAgentError):
        registry.get("missing")
    with pytest.raises(UnknownAgentError):
        registry.deregister("missing")


def test_deregister_removes_agent():
    registry = make_registry(TrackerAgent("a"))
    registry.deregister("a")
    assert "a" not in registry


async def test_discovery_requires_operational_state_by_default():
    alpha = TrackerAgent("alpha", ["cap_shared"])
    beta = TrackerAgent("beta", ["cap_shared"])
    gamma = TrackerAgent("gamma", ["cap_other"])
    registry = make_registry(alpha, beta, gamma)

    assert registry.discover("cap_shared") == []
    assert set(registry.discover("cap_shared", only_operational=False)) == {alpha, beta}
    assert registry.discover("cap_missing") == []

    results = await registry.initialize_all()
    assert results == {"alpha": True, "beta": True, "gamma": True}

    discovered = registry.discover("cap_shared")
    assert discovered == sorted([alpha, beta], key=lambda a: a.agent_id)
    assert registry.discover("cap_other") == [gamma]


async def test_initialize_all_runs_non_critical_agents_concurrently():
    tracker = {"active": 0, "max_active": 0, "order": []}
    agents = [TrackerAgent(f"agent_{i}", ["c"], tracker=tracker) for i in range(6)]
    registry = make_registry(*agents)

    results = await registry.initialize_all()
    assert all(results.values())
    assert all(a.state == AgentState.READY for a in agents)
    assert tracker["max_active"] > 1


async def test_critical_path_agents_initialize_first_in_order():
    tracker = {"active": 0, "max_active": 0, "order": []}
    agents = {
        name: TrackerAgent(name, ["c"], tracker=tracker)
        for name in ("first", "second", "worker_1", "worker_2")
    }
    registry = make_registry(*agents.values())

    await registry.initialize_all(critical_path=["second", "first"])

    assert tracker["order"][:2] == ["second", "first"]


async def test_failed_initialization_is_isolated_and_terminates_agent():
    good = TrackerAgent("good", ["c"])
    bad = TrackerAgent("bad", ["c"], fail=True)
    registry = make_registry(good, bad)

    results = await registry.initialize_all()

    assert results == {"good": True, "bad": False}
    assert good.state == AgentState.READY
    assert bad.state == AgentState.TERMINATED


async def test_pause_resume_activate_via_registry():
    agent = TrackerAgent("a")
    registry = make_registry(agent)
    await registry.initialize_all()

    with pytest.raises(InvalidTransitionError):
        await registry.pause("a")

    await registry.activate("a")
    assert agent.state == AgentState.RUNNING
    await registry.pause("a")
    assert agent.state == AgentState.PAUSED
    await registry.resume("a")
    assert agent.state == AgentState.RUNNING


async def test_shutdown_all_only_touches_operational_agents():
    ready = TrackerAgent("ready_agent")
    registry = make_registry(ready)
    await registry.initialize_all()

    fresh = TrackerAgent("fresh_agent")
    registry.register(fresh)

    assert await registry.shutdown_all() == {"ready_agent": True}
    assert ready.state == AgentState.TERMINATED
    assert fresh.state == AgentState.UNREGISTERED
    assert await registry.shutdown_all() == {}


async def test_health_check_all_reports_each_registered_agent():
    healthy = TrackerAgent("healthy")
    failed = TrackerAgent("failed", fail=True)
    registry = make_registry(healthy, failed)

    statuses = await registry.health_check_all()
    assert statuses == {
        "healthy": HealthStatus.UNHEALTHY,
        "failed": HealthStatus.UNHEALTHY,
    }

    await registry.initialize_all()
    statuses = await registry.health_check_all()
    assert statuses["healthy"] == HealthStatus.HEALTHY
    assert statuses["failed"] == HealthStatus.UNHEALTHY


async def test_persistence_snapshot_round_trip_and_recovery(tmp_path):
    path = tmp_path / "registry.json"
    first = make_registry(
        TrackerAgent("keep_a", ["cap_a"]),
        TrackerAgent("keep_b", ["cap_b"]),
        persistence_path=path,
    )
    await first.initialize_all()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["agents"]["keep_a"]["state"] == "ready"
    assert raw["agents"]["keep_b"]["capabilities"] == ["cap_b"]

    second = AgentRegistry(persistence_path=path)
    recovered = TrackerAgent("keep_a", ["cap_a"])
    reinitialized = TrackerAgent("keep_b", ["cap_b"])
    second.register(recovered)
    second.register(reinitialized)

    states = await second.recover()
    assert states["keep_a"] == AgentState.READY
    assert states["keep_b"] == AgentState.READY
    assert second.discover("cap_a") == [recovered]


async def test_recovery_restores_running_and_paused_states(tmp_path):
    path = tmp_path / "registry.json"
    first = make_registry(
        TrackerAgent("runner", ["cap_r"]),
        TrackerAgent("pauser", ["cap_p"]),
        persistence_path=path,
    )
    await first.initialize_all()
    await first.activate("runner")
    await first.activate("pauser")
    await first.pause("pauser")

    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot["agents"]["runner"]["state"] == "running"
    assert snapshot["agents"]["pauser"]["state"] == "paused"

    second = AgentRegistry(persistence_path=path)
    second.register(TrackerAgent("runner", ["cap_r"]))
    second.register(TrackerAgent("pauser", ["cap_p"]))

    states = await second.recover()
    assert states["runner"] == AgentState.RUNNING
    assert states["pauser"] == AgentState.PAUSED


def test_deregister_updates_persisted_snapshot(tmp_path):
    path = tmp_path / "registry.json"
    registry = make_registry(TrackerAgent("gone"), persistence_path=path)
    registry.deregister("gone")

    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert "gone" not in snapshot["agents"]


def test_corrupt_snapshot_does_not_crash(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text("{not json", encoding="utf-8")

    registry = AgentRegistry(persistence_path=path)
    registry.register(TrackerAgent("a"))
    assert "a" in registry
