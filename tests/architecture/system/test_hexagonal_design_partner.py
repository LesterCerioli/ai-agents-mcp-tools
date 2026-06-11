import pytest

from src.architecture.agents.system.hexagonal_design_partner import HexagonalDesignPartnerAgent
from src.architecture.schemas.requirements import (
    ArchitectureRequirements,
    ComplianceRequirement,
    DomainBoundariesRequirement,
    IntegrationRequirement,
    SpecificationStatus,
)
from src.architecture.schemas.solution import (
    ArchitectureLayer,
    ArchitecturePattern,
    ComponentType,
    DecisionComponent,
    DiagramEdge,
    DiagramNode,
    DiagramView,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
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
            SolutionPattern(
                pattern=ArchitecturePattern.HEXAGONAL,
                rationale="domain isolation",
                confidence=0.85,
                is_primary=True,
                trade_off_matrix=_trade_offs(),
            ),
        ],
        components=[
            DecisionComponent(
                name="API Gateway",
                type=ComponentType.GATEWAY,
                layer=ArchitectureLayer.APPLICATION,
                responsibility="entry",
            ),
            DecisionComponent(
                name=f"{domain} Service",
                type=ComponentType.SERVICE,
                layer=ArchitectureLayer.DOMAIN,
                responsibility="core",
            ),
        ],
        decision_confidence=0.85,
    )


def _diagram(decision_id: str) -> SolutionFlowDiagram:
    empty_view = DiagramView(mermaid="graph TD", nodes=[], edges=[])
    return SolutionFlowDiagram(
        decision_id=decision_id,
        context_view=empty_view,
        container_view=empty_view,
        component_view=empty_view,
    )


def _req(**kwargs) -> ArchitectureRequirements:
    return ArchitectureRequirements(raw_input="test", overall_confidence=0.85, **kwargs)


def test_driving_ports_include_rest():
    agent = _agent()
    decision = _decision("inventory")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="inventory",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    port_names = [p.name for p in design.driving_ports]
    assert "RestApiPort" in port_names


def test_event_subscriber_port_added_when_real_time():
    agent = _agent()
    decision = _decision("inventory")
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
    design = agent.design(_diagram(decision.decision_id), decision, req)

    port_names = [p.name for p in design.driving_ports]
    assert "EventSubscriberPort" in port_names


def test_driven_ports_include_repository():
    agent = _agent()
    decision = _decision("billing")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="billing",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    port_names = [p.name for p in design.driven_ports]
    assert "RepositoryPort" in port_names


def test_driven_ports_added_for_external_systems():
    agent = _agent()
    decision = _decision("payment")
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
    design = agent.design(_diagram(decision.decision_id), decision, req)

    port_names = [p.name for p in design.driven_ports]
    assert "StripePort" in port_names
    assert "PayPalPort" in port_names


def test_acl_created_per_external_system():
    agent = _agent()
    decision = _decision("payment")
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
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.anti_corruption_layers) == 2
    assert any("Stripe" in acl for acl in design.anti_corruption_layers)
    assert any("PayPal" in acl for acl in design.anti_corruption_layers)


def test_domain_services_from_bounded_contexts():
    agent = _agent()
    decision = _decision("crm")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="crm",
            bounded_contexts=["contact", "opportunity", "pipeline"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.application_core.domain_services) == 3
    service_names = [s.name for s in design.application_core.domain_services]
    assert any("Contact" in n for n in service_names)


def test_all_ports_have_port_type_set():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    for port in design.driving_ports:
        assert port.port_type == PortType.DRIVING
    for port in design.driven_ports:
        assert port.port_type == PortType.DRIVEN


def test_application_core_has_entities_value_objects_and_use_cases():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            bounded_contexts=["cart", "catalog"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    core = design.application_core
    assert len(core.domain_entities) >= 2
    assert len(core.value_objects) >= 1
    assert len(core.use_cases) >= 1


def test_application_core_enriched_by_diagram_domain_nodes():
    agent = _agent()
    decision = _decision("order")
    domain_node = DiagramNode(
        id="order_node",
        label="OrderAggregate",
        type=ComponentType.SERVICE,
        layer=ArchitectureLayer.DOMAIN,
        responsibility="Root aggregate",
    )
    component_view = DiagramView(mermaid="graph TD", nodes=[domain_node], edges=[])
    diagram = SolutionFlowDiagram(
        decision_id=decision.decision_id,
        context_view=DiagramView(mermaid="graph TD", nodes=[], edges=[]),
        container_view=DiagramView(mermaid="graph TD", nodes=[], edges=[]),
        component_view=component_view,
    )
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(diagram, decision, req)

    entity_names = [e.name for e in design.application_core.domain_entities]
    assert "OrderAggregate" in entity_names


def test_application_core_use_cases_derived_from_diagram_application_nodes():
    agent = _agent()
    decision = _decision("order")
    app_node = DiagramNode(
        id="create_order",
        label="CreateOrderUseCase",
        type=ComponentType.SERVICE,
        layer=ArchitectureLayer.APPLICATION,
        responsibility="Creates a new order",
    )
    component_view = DiagramView(mermaid="graph TD", nodes=[app_node], edges=[])
    diagram = SolutionFlowDiagram(
        decision_id=decision.decision_id,
        context_view=DiagramView(mermaid="graph TD", nodes=[], edges=[]),
        container_view=DiagramView(mermaid="graph TD", nodes=[], edges=[]),
        component_view=component_view,
    )
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(diagram, decision, req)

    use_case_names = [uc.name for uc in design.application_core.use_cases]
    assert "CreateOrderUseCase" in use_case_names


def test_application_core_contains_no_infrastructure_concerns():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            bounded_contexts=["cart", "fulfillment"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Inventory", "Shipping"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    infra_keywords = {"sqlalchemy", "fastapi", "kafka", "rabbitmq", "postgresql", "redis"}
    for entity in design.application_core.domain_entities:
        assert not any(kw in entity.name.lower() for kw in infra_keywords)
    for vo in design.application_core.value_objects:
        assert not any(kw in vo.name.lower() for kw in infra_keywords)
    for svc in design.application_core.domain_services:
        assert not any(kw in svc.name.lower() for kw in infra_keywords)



def test_dependency_compliance_map_is_produced():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.dependency_compliance_map is not None
    assert len(design.dependency_compliance_map.rules) >= 4


def test_dependency_compliance_map_is_overall_compliant():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.dependency_compliance_map.overall_compliant is True
    for rule in design.dependency_compliance_map.rules:
        assert rule.compliant is True
        assert rule.violations == []


def test_dependency_rule_domain_layer_has_no_allowed_dependencies():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    domain_rule = next(
        (r for r in design.dependency_compliance_map.rules if r.layer == "domain"), None
    )
    assert domain_rule is not None
    assert domain_rule.allowed_dependencies == []
    assert len(domain_rule.forbidden_dependencies) > 0


def test_testing_strategy_covers_all_three_layers():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    ts = design.testing_strategy
    assert ts.domain_layer is not None
    assert ts.use_case_layer is not None
    assert ts.adapter_layer is not None


def test_domain_layer_testing_requires_no_mocks():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.testing_strategy.domain_layer.mocking_required == []


def test_use_case_layer_testing_mocks_driven_ports():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    mocked = design.testing_strategy.use_case_layer.mocking_required
    assert "RepositoryPort" in mocked


def test_all_layers_have_example_scenarios():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    ts = design.testing_strategy
    assert len(ts.domain_layer.example_scenarios) >= 1
    assert len(ts.use_case_layer.example_scenarios) >= 1
    assert len(ts.adapter_layer.example_scenarios) >= 1


def test_scenario_order_management():
    agent = _agent()
    decision = _decision("order")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="order",
            bounded_contexts=["cart", "catalog", "fulfillment"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Inventory", "Shipping"],
            real_time=True,
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.domain == "order"
    assert len(design.application_core.domain_entities) == 3
    assert len(design.application_core.domain_services) == 3
    assert any("EventSubscriber" in p.name for p in design.driving_ports)
    assert any("EventPublisher" in p.name for p in design.driven_ports)
    assert any("Inventory" in acl for acl in design.anti_corruption_layers)
    assert any("Shipping" in acl for acl in design.anti_corruption_layers)
    assert design.dependency_compliance_map.overall_compliant is True
    assert design.testing_strategy.domain_layer.mocking_required == []


def test_scenario_user_authentication():
    agent = _agent()
    decision = _decision("authentication")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="authentication",
            bounded_contexts=["identity", "session", "permissions"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["OAuth2 Provider", "LDAP"],
            real_time=False,
            confidence=0.9,
        ),
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED,
            frameworks=["SOC2", "GDPR"],
            audit_trail=True,
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.domain == "authentication"
    assert len(design.application_core.domain_entities) == 3
    port_names = [p.name for p in design.driven_ports]
    assert "OAuth2ProviderPort" in port_names
    assert "LDAPPort" in port_names
    assert any("OAuth2" in acl for acl in design.anti_corruption_layers)
    assert design.dependency_compliance_map.overall_compliant is True


def test_scenario_notification_dispatch():
    agent = _agent()
    decision = _decision("notification")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="notification",
            bounded_contexts=["email", "sms", "push"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["SendGrid", "Twilio", "Firebase"],
            real_time=True,
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.domain == "notification"
    assert len(design.application_core.domain_entities) == 3
    port_names = [p.name for p in design.driven_ports]
    assert "SendGridPort" in port_names
    assert "TwilioPort" in port_names
    assert "FirebasePort" in port_names
    assert any("EventPublisher" in p.name for p in design.driven_ports)
    assert any("EventSubscriber" in p.name for p in design.driving_ports)
    assert design.dependency_compliance_map.overall_compliant is True
    assert design.testing_strategy.use_case_layer.mocking_required != []


def test_scenario_payment_processing():
    agent = _agent()
    decision = _decision("payment")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="payment",
            bounded_contexts=["billing", "refund", "reconciliation"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "PayPal"],
            confidence=0.9,
        ),
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED,
            frameworks=["PCI-DSS"],
            audit_trail=True,
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.domain == "payment"
    assert len(design.application_core.domain_entities) == 3
    port_names = [p.name for p in design.driven_ports]
    assert "StripePort" in port_names
    assert "PayPalPort" in port_names
    assert any("Stripe" in acl for acl in design.anti_corruption_layers)
    assert any("PayPal" in acl for acl in design.anti_corruption_layers)
    assert design.dependency_compliance_map.overall_compliant is True
    assert design.testing_strategy.adapter_layer.mocking_required == []


@pytest.mark.asyncio
async def test_run_populates_hexagonal_design():
    from src.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    decision = _decision("billing")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="billing",
            confidence=0.9,
        ),
    )
    ctx = PipelineContext()
    ctx.requirements = req
    ctx.decision = decision
    ctx.diagram = _diagram(decision.decision_id)

    ctx = await agent.run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.hexagonal_design is not None
    assert ctx.system_design.hexagonal_architecture_design is not None
    assert ctx.system_design.active_partner == "hexagonal_design_partner"


@pytest.mark.asyncio
async def test_run_returns_context_unchanged_when_diagram_missing():
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

    assert ctx.system_design is None
