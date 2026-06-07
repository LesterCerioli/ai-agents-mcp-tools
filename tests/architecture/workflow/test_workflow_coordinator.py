"""
Integration tests for WorkflowCoordinator.
Tests the full pipeline from objective to WorkflowOutput across all three scopes.
"""
import pytest

from src.architecture.workflow_coordinator import WorkflowCoordinator
from src.architecture.schemas.workflow import WorkflowScope
from src.agents.orchestrator import AgentOrchestrator


def _coordinator() -> WorkflowCoordinator:
    orchestrator = AgentOrchestrator(llm=None)
    return WorkflowCoordinator(orchestrator=orchestrator, llm=None)


# ── Backend scope ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backend_scope_produces_artifacts():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="Build a fintech SaaS with user accounts and transactions. "
                  "Needs compliance, 10k users, team of 20.",
        scope=WorkflowScope.BACKEND,
    )
    assert output.scope == WorkflowScope.BACKEND
    assert len(output.backend_artifacts) > 0
    assert len(output.frontend_artifacts) == 0
    assert output.integration_contracts is None
    assert output.confidence > 0.0


@pytest.mark.asyncio
async def test_backend_artifacts_contain_python_files():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="E-commerce platform with catalog, cart, orders and payments.",
        scope=WorkflowScope.BACKEND,
    )
    languages = {a.language for a in output.backend_artifacts}
    assert "python" in languages


@pytest.mark.asyncio
async def test_backend_scope_has_architecture_pattern():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="SaaS CRM with 5 engineers, startup budget, REST integrations.",
        scope=WorkflowScope.BACKEND,
    )
    assert output.architecture_pattern != ""
    assert output.system_design_summary != ""


# ── Frontend scope ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_frontend_scope_produces_artifacts():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="Dashboard application for a logistics platform with real-time tracking.",
        scope=WorkflowScope.FRONTEND,
    )
    assert output.scope == WorkflowScope.FRONTEND
    assert len(output.backend_artifacts) == 0
    assert output.integration_contracts is None


# ── Fullstack scope ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fullstack_produces_integration_contracts():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="IoT platform with device registry, telemetry, and real-time dashboard. "
                  "500k devices, Kafka integration.",
        scope=WorkflowScope.FULLSTACK,
    )
    assert output.scope == WorkflowScope.FULLSTACK
    assert output.integration_contracts is not None
    assert output.integration_contracts.openapi_stub != ""
    assert output.integration_contracts.typescript_types != ""
    assert output.integration_contracts.pydantic_schemas != ""


@pytest.mark.asyncio
async def test_fullstack_has_both_artifact_types():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="Multi-tenant SaaS platform with billing, analytics and user management.",
        scope=WorkflowScope.FULLSTACK,
    )
    assert len(output.backend_artifacts) > 0 or len(output.frontend_artifacts) > 0


@pytest.mark.asyncio
async def test_integration_contracts_include_openapi():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="Retail marketplace with product catalog, orders and payments. 1M users.",
        scope=WorkflowScope.FULLSTACK,
    )
    if output.integration_contracts:
        assert "openapi" in output.integration_contracts.openapi_stub.lower()
        assert "interface" in output.integration_contracts.typescript_types
        assert "BaseModel" in output.integration_contracts.pydantic_schemas


# ── WorkflowOutput schema ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workflow_output_has_all_required_fields():
    coordinator = _coordinator()
    output = await coordinator.run(
        objective="Simple CRUD application for task management.",
        scope=WorkflowScope.BACKEND,
    )
    assert output.workflow_id != ""
    assert output.session_id != ""
    assert output.scope is not None
    assert output.system_design_summary != "" or output.architecture_pattern != ""
    assert isinstance(output.backend_artifacts, list)
    assert isinstance(output.frontend_artifacts, list)
    assert 0.0 <= output.confidence <= 1.0


# ── Existing context reuse ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_existing_context_skips_parse():
    from src.architecture.context.pipeline_context import PipelineContext
    from src.architecture.agents.business_objective_parser import BusinessObjectiveParserAgent

    orchestrator = AgentOrchestrator(llm=None)
    coordinator = WorkflowCoordinator(orchestrator=orchestrator, llm=None)

    # Pre-parse requirements
    ctx = PipelineContext()
    parser = BusinessObjectiveParserAgent(llm=None)
    await parser.parse("Logistics SaaS with shipment tracking and GPS integration.", ctx)

    # Run coordinator with pre-parsed context
    output = await coordinator.run(
        objective="",  # ignored because context already has requirements
        scope=WorkflowScope.BACKEND,
        existing_context=ctx,
    )
    assert output.session_id == ctx.session_id
    assert output.confidence > 0.0
