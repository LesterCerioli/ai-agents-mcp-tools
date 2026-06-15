
import pytest

from app.agents.solid_agent import SOLIDPrinciplesEnforcerAgent
from app.architecture.schemas.solid import (
    ComplianceLevel,
    NormalizedDesignInput,
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

def _agent() -> SOLIDPrinciplesEnforcerAgent:
    return SOLIDPrinciplesEnforcerAgent(llm=None)


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
    protocols: list[str] | None = None,
) -> DecisionComponent:
    return DecisionComponent(
        name=name,
        type=comp_type,
        layer=layer,
        responsibility=responsibility or f"Handles {name.lower()}",
        technology_hints=tech_hints or [],
        protocols=protocols or ["HTTP/REST"],
    )


@pytest.mark.asyncio
async def test_report_always_has_five_principle_results():
    
    decision = _decision(ArchitecturePattern.MICROSERVICES, [
        _comp("APIGateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION),
        _comp("UserService", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Database", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ])
    report = await _agent().analyze(decision)
    principles = {r.principle for r in report.principle_results}
    assert principles == {
        SOLIDPrinciple.SRP,
        SOLIDPrinciple.OCP,
        SOLIDPrinciple.LSP,
        SOLIDPrinciple.ISP,
        SOLIDPrinciple.DIP,
    }


@pytest.mark.asyncio
async def test_report_overall_compliance_reflects_worst_principle():
    
    decision = _decision(ArchitecturePattern.MONOLITH, [
        _comp(
            "GodService",
            ComponentType.SERVICE,
            ArchitectureLayer.DOMAIN,
            responsibility="Handles auth and billing and logging",
            tech_hints=["PostgreSQL"],
        ),
    ])
    report = await _agent().analyze(decision)
    assert report.overall_compliance == ComplianceLevel.VIOLATION


@pytest.mark.asyncio
async def test_report_components_analyzed_is_positive():
    decision = _decision(ArchitecturePattern.MICROSERVICES, [
        _comp("Svc1", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("Svc2", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
        _comp("DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE),
    ])
    report = await _agent().analyze(decision)
    assert report.components_analyzed > 0


@pytest.mark.asyncio
async def test_report_analysis_summary_is_populated():
    decision = _decision(ArchitecturePattern.LAYERED, [
        _comp("AppService", ComponentType.SERVICE, ArchitectureLayer.APPLICATION),
    ])
    report = await _agent().analyze(decision)
    assert report.analysis_summary
    assert len(report.analysis_summary) > 10



@pytest.mark.asyncio
async def test_cross_correlation_srp_isp_cascade():
    
    inp = NormalizedDesignInput(
        pattern="monolith",
        components=[
            {
                "name": "GodModule",
                "type": "service",
                "layer": "domain",
                "responsibility": "Handles billing and notifications and reporting",
                "technology_hints": ["FastAPI", "PostgreSQL", "Redis", "Kafka", "S3"],
                "protocols": ["HTTP/REST"],
            }
        ],
        modules=[
            {
                "name": "GodModule",
                "responsibilities": [
                    "Manages billing",
                    "Sends notifications",
                    "Generates reports",
                    "Manages user preferences",
                    "Handles file uploads",
                ],
                "technology_hints": [],
                "allowed_dependencies": [],
            }
        ],
        service_count=1,
    )
    report = await _agent().analyze(inp)

    srp_result = report.get_result(SOLIDPrinciple.SRP)
    isp_result = report.get_result(SOLIDPrinciple.ISP)
    assert srp_result is not None
    assert srp_result.compliance_level == ComplianceLevel.VIOLATION

    srp_isp_corrs = [
        c for c in report.cross_principle_correlations
        if c.primary_principle == SOLIDPrinciple.SRP
        and SOLIDPrinciple.ISP in c.cascaded_principles
    ]
    assert len(srp_isp_corrs) > 0


@pytest.mark.asyncio
async def test_cross_correlation_ocp_dip_cascade():
    """Missing abstraction (OCP violation) should cascade to DIP violation."""
    inp = NormalizedDesignInput(
        pattern="hexagonal",
        has_ports_and_adapters=False,
        has_repositories=False,
        ports=[],
        service_count=3,
        has_gateway=False,
        components=[
            {
                "name": "OrderService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Processes orders",
                "technology_hints": ["PostgreSQL"],
                "protocols": [],
            },
            {
                "name": "UserService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Manages users",
                "technology_hints": ["Redis"],
                "protocols": [],
            },
            {
                "name": "InventoryService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Tracks inventory",
                "technology_hints": ["MongoDB"],
                "protocols": [],
            },
        ],
    )
    report = await _agent().analyze(inp)

    ocp_result = report.get_result(SOLIDPrinciple.OCP)
    dip_result = report.get_result(SOLIDPrinciple.DIP)
    assert ocp_result is not None and ocp_result.compliance_level == ComplianceLevel.VIOLATION
    assert dip_result is not None and dip_result.compliance_level == ComplianceLevel.VIOLATION

    ocp_dip_corrs = [
        c for c in report.cross_principle_correlations
        if c.primary_principle == SOLIDPrinciple.OCP
        and SOLIDPrinciple.DIP in c.cascaded_principles
    ]
    assert len(ocp_dip_corrs) > 0


@pytest.mark.asyncio
async def test_cross_correlation_dip_lsp_cascade():
    """DIP violation (domain depends on concrete infra) should cascade to LSP."""
    inp = NormalizedDesignInput(
        pattern="layered",
        has_repositories=False,
        has_ports_and_adapters=False,
        components=[
            {
                "name": "Domain–Infrastructure Boundary",
                "type": "service",
                "layer": "domain",
                "responsibility": "Handles business logic",
                "technology_hints": ["PostgreSQL"],
                "protocols": ["HTTP/REST"],
            }
        ],
        ports=[
            {
                "name": "PaymentPort",
                "port_type": "driven",
                "interface_name": "IPayment",
                "adapter_implementations": [],
            }
        ],
    )
    report = await _agent().analyze(inp)

    dip_result = report.get_result(SOLIDPrinciple.DIP)
    lsp_result = report.get_result(SOLIDPrinciple.LSP)
    assert dip_result is not None and dip_result.compliance_level == ComplianceLevel.VIOLATION
    assert lsp_result is not None and lsp_result.compliance_level == ComplianceLevel.VIOLATION

    dip_lsp_corrs = [
        c for c in report.cross_principle_correlations
        if c.primary_principle == SOLIDPrinciple.DIP
        and SOLIDPrinciple.LSP in c.cascaded_principles
    ]
    assert len(dip_lsp_corrs) > 0


@pytest.mark.asyncio
async def test_agent_accepts_normalized_design_input_directly():
    """Agent must accept NormalizedDesignInput directly (union type contract)."""
    inp = NormalizedDesignInput(
        pattern="microservices",
        service_count=2,
        has_gateway=True,
        has_repositories=True,
        has_ports_and_adapters=True,
    )
    report = await _agent().analyze(inp)
    assert len(report.principle_results) == 5


@pytest.mark.asyncio
async def test_agent_accepts_solution_architecture_decision():
    """Agent must accept SolutionArchitectureDecision (union type contract)."""
    decision = _decision(ArchitecturePattern.MONOLITH, [
        _comp("AppModule", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
    ])
    report = await _agent().analyze(decision)
    assert len(report.principle_results) == 5


@pytest.mark.asyncio
async def test_analysis_completes_fast_for_30_components():
    """Analysis must complete within 10 seconds for 30 design components."""
    import time

    components = [
        _comp(
            f"Service{i}",
            ComponentType.SERVICE,
            ArchitectureLayer.DOMAIN,
            tech_hints=["Python"],
        )
        for i in range(30)
    ]
    decision = _decision(ArchitecturePattern.MICROSERVICES, components)
    start = time.monotonic()
    report = await _agent().analyze(decision)
    elapsed = time.monotonic() - start

    assert len(report.principle_results) == 5
    assert elapsed < 10.0, f"Analysis took {elapsed:.2f}s, must be < 10s"


@pytest.mark.asyncio
async def test_each_principle_result_has_required_fields():
    """Every PrincipleResult must have principle, compliance_level, and summary."""
    decision = _decision(ArchitecturePattern.LAYERED, [
        _comp("Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN),
    ])
    report = await _agent().analyze(decision)

    for r in report.principle_results:
        assert r.principle is not None
        assert r.compliance_level is not None
        assert isinstance(r.summary, str)
        assert len(r.summary) > 0


@pytest.mark.asyncio
async def test_violated_principles_have_affected_components():
    """Any VIOLATION-level result must list at least one affected component."""
    decision = _decision(ArchitecturePattern.MONOLITH, [
        _comp(
            "MultiResponsibilityService",
            ComponentType.SERVICE,
            ArchitectureLayer.DOMAIN,
            responsibility="Handles auth and billing and persistence",
            tech_hints=["PostgreSQL", "Redis"],
        ),
    ])
    report = await _agent().analyze(decision)

    for r in report.principle_results:
        if r.compliance_level == ComplianceLevel.VIOLATION:
            assert len(r.affected_components) > 0, (
                f"Principle {r.principle} is VIOLATION but has no affected components"
            )


@pytest.mark.asyncio
async def test_violated_principles_have_recommendations():
    """Any VIOLATION-level result must include at least one recommendation."""
    decision = _decision(ArchitecturePattern.MONOLITH, [
        _comp(
            "PoorService",
            ComponentType.SERVICE,
            ArchitectureLayer.DOMAIN,
            responsibility="Manages everything including auth and billing",
            tech_hints=["PostgreSQL"],
        ),
    ])
    report = await _agent().analyze(decision)

    for r in report.principle_results:
        if r.compliance_level == ComplianceLevel.VIOLATION:
            assert len(r.recommendations) > 0, (
                f"Principle {r.principle} is VIOLATION but has no recommendations"
            )
