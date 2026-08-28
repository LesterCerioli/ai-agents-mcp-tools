"""Integration tests: all architecture agents from Tasks 1-3 through the MCP registry."""

import pytest

from app.architecture.lifecycle import (
    AgentState,
    HealthStatus,
    InvalidTransitionError,
)
from app.mcp.bootstrap import create_architecture_registry, default_architecture_agents
from app.mcp.registry import AgentRegistry

EXPECTED_AGENT_IDS = {
    "business_objective_parser",
    "solution_architecture_decision_engine",
    "solution_flow_diagram",
    "solution_architecture_validation",
    "microservices_design_partner",
    "hexagonal_design_partner",
    "monolith_design_partner",
    "monolith_architecture_design_partner",
    "design_partner_orchestrator",
}

EXPECTED_CAPABILITIES = {
    "solution_parsing": {"business_objective_parser"},
    "requirements_extraction": {"business_objective_parser"},
    "solution_design": {"solution_architecture_decision_engine"},
    "pattern_selection": {"solution_architecture_decision_engine"},
    "flow_diagram_generation": {"solution_flow_diagram"},
    "solution_validation": {"solution_architecture_validation"},
    "system_design": {"design_partner_orchestrator"},
    "microservices_design": {"microservices_design_partner", "design_partner_orchestrator"},
    "monolith_design": {
        "monolith_design_partner",
        "monolith_architecture_design_partner",
        "design_partner_orchestrator",
    },
    "monolith_architecture_design": {"monolith_architecture_design_partner"},
    "hexagonal_design": {"hexagonal_design_partner", "design_partner_orchestrator"},
}


def build_registered_registry() -> AgentRegistry:
    registry = AgentRegistry()
    for agent in default_architecture_agents():
        registry.register(agent)
    return registry


async def test_all_task_1_3_agents_register_and_reach_ready_state():
    registry = build_registered_registry()

    assert set(registry.agent_ids) == EXPECTED_AGENT_IDS
    results = await registry.initialize_all()
    assert all(results.values()), results
    assert all(state == AgentState.READY for state in registry.states().values())


async def test_discovery_returns_correct_agents_for_every_capability():
    registry = build_registered_registry()
    await registry.initialize_all()

    declared = {cap for aid in EXPECTED_AGENT_IDS for cap in registry.get(aid).capabilities}
    assert declared == set(EXPECTED_CAPABILITIES)

    for capability, expected_ids in EXPECTED_CAPABILITIES.items():
        discovered = {agent.agent_id for agent in registry.discover(capability)}
        assert discovered == expected_ids, f"capability '{capability}' mismatch"


async def test_lifecycle_transitions_are_enforced_via_registry():
    registry = build_registered_registry()
    await registry.initialize_all()

    parser_id = "business_objective_parser"
    with pytest.raises(InvalidTransitionError):
        await registry.pause(parser_id)

    await registry.activate(parser_id)
    assert registry.get(parser_id).state == AgentState.RUNNING
    await registry.pause(parser_id)
    assert registry.get(parser_id).state == AgentState.PAUSED


async def test_health_checks_report_healthy_after_initialization():
    registry = build_registered_registry()
    statuses_before = await registry.health_check_all()
    assert all(s == HealthStatus.UNHEALTHY for s in statuses_before.values())

    await registry.initialize_all()
    statuses = await registry.health_check_all()
    assert all(s == HealthStatus.HEALTHY for s in statuses.values()), statuses


async def test_registry_recovers_state_after_simulated_restart(tmp_path):
    path = tmp_path / "mcp_registry.json"

    first = create_architecture_registry(persistence_path=str(path))
    await first.initialize_all()
    original_capabilities = {aid: list(first.get(aid).capabilities) for aid in first.agent_ids}

    second = AgentRegistry(persistence_path=path)
    for agent in default_architecture_agents():
        second.register(agent)
    assert set(second.agent_ids) == set(first.agent_ids)
    assert all(second.states()[aid] == AgentState.UNREGISTERED for aid in second.agent_ids)

    states = await second.recover()

    assert set(states) == EXPECTED_AGENT_IDS
    assert all(state == AgentState.READY for state in states.values())
    assert {
        aid: list(second.get(aid).capabilities) for aid in second.agent_ids
    } == original_capabilities
    assert {agent.agent_id for agent in second.discover("solution_parsing")} == {
        "business_objective_parser"
    }


async def test_bootstrap_factory_registers_everything_operational():
    registry = create_architecture_registry()
    assert set(registry.agent_ids) == EXPECTED_AGENT_IDS
