import pytest

from app.agents.design_pattern_agent import DesignPatternRecommenderAgent
from app.architecture.schemas.design_patterns import PatternCategory, PatternRecommendationReport
from app.architecture.schemas.solid import (
    AffectedComponent,
    ComplianceLevel,
    NormalizedDesignInput,
    PrincipleResult,
    SOLIDComplianceReport,
    SOLIDPrinciple,
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

def _agent() -> DesignPatternRecommenderAgent:
    return DesignPatternRecommenderAgent(llm=None)


def _decision(
    pattern: ArchitecturePattern,
    components: list[DecisionComponent],
    domain: str = "test",
) -> SolutionArchitectureDecision:
    tm = TradeOffMatrix(
        scalability=TradeOffRating.MEDIUM,
        consistency=TradeOffRating.MEDIUM,
        operational_complexity=TradeOffRating.MEDIUM,
        time_to_market=TradeOffRating.MEDIUM,
        cost=TradeOffRating.MEDIUM,
    )
    return SolutionArchitectureDecision(
        domain=domain,
        patterns=[SolutionPattern(
            pattern=pattern,
            rationale="test",
            confidence=0.9,
            trade_off_matrix=tm,
            is_primary=True,
        )],
        components=components,
        rationale="test",
    )


def _comp(
    name: str,
    comp_type: ComponentType,
    layer: ArchitectureLayer,
    responsibility: str = "",
    tech_hints: list[str] | None = None,
) -> DecisionComponent:
    return DecisionComponent(
        name=name,
        type=comp_type,
        layer=layer,
        responsibility=responsibility or f"Handles {name.lower()}",
        technology_hints=tech_hints or [],
        protocols=["HTTP/REST"],
    )


def _solid_report_with_violations(
    violations: list[SOLIDPrinciple],
) -> SOLIDComplianceReport:
    results: list[PrincipleResult] = []
    for principle in SOLIDPrinciple:
        level = (
            ComplianceLevel.VIOLATION if principle in violations else ComplianceLevel.COMPLIANT
        )
        affected = (
            [AffectedComponent(
                component_name="TestComponent",
                violation_description=f"{principle.value.upper()} violated",
            )]
            if principle in violations
            else []
        )
        results.append(PrincipleResult(
            principle=principle,
            compliance_level=level,
            affected_components=affected,
            recommendations=["Fix it"] if principle in violations else [],
            summary=f"{principle.value.upper()} {'violated' if principle in violations else 'ok'}",
        ))

    overall = (
        ComplianceLevel.VIOLATION if violations else ComplianceLevel.COMPLIANT
    )
    return SOLIDComplianceReport(
        principle_results=results,
        overall_compliance=overall,
        components_analyzed=3,
        architecture_pattern="test",
    )


@pytest.mark.asyncio
async def test_report_has_between_3_and_10_recommendations_microservices():
    """Scenario 1: Microservices with DIP+OCP violations — must produce 3–10 recommendations."""
    inp = NormalizedDesignInput(
        pattern="microservices",
        service_count=4,
        has_gateway=True,
        has_repositories=False,
        bounded_contexts=[
            {"name": "OrderContext", "service_name": "order-service", "responsibilities": ["place orders"], "communication_style": "async", "technology_hints": []},
            {"name": "PaymentContext", "service_name": "payment-service", "responsibilities": ["process payments"], "communication_style": "async", "technology_hints": []},
        ],
        components=[
            {"name": "APIGateway", "type": "gateway", "layer": "application", "responsibility": "Routes requests", "technology_hints": ["Kong"], "protocols": ["HTTP"]},
            {"name": "OrderService", "type": "service", "layer": "domain", "responsibility": "Processes orders", "technology_hints": ["PostgreSQL"], "protocols": ["HTTP"]},
        ],
    )
    solid_report = _solid_report_with_violations([SOLIDPrinciple.DIP, SOLIDPrinciple.OCP])
    report = await _agent().recommend(inp, solid_report=solid_report)

    assert isinstance(report, PatternRecommendationReport)
    assert 3 <= len(report.recommendations) <= 10, (
        f"Expected 3–10 recommendations, got {len(report.recommendations)}"
    )


@pytest.mark.asyncio
async def test_every_recommendation_has_required_fields():
    """Scenario 2: Every PatternRecommendation must have all required fields populated."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        has_ports_and_adapters=True,
        ports=[
            {"name": "UserPort", "port_type": "driven", "interface_name": "IUserRepo", "adapter_implementations": []},
        ],
    )
    report = await _agent().recommend(inp, solid_report=None)

    for rec in report.recommendations:
        assert rec.rank >= 1, "rank must be ≥ 1"
        assert rec.pattern_name, "pattern_name must be non-empty"
        assert rec.category in PatternCategory, "category must be a valid PatternCategory"
        assert rec.problem_solved, "problem_solved must be non-empty"
        assert rec.implementation_sketch, "implementation_sketch must be non-empty"
        assert isinstance(rec.solid_principles_reinforced, list), "solid_principles_reinforced must be a list"
        assert len(rec.solid_principles_reinforced) >= 1, (
            f"Pattern '{rec.pattern_name}' must reinforce at least one SOLID principle"
        )


@pytest.mark.asyncio
async def test_recommendations_are_ranked_in_order():
    """Scenario 3: Recommendations must be ranked starting at 1 with no gaps."""
    inp = NormalizedDesignInput(pattern="monolith", has_repositories=False)
    report = await _agent().recommend(inp)

    ranks = [r.rank for r in report.recommendations]
    expected = list(range(1, len(ranks) + 1))
    assert ranks == expected, f"Ranks must be sequential 1-N, got {ranks}"


@pytest.mark.asyncio
async def test_microservices_recommends_different_patterns_than_monolith():
    """Scenario 4: Architecture-style awareness — microservices vs monolith differ."""
    ms_inp = NormalizedDesignInput(
        pattern="microservices",
        service_count=5,
        has_gateway=True,
        components=[
            {"name": f"Svc{i}", "type": "service", "layer": "domain", "responsibility": f"Service {i}", "technology_hints": ["Kafka"], "protocols": ["HTTP"]}
            for i in range(5)
        ],
    )
    mono_inp = NormalizedDesignInput(
        pattern="monolith",
        service_count=1,
        modules=[
            {"name": "AppModule", "responsibilities": ["all business logic"], "technology_hints": [], "allowed_dependencies": []},
        ],
    )
    ms_report = await _agent().recommend(ms_inp)
    mono_report = await _agent().recommend(mono_inp)

    ms_names = {r.pattern_name for r in ms_report.recommendations}
    mono_names = {r.pattern_name for r in mono_report.recommendations}
    
    assert ms_names != mono_names, (
        "Microservices and monolith recommendations should differ"
    )
    
    ms_or_mono_exclusive = ms_names.symmetric_difference(mono_names)
    assert len(ms_or_mono_exclusive) >= 2, (
        "At least 2 patterns should be exclusive to one architecture style"
    )


@pytest.mark.asyncio
async def test_conflict_detector_flags_event_sourcing_and_unit_of_work():
    """Scenario 5 (seeded conflict): Event Sourcing + Unit of Work must be flagged as conflicting."""
    inp = NormalizedDesignInput(
        pattern="microservices",
        service_count=4,
        has_gateway=True,
        has_repositories=False,
        components=[
            {"name": "OrderService", "type": "service", "layer": "domain",
             "responsibility": "Processes orders", "technology_hints": ["Kafka", "PostgreSQL"], "protocols": ["HTTP"]},
            {"name": "PaymentService", "type": "service", "layer": "domain",
             "responsibility": "Handles payments", "technology_hints": ["Kafka"], "protocols": ["HTTP"]},
            {"name": "DB", "type": "database", "layer": "infrastructure",
             "responsibility": "Persistence", "technology_hints": ["PostgreSQL"], "protocols": ["TCP"]},
        ],
        bounded_contexts=[
            {"name": "OrderBC", "service_name": "order-svc", "responsibilities": ["order lifecycle"], "communication_style": "async", "technology_hints": ["Kafka"]},
            {"name": "PaymentBC", "service_name": "payment-svc", "responsibilities": ["payment processing"], "communication_style": "async", "technology_hints": ["Kafka"]},
            {"name": "InventoryBC", "service_name": "inventory-svc", "responsibilities": ["stock management"], "communication_style": "async", "technology_hints": []},
            {"name": "ShippingBC", "service_name": "shipping-svc", "responsibilities": ["delivery"], "communication_style": "async", "technology_hints": []},
        ],
    )
    
    solid_report = _solid_report_with_violations(
        [SOLIDPrinciple.DIP, SOLIDPrinciple.OCP, SOLIDPrinciple.SRP]
    )
    report = await _agent().recommend(inp, solid_report=solid_report)

    
    conflict_pairs = {
        frozenset([c.pattern_a, c.pattern_b]) for c in report.conflicts
    }
    es_uow_conflict = frozenset(["event_sourcing", "unit_of_work"])
    assert es_uow_conflict in conflict_pairs, (
        f"Expected event_sourcing/unit_of_work conflict. Detected conflicts: {conflict_pairs}"
    )


@pytest.mark.asyncio
async def test_conflict_detector_flags_singleton_in_microservices():
    """Scenario 6 (seeded conflict): Singleton in microservices context must be flagged."""
    
    inp = NormalizedDesignInput(
        pattern="microservices",
        service_count=3,
        has_gateway=False,
        has_repositories=False,
        components=[
            {"name": "UserService", "type": "service", "layer": "domain",
             "responsibility": "Manages users", "technology_hints": ["PostgreSQL"], "protocols": ["HTTP"]},
            {"name": "AppConfig", "type": "service", "layer": "application",
             "responsibility": "Shared configuration singleton", "technology_hints": [], "protocols": []},
        ],
        modules=[],
    )
    
    solid_report = _solid_report_with_violations([SOLIDPrinciple.DIP])
    report = await _agent().recommend(inp, solid_report=solid_report)
    
    singleton_recommended = any(
        r.pattern_name == "singleton" for r in report.recommendations
    )
    singleton_conflict = any(
        "singleton" in (c.pattern_a, c.pattern_b) for c in report.conflicts
    )
    
    if singleton_recommended:
        assert singleton_conflict, (
            "Singleton recommended in microservices must trigger a conflict detection"
        )


@pytest.mark.asyncio
async def test_hexagonal_prioritises_repository_and_adapter():
    """Scenario 7: Hexagonal architecture with DIP violation — repository and adapter must rank high."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        has_ports_and_adapters=True,
        has_repositories=False,
        ports=[
            {"name": "OrderRepository", "port_type": "driven", "interface_name": "IOrderRepository", "adapter_implementations": []},
            {"name": "PaymentGateway", "port_type": "driven", "interface_name": "IPaymentGateway", "adapter_implementations": []},
        ],
        domain_services=[
            {"name": "OrderDomainService", "responsibilities": ["place order", "cancel order"], "dependencies": ["IOrderRepository"]},
        ],
    )
    solid_report = _solid_report_with_violations([SOLIDPrinciple.DIP])
    report = await _agent().recommend(inp, solid_report=solid_report)

    pattern_names = [r.pattern_name for r in report.recommendations]
    assert "repository" in pattern_names, "Repository must be recommended for hexagonal+DIP"
    assert "adapter" in pattern_names, "Adapter must be recommended for hexagonal architecture"

    
    repo_rank = next(r.rank for r in report.recommendations if r.pattern_name == "repository")
    adapter_rank = next(r.rank for r in report.recommendations if r.pattern_name == "adapter")
    assert repo_rank <= 5, f"Repository should rank ≤ 5, got rank {repo_rank}"
    assert adapter_rank <= 5, f"Adapter should rank ≤ 5, got rank {adapter_rank}"


@pytest.mark.asyncio
async def test_ocp_violation_drives_strategy_and_decorator():
    """Scenario 8: OCP violation must surface Strategy and/or Decorator in recommendations."""
    inp = NormalizedDesignInput(
        pattern="monolith",
        components=[
            {
                "name": "PaymentProcessor",
                "type": "service",
                "layer": "domain",
                "responsibility": "Processes payments with multiple hardcoded payment methods",
                "technology_hints": [],
                "protocols": ["HTTP"],
            }
        ],
        modules=[
            {
                "name": "PaymentModule",
                "responsibilities": [
                    "stripe payments",
                    "paypal payments",
                    "bank transfer",
                    "crypto payments",
                ],
                "technology_hints": [],
                "allowed_dependencies": [],
            }
        ],
    )
    solid_report = _solid_report_with_violations([SOLIDPrinciple.OCP])
    report = await _agent().recommend(inp, solid_report=solid_report)

    pattern_names = {r.pattern_name for r in report.recommendations}
    ocp_patterns = pattern_names & {"strategy", "decorator", "factory_method", "template_method"}
    assert len(ocp_patterns) >= 1, (
        f"At least one OCP-addressing pattern must be recommended. Got: {pattern_names}"
    )


@pytest.mark.asyncio
async def test_analysis_summary_is_populated():
    """Scenario 9: analysis_summary must be a non-empty informative string."""
    inp = NormalizedDesignInput(pattern="microservices", service_count=3)
    report = await _agent().recommend(inp)
    assert report.analysis_summary
    assert len(report.analysis_summary) > 20


@pytest.mark.asyncio
async def test_report_accepts_solution_architecture_decision():
    """Scenario 10: Agent must accept SolutionArchitectureDecision directly."""
    decision = _decision(ArchitecturePattern.MICROSERVICES, [
        _comp("APIGateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("UserService", ComponentType.SERVICE, ArchitectureLayer.DOMAIN, tech_hints=["PostgreSQL"]),
        _comp("DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE, tech_hints=["PostgreSQL"]),
    ])
    report = await _agent().recommend(decision)
    assert 3 <= len(report.recommendations) <= 10


@pytest.mark.asyncio
async def test_no_duplicate_pattern_names_in_recommendations():
    """Each pattern_name must appear at most once in the final recommendations."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        has_ports_and_adapters=True,
        has_repositories=False,
        service_count=3,
    )
    solid_report = _solid_report_with_violations(
        [SOLIDPrinciple.DIP, SOLIDPrinciple.OCP, SOLIDPrinciple.SRP]
    )
    report = await _agent().recommend(inp, solid_report=solid_report)
    names = [r.pattern_name for r in report.recommendations]
    assert len(names) == len(set(names)), f"Duplicate patterns found: {names}"


@pytest.mark.asyncio
async def test_total_patterns_evaluated_is_positive():
    """total_patterns_evaluated must reflect the total candidates before filtering."""
    inp = NormalizedDesignInput(pattern="microservices", service_count=2)
    report = await _agent().recommend(inp)
    assert report.total_patterns_evaluated > 0


@pytest.mark.asyncio
async def test_fast_completion_for_large_design():
    """Analysis must complete within 10 seconds for a large design artifact."""
    import time

    inp = NormalizedDesignInput(
        pattern="microservices",
        service_count=15,
        has_gateway=True,
        has_repositories=False,
        bounded_contexts=[
            {
                "name": f"Context{i}",
                "service_name": f"service-{i}",
                "responsibilities": [f"Responsibility {i}"],
                "communication_style": "async",
                "technology_hints": ["Kafka"],
            }
            for i in range(15)
        ],
        components=[
            {
                "name": f"Service{i}",
                "type": "service",
                "layer": "domain",
                "responsibility": f"Handles domain {i}",
                "technology_hints": ["PostgreSQL"],
                "protocols": ["HTTP"],
            }
            for i in range(15)
        ],
    )
    solid_report = _solid_report_with_violations(
        [SOLIDPrinciple.DIP, SOLIDPrinciple.OCP]
    )

    start = time.monotonic()
    report = await _agent().recommend(inp, solid_report=solid_report)
    elapsed = time.monotonic() - start

    assert len(report.recommendations) >= 3
    assert elapsed < 10.0, f"Analysis took {elapsed:.2f}s — must complete in < 10s"
