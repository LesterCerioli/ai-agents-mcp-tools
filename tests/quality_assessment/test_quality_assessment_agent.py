"""
Integration tests for ArchitectureQualityAssessmentAgent (issue #17).

Four scenarios:
  - Excellent architecture  → overall health ≥ 80
  - Good architecture       → overall health in [60, 80)
  - Poor architecture       → overall health in [40, 60)
  - Failing architecture    → overall health ≤ 40
"""
import pytest

import app.skills.quality_assessment  # noqa: F401 — registers all 5 quality skills

from app.agents.quality_assessment_agent import ArchitectureQualityAssessmentAgent
from app.architecture.schemas.quality_assessment import (
    QualityAssessmentReport,
    QualityAttribute,
)
from app.architecture.schemas.solid import (
    AffectedComponent,
    ComplianceLevel,
    NormalizedDesignInput,
    PrincipleResult,
    SOLIDComplianceReport,
    SOLIDPrinciple,
)
from app.architecture.schemas.design_patterns import (
    PatternCategory,
    PatternRecommendation,
    PatternRecommendationReport,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _agent() -> ArchitectureQualityAssessmentAgent:
    return ArchitectureQualityAssessmentAgent(llm=None)


def _compliant_report() -> SOLIDComplianceReport:
    """All five SOLID principles fully compliant — no violations, no warnings."""
    return SOLIDComplianceReport(
        principle_results=[
            PrincipleResult(
                principle=p,
                compliance_level=ComplianceLevel.COMPLIANT,
                summary=f"{p.value.upper()} compliant.",
            )
            for p in SOLIDPrinciple
        ],
        overall_compliance=ComplianceLevel.COMPLIANT,
        components_analyzed=5,
    )


def _warning_report(warned: list[SOLIDPrinciple]) -> SOLIDComplianceReport:
    """Some principles at WARNING level."""
    results = []
    for p in SOLIDPrinciple:
        level = ComplianceLevel.WARNING if p in warned else ComplianceLevel.COMPLIANT
        results.append(PrincipleResult(
            principle=p,
            compliance_level=level,
            summary=f"{p.value.upper()} {'warning' if p in warned else 'compliant'}.",
        ))
    return SOLIDComplianceReport(
        principle_results=results,
        overall_compliance=ComplianceLevel.WARNING,
        components_analyzed=5,
    )


def _violation_report(violated: list[SOLIDPrinciple]) -> SOLIDComplianceReport:
    """Some principles at VIOLATION level."""
    results = []
    for p in SOLIDPrinciple:
        if p in violated:
            level = ComplianceLevel.VIOLATION
            affected = [AffectedComponent(
                component_name=f"{p.value.upper()}-ViolatingComponent",
                violation_description=f"Violation of {p.value.upper()}.",
            )]
        else:
            level = ComplianceLevel.COMPLIANT
            affected = []
        results.append(PrincipleResult(
            principle=p,
            compliance_level=level,
            affected_components=affected,
            summary=f"{p.value.upper()} {'violated' if p in violated else 'compliant'}.",
        ))
    return SOLIDComplianceReport(
        principle_results=results,
        overall_compliance=ComplianceLevel.VIOLATION,
        components_analyzed=5,
    )


def _pattern_report_with(*pattern_names: str) -> PatternRecommendationReport:
    recs = [
        PatternRecommendation(
            rank=i + 1,
            pattern_name=name,
            category=PatternCategory.ENTERPRISE,
            problem_solved="supports quality",
            implementation_sketch="...",
            score=5.0,
        )
        for i, name in enumerate(pattern_names)
    ]
    return PatternRecommendationReport(recommendations=recs)


def _excellent_design() -> NormalizedDesignInput:
    """Hexagonal architecture, gateway, repositories, ports-and-adapters, clean domain."""
    return NormalizedDesignInput(
        pattern="hexagonal",
        domain="orders",
        components=[
            {
                "name": "APIGateway",
                "type": "gateway",
                "layer": "presentation",
                "responsibility": "Routes and authenticates all inbound HTTP requests.",
                "technology_hints": ["Kong"],
                "protocols": ["HTTP/REST"],
            },
            {
                "name": "OrderService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Manages order lifecycle.",
                "technology_hints": [],
                "protocols": [],
            },
        ],
        domain_services=[
            {"name": "OrderDomainService", "responsibilities": ["process order"], "dependencies": []},
        ],
        ports=[
            {"name": "OrderRepository", "port_type": "driven", "interface_name": "IOrderRepository", "adapter_implementations": ["PostgresOrderRepository"]},
        ],
        has_gateway=True,
        has_repositories=True,
        has_ports_and_adapters=True,
        has_shared_database=False,
        service_count=2,
    )


def _good_design() -> NormalizedDesignInput:
    """Monolith with gateway but no ports/adapters/repos — warnings reduce score into [60, 80)."""
    return NormalizedDesignInput(
        pattern="monolith",
        domain="users",
        components=[
            {
                "name": "APIGateway",
                "type": "gateway",
                "layer": "presentation",
                "responsibility": "Routes requests.",
                "technology_hints": ["Nginx"],
                "protocols": ["HTTP/REST"],
            },
            {
                "name": "UserService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Manages user accounts.",
                "technology_hints": [],
                "protocols": [],
            },
        ],
        has_gateway=True,
        has_repositories=False,
        has_ports_and_adapters=False,
        has_shared_database=False,
        service_count=1,
    )


def _poor_design() -> NormalizedDesignInput:
    """Monolith without gateway, some layer mixing."""
    return NormalizedDesignInput(
        pattern="monolith",
        domain="billing",
        components=[
            {
                "name": "BillingService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Manages billing and sends emails and updates database.",
                "technology_hints": ["PostgreSQL", "Redis"],
                "protocols": ["HTTP/REST"],
            },
        ],
        modules=[
            {"name": "BillingModule", "responsibilities": ["billing", "emailing", "reporting", "auditing"], "technology_hints": [], "allowed_dependencies": []},
        ],
        has_gateway=False,
        has_repositories=False,
        has_ports_and_adapters=False,
        has_shared_database=True,
        service_count=1,
    )


def _failing_design() -> NormalizedDesignInput:
    """Monolith with maximum violations: shared DB, no gateway, no repos, no ports."""
    return NormalizedDesignInput(
        pattern="monolith",
        domain="legacy",
        components=[
            {
                "name": "GodService",
                "type": "service",
                "layer": "domain",
                "responsibility": "Handles auth, billing, reporting, notifications and also caching.",
                "technology_hints": ["PostgreSQL", "Redis", "Kafka", "S3", "Elasticsearch"],
                "protocols": ["HTTP/REST"],
            },
            {
                "name": "DataAccessLayer",
                "type": "service",
                "layer": "domain",
                "responsibility": "Manages SQL queries and also sends emails and along with caching.",
                "technology_hints": ["MySQL", "MongoDB"],
                "protocols": ["TCP"],
            },
        ],
        modules=[
            {
                "name": "MonolithModule",
                "responsibilities": [
                    "authentication", "billing", "reporting", "notifications",
                    "caching", "file_storage",
                ],
                "technology_hints": [],
                "allowed_dependencies": [],
            }
        ],
        has_gateway=False,
        has_repositories=False,
        has_ports_and_adapters=False,
        has_shared_database=True,
        service_count=1,
    )


# ── Scenarios ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_excellent_architecture_scores_above_80():
    """Compliant hexagonal design with full patterns should score ≥ 80."""
    agent = _agent()
    design = _excellent_design()
    solid = _compliant_report()
    patterns = _pattern_report_with("repository", "strategy", "factory_method", "cqrs")

    report = await agent.assess(design, solid_report=solid, pattern_report=patterns)

    assert isinstance(report, QualityAssessmentReport)
    assert report.overall_health_score >= 80.0, (
        f"Expected excellent score ≥ 80, got {report.overall_health_score}. "
        f"Attributes: {[(s.attribute.value, s.score) for s in report.attribute_scores]}"
    )
    assert report.health_grade == "Excellent"
    assert len(report.attribute_scores) == 5
    assert len(report.layer_quality_breakdown) == 4


@pytest.mark.asyncio
async def test_good_architecture_scores_between_60_and_80():
    """Design with warnings but no violations should score in [60, 80)."""
    agent = _agent()
    design = _good_design()
    solid = _warning_report([SOLIDPrinciple.SRP, SOLIDPrinciple.OCP])
    patterns = _pattern_report_with("repository", "strategy")

    report = await agent.assess(design, solid_report=solid, pattern_report=patterns)

    assert isinstance(report, QualityAssessmentReport)
    assert 60.0 <= report.overall_health_score < 80.0, (
        f"Expected good score in [60, 80), got {report.overall_health_score}. "
        f"Attributes: {[(s.attribute.value, s.score) for s in report.attribute_scores]}"
    )
    assert report.health_grade == "Good"


@pytest.mark.asyncio
async def test_poor_architecture_scores_between_40_and_60():
    """Design with 1-2 violations should score in [40, 60)."""
    agent = _agent()
    design = _poor_design()
    solid = _violation_report([SOLIDPrinciple.SRP, SOLIDPrinciple.OCP])
    patterns = _pattern_report_with("facade")

    report = await agent.assess(design, solid_report=solid, pattern_report=patterns)

    assert isinstance(report, QualityAssessmentReport)
    assert 40.0 <= report.overall_health_score < 60.0, (
        f"Expected poor score in [40, 60), got {report.overall_health_score}. "
        f"Attributes: {[(s.attribute.value, s.score) for s in report.attribute_scores]}"
    )
    assert report.health_grade == "Needs Improvement"


@pytest.mark.asyncio
async def test_failing_architecture_scores_below_40():
    """Design with maximum violations, no structure, should score ≤ 40."""
    agent = _agent()
    design = _failing_design()
    solid = _violation_report(list(SOLIDPrinciple))
    patterns = _pattern_report_with()

    report = await agent.assess(design, solid_report=solid, pattern_report=patterns)

    assert isinstance(report, QualityAssessmentReport)
    assert report.overall_health_score <= 40.0, (
        f"Expected failing score ≤ 40, got {report.overall_health_score}. "
        f"Attributes: {[(s.attribute.value, s.score) for s in report.attribute_scores]}"
    )
    assert report.health_grade == "Critical"


# ── Structural / contract tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_has_all_five_attribute_scores():
    agent = _agent()
    report = await agent.assess(_excellent_design(), solid_report=_compliant_report())

    attributes = {s.attribute for s in report.attribute_scores}
    assert QualityAttribute.MAINTAINABILITY in attributes
    assert QualityAttribute.EXTENSIBILITY in attributes
    assert QualityAttribute.TESTABILITY in attributes
    assert QualityAttribute.SCALABILITY in attributes
    assert QualityAttribute.SECURITY_BOUNDARY_CLARITY in attributes


@pytest.mark.asyncio
async def test_report_has_four_layer_breakdowns():
    agent = _agent()
    report = await agent.assess(_excellent_design(), solid_report=_compliant_report())

    layers = {lq.layer for lq in report.layer_quality_breakdown}
    assert "presentation" in layers
    assert "application" in layers
    assert "domain" in layers
    assert "infrastructure" in layers


@pytest.mark.asyncio
async def test_improvement_actions_max_five():
    agent = _agent()
    report = await agent.assess(_failing_design(), solid_report=_violation_report(list(SOLIDPrinciple)))

    assert len(report.improvement_actions) <= 5
    if report.improvement_actions:
        ranks = [a.rank for a in report.improvement_actions]
        assert ranks == list(range(1, len(ranks) + 1))


@pytest.mark.asyncio
async def test_all_attribute_scores_in_valid_range():
    agent = _agent()
    for design_fn in (_excellent_design, _good_design, _poor_design, _failing_design):
        report = await agent.assess(design_fn())
        for s in report.attribute_scores:
            assert 0.0 <= s.score <= 100.0, (
                f"Score {s.score} out of range for {s.attribute.value}"
            )
        assert 0.0 <= report.overall_health_score <= 100.0


@pytest.mark.asyncio
async def test_report_without_solid_or_pattern_context():
    """Agent must work gracefully when SOLID and pattern reports are absent."""
    agent = _agent()
    design = _good_design()

    report = await agent.assess(design, solid_report=None, pattern_report=None)

    assert isinstance(report, QualityAssessmentReport)
    assert report.overall_health_score > 0
    assert len(report.attribute_scores) == 5


@pytest.mark.asyncio
async def test_report_generation_is_fast(benchmark=None):
    """Report should generate in under 8 seconds (issue acceptance criterion)."""
    import time
    agent = _agent()
    design = _excellent_design()
    solid = _compliant_report()
    patterns = _pattern_report_with("repository", "strategy")

    start = time.monotonic()
    report = await agent.assess(design, solid_report=solid, pattern_report=patterns)
    elapsed = time.monotonic() - start

    assert elapsed < 8.0, f"Report took {elapsed:.2f}s — exceeded 8s limit."
    assert isinstance(report, QualityAssessmentReport)


@pytest.mark.asyncio
async def test_health_grade_thresholds():
    """Validate health grade mapping matches acceptance criteria."""
    from app.architecture.schemas.quality_assessment import _health_grade

    assert _health_grade(80.0) == "Excellent"
    assert _health_grade(95.0) == "Excellent"
    assert _health_grade(60.0) == "Good"
    assert _health_grade(79.9) == "Good"
    assert _health_grade(40.0) == "Needs Improvement"
    assert _health_grade(59.9) == "Needs Improvement"
    assert _health_grade(39.9) == "Critical"
    assert _health_grade(10.0) == "Critical"
