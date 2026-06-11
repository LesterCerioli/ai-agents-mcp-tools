import pytest

from app.architecture.agents.solution_flow_diagram import SolutionFlowDiagramAgent
from app.architecture.agents.validation_agent import SolutionArchitectureValidationAgent
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
    DiagramEdge,
    DiagramNode,
    DiagramView,
    IssueSeverity,
    RiskFactor,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)



def _agent() -> SolutionArchitectureValidationAgent:
    return SolutionArchitectureValidationAgent(llm=None)


def _diagram_agent() -> SolutionFlowDiagramAgent:
    return SolutionFlowDiagramAgent(llm=None)


def _req(**kwargs) -> ArchitectureRequirements:
    return ArchitectureRequirements(raw_input="test", overall_confidence=0.85, **kwargs)


def _trade_off_matrix() -> TradeOffMatrix:
    return TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.MEDIUM,
        operational_complexity=TradeOffRating.MEDIUM,
        time_to_market=TradeOffRating.MEDIUM,
        cost=TradeOffRating.MEDIUM,
    )


def _pattern(p: ArchitecturePattern, primary: bool = False) -> SolutionPattern:
    return SolutionPattern(
        pattern=p,
        rationale=f"Rationale for {p.value}",
        confidence=0.85,
        trade_offs=[],
        trade_off_matrix=_trade_off_matrix(),
        is_primary=primary,
    )


def _decision(
    primary: ArchitecturePattern,
    components: list[DecisionComponent],
    external_integrations: list[str] | None = None,
) -> SolutionArchitectureDecision:
    return SolutionArchitectureDecision(
        domain="test-domain",
        patterns=[_pattern(primary, True), _pattern(ArchitecturePattern.LAYERED)],
        components=components,
        external_integrations=external_integrations or [],
        rationale="Test rationale",
        architectural_drivers=[ArchitecturalDriver(driver="test", weight=0.8, source_dimension="overall")],
        risk_factors=[RiskFactor(risk="test risk", severity="low", mitigation="test")],
        decision_confidence=0.85,
    )


def _comp(
    name: str,
    comp_type: ComponentType,
    layer: ArchitectureLayer,
    protocols: list[str] | None = None,
) -> DecisionComponent:
    return DecisionComponent(
        name=name,
        type=comp_type,
        layer=layer,
        responsibility=f"Responsibility of {name}",
        technology_hints=[],
        protocols=protocols or ["HTTP/REST"],
    )


def _standard_components() -> list[DecisionComponent]:
    return [
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
        _comp("Cache", ComponentType.CACHE, ArchitectureLayer.INFRASTRUCTURE),
    ]


def _microservices_components() -> list[DecisionComponent]:
    return [
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("User Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Order Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]


def _make_diagram(decision: SolutionArchitectureDecision) -> SolutionFlowDiagram:
    return _diagram_agent().generate(decision)


def _diagram_with_cycle(decision: SolutionArchitectureDecision) -> SolutionFlowDiagram:
    
    diagram = _make_diagram(decision)
    nodes = list(diagram.component_view.nodes)
    edges = list(diagram.component_view.edges)
    if len(nodes) >= 2:
        edges.append(DiagramEdge(
            source_id=nodes[-1].id,
            target_id=nodes[0].id,
            label="cycle",
            protocol="HTTP/REST",
        ))
        edges.append(DiagramEdge(
            source_id=nodes[0].id,
            target_id=nodes[-1].id,
            label="cycle-back",
            protocol="HTTP/REST",
        ))
    cyclic_view = DiagramView(
        mermaid=diagram.component_view.mermaid,
        nodes=nodes,
        edges=edges,
    )
    return SolutionFlowDiagram(
        decision_id=diagram.decision_id,
        context_view=diagram.context_view,
        container_view=diagram.container_view,
        component_view=cyclic_view,
        annotations=diagram.annotations,
    )



def test_scenario_1_all_pass():
    
    req = _req(
        scalability=ScalabilityRequirement(status=SpecificationStatus.SPECIFIED, expected_users="50k users", confidence=0.9),
        availability=AvailabilityRequirement(status=SpecificationStatus.SPECIFIED, target_uptime="99.5%", confidence=0.9),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    
    well_formed_components = [
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Notification Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
        _comp("Cache", ComponentType.CACHE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.MICROSERVICES, well_formed_components)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    assert report.passed is True
    assert report.re_evaluation_required is False
    assert not any(g.severity == IssueSeverity.BLOCKER for g in report.gaps)
    assert not any(v.severity == IssueSeverity.BLOCKER for v in report.anti_pattern_violations)
    assert 0.0 < report.confidence_score <= 1.0



def test_scenario_2_warnings_only_missing_integration():
    """External integrations declared in requirements but absent from diagram give warnings."""
    req = _req(
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "Salesforce"],
            confidence=0.9,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    decision = _decision(
        ArchitecturePattern.LAYERED,
        _standard_components(),
        external_integrations=[],  # intentionally empty — won't appear in diagram
    )
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    assert report.passed is True  # warnings are not blockers
    assert report.re_evaluation_required is False
    integration_cov = next(c for c in report.requirement_coverages if c.dimension == "integration")
    assert integration_cov.covered is False
    assert integration_cov.severity == IssueSeverity.WARNING
    assert len(report.gaps) >= 1



def test_scenario_3_blocker_circular_dependency():
    
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    decision = _decision(ArchitecturePattern.LAYERED, _standard_components())
    diagram = _diagram_with_cycle(decision)

    report = _agent().validate(req, diagram, decision)

    assert report.passed is False
    assert report.re_evaluation_required is True
    assert report.re_evaluation_context != ""
    violation_names = [v.pattern_name for v in report.anti_pattern_violations]
    assert "circular_dependency" in violation_names
    blocker_violations = [v for v in report.anti_pattern_violations if v.severity == IssueSeverity.BLOCKER]
    assert len(blocker_violations) >= 1



def test_scenario_4_blocker_missing_security_boundary_compliance():
    
    req = _req(
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED,
            frameworks=["HIPAA"],
            confidence=0.95,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    components_no_gateway = [
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.MONOLITH, components_no_gateway)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    assert report.passed is False
    assert report.re_evaluation_required is True
    compliance_cov = next(c for c in report.requirement_coverages if c.dimension == "compliance")
    assert compliance_cov.covered is False
    assert compliance_cov.severity == IssueSeverity.BLOCKER
    violation_names = [v.pattern_name for v in report.anti_pattern_violations]
    assert "missing_security_boundary" in violation_names



def test_scenario_5_blocker_monolithic_bottleneck_in_microservices():
    
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED, expected_users="1M users", confidence=0.9
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    single_service_components = [
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.MICROSERVICES, single_service_components)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    assert report.passed is False
    assert report.re_evaluation_required is True
    violation_names = [v.pattern_name for v in report.anti_pattern_violations]
    assert "monolithic_bottleneck" in violation_names
    bottleneck = next(v for v in report.anti_pattern_violations if v.pattern_name == "monolithic_bottleneck")
    assert bottleneck.severity == IssueSeverity.BLOCKER



def test_scenario_6_blocker_cqrs_without_database_segregation():
    
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    single_db_components = [
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("Command Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Query Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Single Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.CQRS, single_db_components)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    assert report.passed is False
    assert report.re_evaluation_required is True
    violation_names = [v.pattern_name for v in report.anti_pattern_violations]
    assert "cqrs_without_database_segregation" in violation_names
    violation = next(v for v in report.anti_pattern_violations if v.pattern_name == "cqrs_without_database_segregation")
    assert violation.severity == IssueSeverity.BLOCKER



def test_scenario_7_mixed_blockers_and_warnings():
    
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED, expected_users="5M users", confidence=0.9
        ),
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED, frameworks=["PCI-DSS"], confidence=0.95
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "PayPal"],
            confidence=0.9,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    
    minimal_components = [
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.MICROSERVICES, minimal_components)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    assert report.passed is False
    assert report.re_evaluation_required is True
    severities = {v.severity for v in report.anti_pattern_violations} | {g.severity for g in report.gaps}
    assert IssueSeverity.BLOCKER in severities
    assert len(report.recommended_corrections) >= 2
    assert report.confidence_score < 0.5



def test_anti_pattern_missing_cache_for_high_scale():
    
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED, expected_users="1 million users", confidence=0.9
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    no_cache_components = [
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Order Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.MICROSERVICES, no_cache_components)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    violation_names = [v.pattern_name for v in report.anti_pattern_violations]
    assert "missing_cache_for_high_scale" in violation_names
    cache_v = next(v for v in report.anti_pattern_violations if v.pattern_name == "missing_cache_for_high_scale")
    assert cache_v.severity == IssueSeverity.WARNING



def test_anti_pattern_single_point_of_failure_high_availability():
    
    req = _req(
        availability=AvailabilityRequirement(
            status=SpecificationStatus.SPECIFIED, target_uptime="99.99%", confidence=0.95
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    one_gateway_components = [
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Replica Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.MICROSERVICES, one_gateway_components)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    violation_names = [v.pattern_name for v in report.anti_pattern_violations]
    assert "single_point_of_failure" in violation_names
    spof = next(v for v in report.anti_pattern_violations if v.pattern_name == "single_point_of_failure")
    assert spof.severity == IssueSeverity.WARNING



def test_report_always_has_all_coverage_dimensions():
    
    req = _req(
        scalability=ScalabilityRequirement(status=SpecificationStatus.SPECIFIED, expected_users="10k", confidence=0.8),
        availability=AvailabilityRequirement(status=SpecificationStatus.SPECIFIED, target_uptime="99.9%", confidence=0.8),
        compliance=ComplianceRequirement(status=SpecificationStatus.SPECIFIED, frameworks=["SOC2"], confidence=0.8),
        integration=IntegrationRequirement(status=SpecificationStatus.SPECIFIED, external_systems=["Slack"], confidence=0.8),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="test-domain", confidence=0.8),
    )
    decision = _decision(ArchitecturePattern.LAYERED, _standard_components(), external_integrations=["Slack"])
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    dimensions = {c.dimension for c in report.requirement_coverages}
    assert "scalability" in dimensions
    assert "availability" in dimensions
    assert "compliance" in dimensions
    assert "integration" in dimensions
    assert "domain_boundaries" in dimensions


def test_report_confidence_score_bounded():
    
    req = _req()
    decision = _decision(ArchitecturePattern.LAYERED, _standard_components())
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    assert 0.0 <= report.confidence_score <= 1.0


def test_re_evaluation_context_empty_when_no_blockers():
    
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    decision = _decision(ArchitecturePattern.LAYERED, _standard_components())
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    if not report.re_evaluation_required:
        assert report.re_evaluation_context == ""


def test_all_gaps_have_recommended_corrections():
    
    req = _req(
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED, frameworks=["HIPAA"], confidence=0.95
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Epic", "HL7"],
            confidence=0.9,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="test-domain",
            confidence=0.9,
        ),
    )
    no_gateway_components = [
        _comp("test-domain Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Primary Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ]
    decision = _decision(ArchitecturePattern.MONOLITH, no_gateway_components)
    diagram = _make_diagram(decision)

    report = _agent().validate(req, diagram, decision)

    for gap in report.gaps:
        assert gap.recommended_correction, f"Gap '{gap.description}' has no correction"
    for violation in report.anti_pattern_violations:
        assert violation.recommended_correction, f"Violation '{violation.pattern_name}' has no correction"
