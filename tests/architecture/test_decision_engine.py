
import pytest

from src.architecture.agents.decision_engine import SolutionArchitectureDecisionEngine
from src.architecture.schemas.requirements import (
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
from src.architecture.schemas.solution import ArchitecturePattern


@pytest.fixture
def engine() -> SolutionArchitectureDecisionEngine:
    return SolutionArchitectureDecisionEngine(llm=None)


def _req(**kwargs) -> ArchitectureRequirements:
    return ArchitectureRequirements(raw_input="test", overall_confidence=0.8, **kwargs)



@pytest.mark.asyncio
async def test_scenario_1_high_scale_event_driven(engine):
    req = _req(
        scalability=ScalabilityRequirement(status=SpecificationStatus.SPECIFIED, expected_users="5M users", confidence=0.95),
        integration=IntegrationRequirement(status=SpecificationStatus.SPECIFIED, external_systems=["Kafka", "Redis"], real_time=True, confidence=0.9),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="streaming", confidence=0.85),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern == ArchitecturePattern.EVENT_DRIVEN
    assert len(decision.alternative_patterns) >= 2
    assert decision.is_rule_based is True


@pytest.mark.asyncio
async def test_scenario_2_hipaa_small_team(engine):
    req = _req(
        compliance=ComplianceRequirement(status=SpecificationStatus.SPECIFIED, frameworks=["HIPAA"], confidence=0.95),
        team_size=TeamSizeSignal(status=SpecificationStatus.SPECIFIED, engineering_team_size="small (3 engineers)", confidence=0.9),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="telemedicine", confidence=0.85),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern == ArchitecturePattern.MONOLITH
    assert any(r.severity == "high" for r in decision.risk_factors)
    assert decision.is_rule_based is True



@pytest.mark.asyncio
async def test_scenario_3_enterprise_high_availability(engine):
    req = _req(
        availability=AvailabilityRequirement(status=SpecificationStatus.SPECIFIED, target_uptime="99.99%", confidence=0.92),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "Salesforce", "SAP", "Twilio", "SendGrid"],
            confidence=0.88,
        ),
        budget=BudgetConstraint(status=SpecificationStatus.SPECIFIED, tier="enterprise", confidence=0.9),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="e-commerce", confidence=0.85),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern == ArchitecturePattern.MICROSERVICES
    assert decision.is_rule_based is True



@pytest.mark.asyncio
async def test_scenario_4_startup_mvp(engine):
    req = _req(
        budget=BudgetConstraint(status=SpecificationStatus.SPECIFIED, tier="startup", confidence=0.95),
        team_size=TeamSizeSignal(status=SpecificationStatus.SPECIFIED, engineering_team_size="1-5 engineers", confidence=0.9),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="saas", confidence=0.8),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern in {ArchitecturePattern.SERVERLESS, ArchitecturePattern.MONOLITH}
    assert decision.is_rule_based is True



@pytest.mark.asyncio
async def test_scenario_5_fintech_pci_compliance(engine):
    req = _req(
        compliance=ComplianceRequirement(status=SpecificationStatus.SPECIFIED, frameworks=["PCI-DSS", "SOX"], confidence=0.95),
        team_size=TeamSizeSignal(status=SpecificationStatus.SPECIFIED, engineering_team_size="2-5 engineers", confidence=0.88),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="fintech", confidence=0.9),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern == ArchitecturePattern.MONOLITH
    assert len(decision.risk_factors) >= 1
    assert decision.is_rule_based is True



@pytest.mark.asyncio
async def test_scenario_6_data_streaming_platform(engine):
    req = _req(
        scalability=ScalabilityRequirement(status=SpecificationStatus.SPECIFIED, expected_users="2M events/day", confidence=0.9),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Kafka", "Kinesis"],
            integration_patterns=["event streaming", "pubsub"],
            real_time=True,
            confidence=0.95,
        ),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="data-platform", confidence=0.85),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern == ArchitecturePattern.EVENT_DRIVEN
    assert decision.is_rule_based is True



@pytest.mark.asyncio
async def test_scenario_7_high_scale_microservices(engine):
    req = _req(
        scalability=ScalabilityRequirement(status=SpecificationStatus.SPECIFIED, expected_users="500,000 users", confidence=0.88),
        budget=BudgetConstraint(status=SpecificationStatus.SPECIFIED, tier="mid-market", confidence=0.8),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="marketplace", confidence=0.85),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern == ArchitecturePattern.MICROSERVICES
    assert decision.is_rule_based is True



@pytest.mark.asyncio
async def test_scenario_8_moderate_layered(engine):
    req = _req(
        scalability=ScalabilityRequirement(status=SpecificationStatus.SPECIFIED, expected_users="5,000 users", confidence=0.7),
        availability=AvailabilityRequirement(status=SpecificationStatus.SPECIFIED, target_uptime="99.5%", confidence=0.7),
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="internal-tool", confidence=0.8),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert decision.primary_pattern.pattern == ArchitecturePattern.LAYERED
    assert decision.is_rule_based is True



@pytest.mark.asyncio
async def test_decision_always_has_primary_and_two_alternatives(engine):
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(status=SpecificationStatus.SPECIFIED, primary_domain="generic", confidence=0.8),
    )
    decision = await engine.decide(req)
    assert decision.primary_pattern is not None
    assert len(decision.alternative_patterns) >= 2


@pytest.mark.asyncio
async def test_all_patterns_have_trade_off_matrix(engine):
    req = _req(
        scalability=ScalabilityRequirement(status=SpecificationStatus.SPECIFIED, expected_users="1M users", confidence=0.9),
        integration=IntegrationRequirement(status=SpecificationStatus.SPECIFIED, external_systems=["Kafka"], real_time=True, confidence=0.9),
    )
    decision = await engine.decide(req)
    for pattern in decision.patterns:
        assert pattern.trade_off_matrix is not None, f"Pattern {pattern.pattern} missing trade-off matrix"


@pytest.mark.asyncio
async def test_decision_has_architectural_drivers(engine):
    req = _req(
        compliance=ComplianceRequirement(status=SpecificationStatus.SPECIFIED, frameworks=["HIPAA"], confidence=0.95),
        team_size=TeamSizeSignal(status=SpecificationStatus.SPECIFIED, engineering_team_size="small", confidence=0.9),
    )
    decision = await engine.decide(req)
    assert len(decision.architectural_drivers) >= 1
    for driver in decision.architectural_drivers:
        assert 0.0 <= driver.weight <= 1.0


@pytest.mark.asyncio
async def test_decision_has_risk_factors_with_mitigations(engine):
    req = _req(
        availability=AvailabilityRequirement(status=SpecificationStatus.SPECIFIED, target_uptime="99.99%", confidence=0.9),
        integration=IntegrationRequirement(status=SpecificationStatus.SPECIFIED, external_systems=["Stripe", "Salesforce", "SAP", "Twilio", "Mailgun"], confidence=0.88),
        budget=BudgetConstraint(status=SpecificationStatus.SPECIFIED, tier="enterprise", confidence=0.9),
    )
    decision = await engine.decide(req)
    assert len(decision.risk_factors) >= 1
    for risk in decision.risk_factors:
        assert risk.mitigation, f"Risk '{risk.risk}' has no mitigation"
        assert risk.severity in {"low", "medium", "high"}


@pytest.mark.asyncio
async def test_conservative_fallback_when_no_rules_match(engine):
    req = ArchitectureRequirements(raw_input="unclear requirements", overall_confidence=0.2)
    decision = await engine.decide(req)
    assert decision is not None
    assert decision.primary_pattern is not None
