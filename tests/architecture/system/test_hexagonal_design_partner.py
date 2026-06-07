import pytest

from src.architecture.agents.system.hexagonal_design_partner import HexagonalDesignPartnerAgent
from src.architecture.schemas.requirements import (
    ArchitectureRequirements,
    DomainBoundariesRequirement,
    IntegrationRequirement,
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
from src.architecture.schemas.system_design import PortType


def _agent() -> HexagonalDesignPartnerAgent:
    return HexagonalDesignPartnerAgent(llm=None)


def _trade_offs() -> TradeOffMatrix:
    return TradeOffMatrix(
        scalability=TradeOffRating.MEDIUM,
        consistency=TradeOffRating.HIGH,
        operational_complexity=TradeOffRating.MEDIUM,
        time_to_market=TradeOffRating.MEDIUM,
        cost=TradeOffRating.MEDIUM,
    )


def _decision(domain: str) -> SolutionArchitectureDecision:
    return SolutionArchitectureDecision(
        domain=domain,
        patterns=[
            SolutionPattern(pattern=ArchitecturePattern.HEXAGONAL, rationale="domain isolation", confidence=0.85, is_primary=True, trade_off_matrix=_trade_offs()),
        ],
        components=[
            DecisionComponent(name="API Gateway", type=ComponentType.GATEWAY, layer=ArchitectureLayer.APPLICATION, responsibility="entry"),
            DecisionComponent(name=f"{domain} Service", type=ComponentType.SERVICE, layer=ArchitectureLayer.DOMAIN, responsibility="core"),
        ],
        decision_confidence=0.85,
    )


def _req(**kwargs) -> ArchitectureRequirements:
    return ArchitectureRequirements(raw_input="test", overall_confidence=0.85, **kwargs)


def test_driving_ports_include_rest():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="inventory",
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("inventory"), req)

    port_names = [p.name for p in design.driving_ports]
    assert "RestApiPort" in port_names


def test_event_subscriber_port_added_when_real_time():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="inventory",
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            real_time=True,
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("inventory"), req)

    port_names = [p.name for p in design.driving_ports]
    assert "EventSubscriberPort" in port_names


def test_driven_ports_include_repository():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="billing",
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("billing"), req)

    port_names = [p.name for p in design.driven_ports]
    assert "RepositoryPort" in port_names


def test_driven_ports_added_for_external_systems():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="payment",
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "PayPal"],
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("payment"), req)

    port_names = [p.name for p in design.driven_ports]
    assert "StripePort" in port_names
    assert "PayPalPort" in port_names


def test_acl_created_per_external_system():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="payment",
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "PayPal"],
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("payment"), req)

    assert len(design.anti_corruption_layers) == 2
    assert any("Stripe" in acl for acl in design.anti_corruption_layers)
    assert any("PayPal" in acl for acl in design.anti_corruption_layers)


def test_domain_services_from_bounded_contexts():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="crm",
            bounded_contexts=["contact", "opportunity", "pipeline"],
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("crm"), req)

    assert len(design.domain_services) == 3
    service_names = [s.name for s in design.domain_services]
    assert any("Contact" in n for n in service_names)


def test_all_ports_have_port_type_set():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("order"), req)

    for port in design.driving_ports:
        assert port.port_type == PortType.DRIVING
    for port in design.driven_ports:
        assert port.port_type == PortType.DRIVEN


@pytest.mark.asyncio
async def test_run_populates_hexagonal_design():
    from src.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="billing",
            confidence=0.9,
        ),
    )
    ctx = PipelineContext()
    ctx.requirements = req
    ctx.decision = _decision("billing")

    ctx = await agent.run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.hexagonal_design is not None
    assert ctx.system_design.active_partner == "hexagonal_design_partner"
