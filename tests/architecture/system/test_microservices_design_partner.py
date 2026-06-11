"""
Integration tests for MicroservicesDesignPartnerAgent.
Covers 5 real-world scenarios: e-commerce, fintech, logistics, SaaS multi-tenant, IoT platform.
"""
import pytest

from app.architecture.agents.system.microservices_design_partner import MicroservicesDesignPartnerAgent
from app.architecture.schemas.requirements import (
    ArchitectureRequirements,
    AvailabilityRequirement,
    BudgetConstraint,
    ComplianceRequirement,
    DomainBoundariesRequirement,
    IntegrationRequirement,
    ScalabilityRequirement,
    SpecificationStatus,
    TeamSizeSignal,
)
from app.architecture.schemas.solution import (
    ArchitecturalDriver,
    ArchitectureLayer,
    ArchitecturePattern,
    ComponentType,
    DecisionComponent,
    RiskFactor,
    SolutionArchitectureDecision,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)
from app.architecture.schemas.system_design import (
    ApiGatewayType,
    CommunicationStyle,
    DataDistributionPattern,
)


def _agent(threshold: int = 5) -> MicroservicesDesignPartnerAgent:
    return MicroservicesDesignPartnerAgent(llm=None, service_mesh_threshold=threshold)


def _trade_offs() -> TradeOffMatrix:
    return TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.LOW,
        operational_complexity=TradeOffRating.HIGH,
        time_to_market=TradeOffRating.LOW,
        cost=TradeOffRating.HIGH,
    )


def _decision(
    domain: str,
    pattern: ArchitecturePattern = ArchitecturePattern.MICROSERVICES,
) -> SolutionArchitectureDecision:
    return SolutionArchitectureDecision(
        domain=domain,
        patterns=[
            SolutionPattern(pattern=pattern, rationale="test", confidence=0.85, is_primary=True, trade_off_matrix=_trade_offs()),
        ],
        components=[
            DecisionComponent(name="API Gateway", type=ComponentType.GATEWAY, layer=ArchitectureLayer.APPLICATION, responsibility="entry point"),
            DecisionComponent(name=f"{domain} Service", type=ComponentType.SERVICE, layer=ArchitectureLayer.DOMAIN, responsibility="core logic"),
        ],
        decision_confidence=0.85,
    )


def _req(**kwargs) -> ArchitectureRequirements:
    return ArchitectureRequirements(raw_input="test", overall_confidence=0.85, **kwargs)


# ── Scenario 1: E-commerce ────────────────────────────────────────────────────

def test_ecommerce_scenario_service_decomposition():
    """E-commerce: 6 bounded contexts → service mesh required, BFF gateway."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="ecommerce",
            bounded_contexts=["catalog", "cart", "order", "payment", "user", "notification"],
            confidence=0.9,
        ),
        availability=AvailabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            target_uptime="99.9%",
            confidence=0.9,
        ),
    )
    decision = _decision("ecommerce")
    design = agent.design(decision, req)

    assert len(design.bounded_contexts) == 6
    assert design.service_mesh.required is True
    assert design.service_mesh.services_count == 6
    assert design.api_gateway.gateway_type == ApiGatewayType.BFF
    assert len(design.service_contracts) == 6
    assert all(bc.database_strategy == DataDistributionPattern.DATABASE_PER_SERVICE for bc in design.bounded_contexts)


def test_ecommerce_scenario_contracts_have_sla():
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="ecommerce",
            bounded_contexts=["catalog", "cart", "order", "payment", "user", "notification"],
            confidence=0.9,
        ),
        availability=AvailabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            target_uptime="99.95%",
            confidence=0.9,
        ),
    )
    decision = _decision("ecommerce")
    design = agent.design(decision, req)

    for contract in design.service_contracts:
        assert contract.sla == "99.95%"
        assert contract.owner_domain != ""
        assert len(contract.protocols) > 0


# ── Scenario 2: Fintech ───────────────────────────────────────────────────────

def test_fintech_scenario_cqrs_data_strategy():
    """Fintech with CQRS alternative pattern → CQRS data strategy, service mesh at threshold."""
    agent = _agent(threshold=5)
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="fintech",
            bounded_contexts=["account", "transaction", "compliance", "auth", "notification"],
            confidence=0.9,
        ),
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED,
            frameworks=["PCI-DSS"],
            confidence=0.95,
        ),
    )
    decision = SolutionArchitectureDecision(
        domain="fintech",
        patterns=[
            SolutionPattern(pattern=ArchitecturePattern.MICROSERVICES, rationale="HA + integrations", confidence=0.9, is_primary=True, trade_off_matrix=_trade_offs()),
            SolutionPattern(pattern=ArchitecturePattern.CQRS, rationale="read/write separation", confidence=0.75, trade_off_matrix=_trade_offs()),
        ],
        components=[
            DecisionComponent(name="API Gateway", type=ComponentType.GATEWAY, layer=ArchitectureLayer.APPLICATION, responsibility="entry"),
        ],
        decision_confidence=0.88,
    )
    design = agent.design(decision, req)

    assert design.data_strategy.pattern == DataDistributionPattern.CQRS
    assert len(design.data_strategy.cqrs_stores) >= 2
    assert design.service_mesh.required is True
    assert design.service_mesh.services_count == 5


def test_fintech_scenario_single_gateway():
    """Fintech domain: not in multi-client list → SINGLE gateway unless many integrations."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="fintech",
            bounded_contexts=["account", "transaction", "compliance", "auth", "notification"],
            confidence=0.9,
        ),
    )
    decision = _decision("fintech")
    design = agent.design(decision, req)

    assert design.api_gateway.gateway_type == ApiGatewayType.SINGLE


# ── Scenario 3: Logistics ─────────────────────────────────────────────────────

def test_logistics_scenario_async_communication():
    """Logistics with real_time=True → async event communication for all services."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="logistics",
            bounded_contexts=["shipment", "tracking", "routing", "fleet", "customer"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            real_time=True,
            external_systems=["GPS Provider", "Carrier API"],
            confidence=0.9,
        ),
    )
    decision = _decision("logistics")
    design = agent.design(decision, req)

    assert all(bc.communication_style == CommunicationStyle.ASYNC_EVENT for bc in design.bounded_contexts)
    assert design.service_mesh.required is True
    assert design.data_strategy.event_bus is not None


def test_logistics_scenario_event_sourcing_with_event_driven_primary():
    """Logistics with EVENT_DRIVEN primary → event sourcing data strategy."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="logistics",
            bounded_contexts=["shipment", "tracking", "routing", "fleet", "customer"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            real_time=True,
            external_systems=["Kafka"],
            confidence=0.9,
        ),
    )
    decision = _decision("logistics", pattern=ArchitecturePattern.EVENT_DRIVEN)
    design = agent.design(decision, req)

    assert design.data_strategy.pattern == DataDistributionPattern.EVENT_SOURCING
    assert design.data_strategy.event_bus == "Apache Kafka"


# ── Scenario 4: SaaS Multi-tenant ────────────────────────────────────────────

def test_saas_scenario_bff_gateway():
    """SaaS domain contains 'saas' keyword → BFF gateway recommended."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="saas",
            bounded_contexts=["tenant", "billing", "product", "analytics", "auth"],
            confidence=0.9,
        ),
    )
    decision = _decision("saas")
    design = agent.design(decision, req)

    assert design.api_gateway.gateway_type == ApiGatewayType.BFF
    assert "web" in design.api_gateway.bff_clients
    assert "mobile" in design.api_gateway.bff_clients


def test_saas_scenario_service_contracts_completeness():
    """Every bounded context must have a corresponding service contract."""
    agent = _agent()
    contexts = ["tenant", "billing", "product", "analytics", "auth"]
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="saas",
            bounded_contexts=contexts,
            confidence=0.9,
        ),
    )
    decision = _decision("saas")
    design = agent.design(decision, req)

    contract_services = {c.service_name for c in design.service_contracts}
    context_services = {bc.service_name for bc in design.bounded_contexts}
    assert contract_services == context_services


# ── Scenario 5: IoT Platform ──────────────────────────────────────────────────

def test_iot_scenario_grpc_for_high_scale():
    """IoT with high user/device scale → gRPC sync communication."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="iot",
            bounded_contexts=["device-registry", "telemetry", "command", "analytics", "alerts"],
            confidence=0.9,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="500k devices",
            confidence=0.9,
        ),
    )
    decision = _decision("iot")
    design = agent.design(decision, req)

    assert all(bc.communication_style == CommunicationStyle.SYNC_GRPC for bc in design.bounded_contexts)


def test_iot_scenario_event_sourcing_via_real_time():
    """IoT with event integration + EVENT_DRIVEN → event sourcing + Kafka event bus."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="iot",
            bounded_contexts=["device-registry", "telemetry", "command", "analytics", "alerts"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            real_time=True,
            external_systems=["MQTT Broker", "InfluxDB", "Kafka"],
            confidence=0.9,
        ),
    )
    decision = _decision("iot", pattern=ArchitecturePattern.EVENT_DRIVEN)
    design = agent.design(decision, req)

    assert design.data_strategy.pattern == DataDistributionPattern.EVENT_SOURCING
    assert design.data_strategy.event_bus == "Apache Kafka"
    assert design.service_mesh.required is True


def test_iot_scenario_federated_gateway_many_integrations():
    """IoT with 6+ external systems → federated gateway."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="iot",
            bounded_contexts=["device-registry", "telemetry", "command", "analytics", "alerts"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["MQTT Broker", "InfluxDB", "Kafka", "Grafana", "AWS IoT", "Azure IoT Hub"],
            confidence=0.9,
        ),
    )
    decision = _decision("iot")
    design = agent.design(decision, req)

    assert design.api_gateway.gateway_type == ApiGatewayType.FEDERATED


# ── Service mesh threshold configurability ────────────────────────────────────

def test_custom_service_mesh_threshold():
    """Service mesh threshold is configurable — 3 services, threshold=3 → required."""
    agent = _agent(threshold=3)
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="core",
            bounded_contexts=["auth", "orders", "payments"],
            confidence=0.9,
        ),
    )
    decision = _decision("core")
    design = agent.design(decision, req)

    assert design.service_mesh.required is True
    assert design.service_mesh.services_count == 3


def test_below_threshold_no_service_mesh():
    """3 services, threshold=5 → service mesh not required."""
    agent = _agent(threshold=5)
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="core",
            bounded_contexts=["auth", "orders", "payments"],
            confidence=0.9,
        ),
    )
    decision = _decision("core")
    design = agent.design(decision, req)

    assert design.service_mesh.required is False
    assert design.service_mesh.mesh_technology == []


# ── Fallback context resolution ───────────────────────────────────────────────

def test_fallback_uses_decision_components():
    """No bounded_contexts/subdomains in requirements → infer from decision components."""
    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="retail",
            confidence=0.7,
        ),
    )
    decision = SolutionArchitectureDecision(
        domain="retail",
        patterns=[
            SolutionPattern(pattern=ArchitecturePattern.MICROSERVICES, rationale="scale", confidence=0.85, is_primary=True, trade_off_matrix=_trade_offs()),
        ],
        components=[
            DecisionComponent(name="Catalog Service", type=ComponentType.SERVICE, layer=ArchitectureLayer.DOMAIN, responsibility="catalog"),
            DecisionComponent(name="Order Service", type=ComponentType.SERVICE, layer=ArchitectureLayer.DOMAIN, responsibility="orders"),
            DecisionComponent(name="API Gateway", type=ComponentType.GATEWAY, layer=ArchitectureLayer.APPLICATION, responsibility="entry"),
        ],
        decision_confidence=0.85,
    )
    design = agent.design(decision, req)

    service_names = [bc.service_name for bc in design.bounded_contexts]
    assert any("catalog" in s.lower() for s in service_names)
    assert any("order" in s.lower() for s in service_names)


# ── run() integrates with PipelineContext ─────────────────────────────────────

@pytest.mark.asyncio
async def test_run_populates_system_design_on_context():
    from app.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="ecommerce",
            bounded_contexts=["catalog", "cart", "order"],
            confidence=0.9,
        ),
    )
    ctx = PipelineContext()
    ctx.requirements = req
    ctx.decision = _decision("ecommerce")

    ctx = await agent.run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.microservices_design is not None
    assert ctx.system_design.active_partner == "microservices_design_partner"


@pytest.mark.asyncio
async def test_run_noop_when_no_decision():
    from app.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    ctx = PipelineContext()
    ctx.requirements = _req()
    result = await agent.run(ctx)
    assert result.system_design is None
