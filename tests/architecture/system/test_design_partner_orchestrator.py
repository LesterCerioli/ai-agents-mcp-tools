import pytest

from src.architecture.agents.system.design_partner_orchestrator import DesignPartnerOrchestrator
from src.architecture.context.pipeline_context import PipelineContext
from src.architecture.schemas.requirements import (
    ArchitectureRequirements,
    DomainBoundariesRequirement,
    SpecificationStatus,
)
from src.architecture.schemas.solution import (
    ArchitectureLayer,
    ArchitecturePattern,
    ComponentType,
    DecisionComponent,
    SolutionArchitectureDecision,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)


def _orchestrator() -> DesignPartnerOrchestrator:
    return DesignPartnerOrchestrator(llm=None, service_mesh_threshold=5)


def _trade_offs() -> TradeOffMatrix:
    return TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.LOW,
        operational_complexity=TradeOffRating.HIGH,
        time_to_market=TradeOffRating.LOW,
        cost=TradeOffRating.HIGH,
    )


def _decision(pattern: ArchitecturePattern, domain: str = "test") -> SolutionArchitectureDecision:
    return SolutionArchitectureDecision(
        domain=domain,
        patterns=[
            SolutionPattern(pattern=pattern, rationale="test", confidence=0.85, is_primary=True, trade_off_matrix=_trade_offs()),
        ],
        components=[
            DecisionComponent(name="API Gateway", type=ComponentType.GATEWAY, layer=ArchitectureLayer.APPLICATION, responsibility="entry"),
            DecisionComponent(name="Core Service", type=ComponentType.SERVICE, layer=ArchitectureLayer.DOMAIN, responsibility="core"),
        ],
        decision_confidence=0.85,
    )


def _req(domain: str = "test", bounded_contexts: list[str] | None = None) -> ArchitectureRequirements:
    return ArchitectureRequirements(
        raw_input="test",
        overall_confidence=0.85,
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain=domain,
            bounded_contexts=bounded_contexts or [],
            confidence=0.9,
        ),
    )


# ── Routing tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_microservices_pattern_routes_to_microservices_partner():
    ctx = PipelineContext()
    ctx.requirements = _req("ecommerce", ["catalog", "order", "payment"])
    ctx.decision = _decision(ArchitecturePattern.MICROSERVICES, "ecommerce")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.microservices_design is not None
    assert ctx.system_design.hexagonal_design is None
    assert ctx.system_design.monolith_design is None
    assert ctx.system_design.active_partner == "microservices_design_partner"


@pytest.mark.asyncio
async def test_event_driven_pattern_routes_to_microservices_partner():
    ctx = PipelineContext()
    ctx.requirements = _req("streaming", ["ingest", "process", "publish"])
    ctx.decision = _decision(ArchitecturePattern.EVENT_DRIVEN, "streaming")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design.microservices_design is not None
    assert ctx.system_design.active_partner == "microservices_design_partner"


@pytest.mark.asyncio
async def test_cqrs_pattern_routes_to_microservices_partner():
    ctx = PipelineContext()
    ctx.requirements = _req("orders")
    ctx.decision = _decision(ArchitecturePattern.CQRS, "orders")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design.microservices_design is not None
    assert ctx.system_design.active_partner == "microservices_design_partner"


@pytest.mark.asyncio
async def test_hexagonal_pattern_routes_to_hexagonal_partner():
    ctx = PipelineContext()
    ctx.requirements = _req("billing", ["invoice", "payment"])
    ctx.decision = _decision(ArchitecturePattern.HEXAGONAL, "billing")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.hexagonal_design is not None
    assert ctx.system_design.microservices_design is None
    assert ctx.system_design.monolith_design is None
    assert ctx.system_design.active_partner == "hexagonal_design_partner"


@pytest.mark.asyncio
async def test_monolith_pattern_routes_to_monolith_partner():
    ctx = PipelineContext()
    ctx.requirements = _req("clinic", ["patient", "appointment"])
    ctx.decision = _decision(ArchitecturePattern.MONOLITH, "clinic")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.monolith_design is not None
    assert ctx.system_design.microservices_design is None
    assert ctx.system_design.hexagonal_design is None
    assert ctx.system_design.active_partner == "monolith_design_partner"


@pytest.mark.asyncio
async def test_layered_pattern_routes_to_monolith_partner():
    ctx = PipelineContext()
    ctx.requirements = _req("internal-tool")
    ctx.decision = _decision(ArchitecturePattern.LAYERED, "internal-tool")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design.monolith_design is not None
    assert ctx.system_design.active_partner == "monolith_design_partner"


@pytest.mark.asyncio
async def test_serverless_pattern_routes_to_monolith_partner():
    ctx = PipelineContext()
    ctx.requirements = _req("automation")
    ctx.decision = _decision(ArchitecturePattern.SERVERLESS, "automation")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design.monolith_design is not None
    assert ctx.system_design.active_partner == "monolith_design_partner"


# ── Guard clauses ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_noop_when_no_decision():
    ctx = PipelineContext()
    ctx.requirements = _req("test")

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design is None


@pytest.mark.asyncio
async def test_noop_when_no_requirements():
    ctx = PipelineContext()
    ctx.decision = _decision(ArchitecturePattern.MICROSERVICES)

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design is None


@pytest.mark.asyncio
async def test_noop_when_no_primary_pattern():
    ctx = PipelineContext()
    ctx.requirements = _req("test")
    ctx.decision = SolutionArchitectureDecision(
        domain="test",
        patterns=[],
        components=[],
        decision_confidence=0.5,
    )

    ctx = await _orchestrator().run(ctx)

    assert ctx.system_design is None
