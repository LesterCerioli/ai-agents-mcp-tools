import pytest

from app.architecture.agents.system.monolith_design_partner import MonolithDesignPartnerAgent
from app.architecture.schemas.requirements import (
    ArchitectureRequirements,
    BudgetConstraint,
    DomainBoundariesRequirement,
    IntegrationRequirement,
    SpecificationStatus,
    TeamSizeSignal,
)
from app.architecture.schemas.solution import (
    ArchitectureLayer,
    ArchitecturePattern,
    ComponentType,
    DecisionComponent,
    SolutionArchitectureDecision,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)
from app.architecture.schemas.system_design import MonolithLayering


def _agent() -> MonolithDesignPartnerAgent:
    return MonolithDesignPartnerAgent(llm=None)


def _trade_offs() -> TradeOffMatrix:
    return TradeOffMatrix(
        scalability=TradeOffRating.MEDIUM,
        consistency=TradeOffRating.HIGH,
        operational_complexity=TradeOffRating.LOW,
        time_to_market=TradeOffRating.HIGH,
        cost=TradeOffRating.LOW,
    )


def _decision(domain: str) -> SolutionArchitectureDecision:
    return SolutionArchitectureDecision(
        domain=domain,
        patterns=[
            SolutionPattern(pattern=ArchitecturePattern.MONOLITH, rationale="simple", confidence=0.85, is_primary=True, trade_off_matrix=_trade_offs()),
        ],
        components=[
            DecisionComponent(name="API Gateway", type=ComponentType.GATEWAY, layer=ArchitectureLayer.APPLICATION, responsibility="entry"),
            DecisionComponent(name=f"{domain} Service", type=ComponentType.SERVICE, layer=ArchitectureLayer.DOMAIN, responsibility="core"),
            DecisionComponent(name="Primary DB", type=ComponentType.DATABASE, layer=ArchitectureLayer.INFRASTRUCTURE, responsibility="persistence"),
        ],
        decision_confidence=0.85,
    )


def _req(**kwargs) -> ArchitectureRequirements:
    return ArchitectureRequirements(raw_input="test", overall_confidence=0.85, **kwargs)


def test_modular_strategy_when_bounded_contexts_specified():
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

    assert design.layering_strategy == MonolithLayering.MODULAR
    assert len(design.modules) == 3


def test_vertical_slices_when_many_subdomains():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="erp",
            subdomains=["hr", "finance", "inventory", "procurement", "sales"],
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("erp"), req)

    assert design.layering_strategy == MonolithLayering.VERTICAL_SLICES
    assert len(design.modules) == 5


def test_layered_strategy_as_default():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="blog",
            confidence=0.7,
        ),
    )
    design = agent.design(_decision("blog"), req)

    assert design.layering_strategy == MonolithLayering.LAYERED


def test_acl_per_external_system():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="cms",
            confidence=0.8,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "SendGrid"],
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("cms"), req)

    assert len(design.anti_corruption_layers) == 2
    assert any("Stripe" in acl for acl in design.anti_corruption_layers)


def test_shared_kernel_always_present():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="pos",
            confidence=0.8,
        ),
    )
    design = agent.design(_decision("pos"), req)

    assert len(design.shared_kernel) > 0


def test_startup_deployment_strategy_for_small_team():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="saas",
            confidence=0.8,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="small (2-5 engineers)",
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("saas"), req)

    assert "Docker" in design.deployment_strategy or "GitHub Actions" in design.deployment_strategy


def test_kubernetes_deployment_for_large_teams():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="enterprise",
            confidence=0.8,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (50+ engineers)",
            confidence=0.9,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.9,
        ),
    )
    design = agent.design(_decision("enterprise"), req)

    assert "Kubernetes" in design.deployment_strategy


@pytest.mark.asyncio
async def test_run_populates_monolith_design():
    from app.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="clinic",
            bounded_contexts=["patient", "appointment", "billing"],
            confidence=0.9,
        ),
    )
    ctx = PipelineContext()
    ctx.requirements = req
    ctx.decision = _decision("clinic")

    ctx = await agent.run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.monolith_design is not None
    assert ctx.system_design.active_partner == "monolith_design_partner"
