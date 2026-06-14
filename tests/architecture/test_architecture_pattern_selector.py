"""Unit tests for ArchitecturePatternSelector.

Coverage:
- 10 distinct requirement profiles (acceptance criterion)
- Hybrid activation triggered for profiles 3 and 9 (>= 2 required)
- Deterministic scoring matrix
- Always selects at least one design partner
- Rationale includes per-pattern scores and rejection reasons for non-selected partners
"""

import pytest

from app.architecture.agents.architecture_pattern_selector import ArchitecturePatternSelector
from app.architecture.schemas.design_partner_plan import DesignPartnerPlan
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
    ArchitectureLayer,
    ArchitecturePattern,
    ComponentType,
    DecisionComponent,
    SolutionArchitectureDecision,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _selector() -> ArchitecturePatternSelector:
    return ArchitecturePatternSelector()


def _trade_off_matrix() -> TradeOffMatrix:
    return TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.MEDIUM,
        operational_complexity=TradeOffRating.MEDIUM,
        time_to_market=TradeOffRating.MEDIUM,
        cost=TradeOffRating.MEDIUM,
    )


def _decision(pattern: ArchitecturePattern, domain: str = "test") -> SolutionArchitectureDecision:
    return SolutionArchitectureDecision(
        domain=domain,
        patterns=[
            SolutionPattern(
                pattern=pattern,
                rationale="test decision",
                confidence=0.85,
                is_primary=True,
                trade_off_matrix=_trade_off_matrix(),
            ),
        ],
        components=[
            DecisionComponent(
                name="API Gateway",
                type=ComponentType.GATEWAY,
                layer=ArchitectureLayer.APPLICATION,
                responsibility="entry",
            ),
        ],
        decision_confidence=0.85,
    )


def _req(**kwargs) -> ArchitectureRequirements:
    return ArchitectureRequirements(raw_input="test", overall_confidence=0.8, **kwargs)


# ---------------------------------------------------------------------------
# Profile 1 — High-scale event streaming (5M users, Kafka, large team, enterprise)
# Expected: microservices_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_1_high_scale_streaming_selects_microservices():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="5M users",
            confidence=0.95,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Kafka", "Redis"],
            real_time=True,
            confidence=0.90,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (80 engineers)",
            confidence=0.85,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="streaming",
            bounded_contexts=[],
            confidence=0.80,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.EVENT_DRIVEN, "streaming"), req)

    assert isinstance(plan, DesignPartnerPlan)
    assert len(plan.selected_partners) >= 1
    assert plan.selected_partners[0].partner_name == "microservices_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Profile 2 — HIPAA + small team
# Expected: monolith_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_2_hipaa_small_team_selects_monolith():
    req = _req(
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED,
            frameworks=["HIPAA"],
            confidence=0.95,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="small (3 engineers)",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="telemedicine",
            bounded_contexts=[],
            confidence=0.85,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MONOLITH, "telemedicine"), req)

    assert plan.selected_partners[0].partner_name == "monolith_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Profile 3 — Enterprise complex DDD (500K users, 8 bounded contexts, large team)
# Expected: microservices + hexagonal, HYBRID
# ---------------------------------------------------------------------------

def test_profile_3_enterprise_complex_ddd_activates_hybrid():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="500,000 users",
            confidence=0.88,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (60 engineers)",
            organizational_maturity="experienced senior engineers",
            confidence=0.85,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="e-commerce",
            bounded_contexts=[
                "catalog", "inventory", "order", "payment",
                "shipment", "customer", "notification", "analytics",
            ],
            confidence=0.90,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MICROSERVICES, "e-commerce"), req)

    assert plan.is_hybrid is True
    partner_names = {a.partner_name for a in plan.selected_partners}
    assert "microservices_design_partner" in partner_names
    assert "hexagonal_design_partner" in partner_names
    assert len(plan.selected_partners) == 2
    assert plan.rationale.hybrid_reason is not None


# ---------------------------------------------------------------------------
# Profile 4 — Startup MVP (startup budget, 1-5 engineers, low scale)
# Expected: monolith_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_4_startup_mvp_selects_monolith():
    req = _req(
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="startup",
            confidence=0.95,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="1-5 engineers",
            confidence=0.90,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="2,000 users",
            confidence=0.70,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="saas",
            bounded_contexts=[],
            confidence=0.80,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MONOLITH, "saas"), req)

    assert plan.selected_partners[0].partner_name == "monolith_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Profile 5 — HA enterprise with multiple integrations
# Expected: microservices_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_5_ha_enterprise_selects_microservices():
    req = _req(
        availability=AvailabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            target_uptime="99.99%",
            confidence=0.92,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "Salesforce", "SAP", "Twilio", "SendGrid"],
            confidence=0.88,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.90,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="20+ engineers",
            confidence=0.85,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="e-commerce",
            bounded_contexts=["order", "payment", "catalog", "customer"],
            confidence=0.85,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MICROSERVICES, "e-commerce"), req)

    assert plan.selected_partners[0].partner_name == "microservices_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Profile 6 — DDD-first with hexagonal (explicit hexagonal decision, high domain complexity)
# Expected: hexagonal_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_6_ddd_hexagonal_selects_hexagonal():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="50,000 users",
            confidence=0.75,
        ),
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED,
            frameworks=["HIPAA"],
            confidence=0.90,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="10-20 engineers",
            confidence=0.80,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="healthcare",
            bounded_contexts=[
                "patient", "appointment", "prescription",
                "billing", "lab-results", "notification",
                "audit", "consent",
            ],
            confidence=0.90,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.HEXAGONAL, "healthcare"), req)

    assert plan.selected_partners[0].partner_name == "hexagonal_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Profile 7 — Real-time data platform (2M events/day, Kafka, large team)
# Expected: microservices_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_7_real_time_data_platform_selects_microservices():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="2M events/day",
            confidence=0.90,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Kafka", "Kinesis"],
            integration_patterns=["event streaming", "pubsub"],
            real_time=True,
            confidence=0.95,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (40 engineers)",
            organizational_maturity="experienced",
            confidence=0.85,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="data-platform",
            bounded_contexts=[],
            confidence=0.85,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.EVENT_DRIVEN, "data-platform"), req)

    assert plan.selected_partners[0].partner_name == "microservices_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Profile 8 — Simple internal CRUD tool (5K users, small team, minimal domain)
# Expected: monolith_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_8_simple_internal_tool_selects_monolith():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="5,000 users",
            confidence=0.70,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="small (4 engineers)",
            confidence=0.85,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="internal-tool",
            bounded_contexts=[],
            confidence=0.80,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.LAYERED, "internal-tool"), req)

    assert plan.selected_partners[0].partner_name == "monolith_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Profile 9 — Fintech DDD platform (1M users, many bounded contexts, large mature team)
# Expected: microservices + hexagonal, HYBRID
# ---------------------------------------------------------------------------

def test_profile_9_fintech_ddd_activates_hybrid():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="1M users",
            confidence=0.90,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (50+ engineers)",
            organizational_maturity="mature senior engineers",
            confidence=0.88,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="fintech",
            bounded_contexts=[
                "accounts", "transactions", "fraud-detection",
                "compliance", "reporting", "notifications",
                "identity", "audit",
            ],
            confidence=0.90,
        ),
        compliance=ComplianceRequirement(
            status=SpecificationStatus.SPECIFIED,
            frameworks=["PCI-DSS", "SOX"],
            confidence=0.92,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MICROSERVICES, "fintech"), req)

    assert plan.is_hybrid is True
    partner_names = {a.partner_name for a in plan.selected_partners}
    assert "microservices_design_partner" in partner_names
    assert "hexagonal_design_partner" in partner_names
    assert len(plan.selected_partners) == 2
    assert plan.rationale.hybrid_reason is not None


# ---------------------------------------------------------------------------
# Profile 10 — Mid-size SaaS (50K users, 6 bounded contexts, medium team, growth stage)
# Expected: hexagonal_design_partner, NOT hybrid
# ---------------------------------------------------------------------------

def test_profile_10_midsized_saas_selects_hexagonal():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="50,000 users",
            confidence=0.80,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="10-20 engineers",
            confidence=0.80,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="growth",
            confidence=0.80,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="project-management",
            bounded_contexts=[
                "projects", "tasks", "teams",
                "billing", "notifications", "reporting",
            ],
            confidence=0.85,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.HEXAGONAL, "project-management"), req)

    assert plan.selected_partners[0].partner_name == "hexagonal_design_partner"
    assert plan.is_hybrid is False


# ---------------------------------------------------------------------------
# Acceptance criteria — always selects at least one partner
# ---------------------------------------------------------------------------

def test_always_selects_at_least_one_partner():
    """Selector must produce a plan with >= 1 partner for any valid input."""
    minimal_req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="generic",
            confidence=0.5,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MONOLITH), minimal_req)
    assert len(plan.selected_partners) >= 1


# ---------------------------------------------------------------------------
# Acceptance criteria — deterministic scoring matrix
# ---------------------------------------------------------------------------

def test_scoring_matrix_is_deterministic():
    """Identical inputs must always produce identical scores."""
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="500,000 users",
            confidence=0.88,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (60 engineers)",
            confidence=0.85,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="e-commerce",
            bounded_contexts=[
                "catalog", "inventory", "order", "payment",
                "shipment", "customer", "notification", "analytics",
            ],
            confidence=0.90,
        ),
    )
    decision = _decision(ArchitecturePattern.MICROSERVICES)
    selector = _selector()

    plan_a = selector.select(decision, req)
    plan_b = selector.select(decision, req)

    assert plan_a.scoring_deterministic is True
    assert plan_b.scoring_deterministic is True

    scores_a = {
        s.partner_name: s.fitness_score
        for s in plan_a.rationale.per_partner_scores
    }
    scores_b = {
        s.partner_name: s.fitness_score
        for s in plan_b.rationale.per_partner_scores
    }
    assert scores_a == scores_b
    assert plan_a.is_hybrid == plan_b.is_hybrid


# ---------------------------------------------------------------------------
# Acceptance criteria — rationale includes per-pattern scores & rejection reasons
# ---------------------------------------------------------------------------

def test_rationale_includes_per_pattern_scores_and_rejection_reasons():
    """Every plan must score all partners and provide rejection reasons for non-selected ones."""
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="1M users",
            confidence=0.90,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (50+ engineers)",
            confidence=0.85,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="marketplace",
            bounded_contexts=["catalog", "order", "payment", "shipping"],
            confidence=0.85,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MICROSERVICES, "marketplace"), req)

    # All three partners must be scored
    scored_partners = {s.partner_name for s in plan.rationale.per_partner_scores}
    assert scored_partners == {
        "microservices_design_partner",
        "hexagonal_design_partner",
        "monolith_design_partner",
    }

    # Non-selected partners must have a rejection reason
    for score in plan.rationale.per_partner_scores:
        if not score.selected:
            assert score.rejection_reason is not None
            assert len(score.rejection_reason) > 0

    # Selected partners must have no rejection reason
    for score in plan.rationale.per_partner_scores:
        if score.selected:
            assert score.rejection_reason is None

    # Each scored partner must have per-dimension scores
    for score in plan.rationale.per_partner_scores:
        assert len(score.dimension_scores) == 5  # 5 dimensions


# ---------------------------------------------------------------------------
# Configuration resolver produces expected parameter keys
# ---------------------------------------------------------------------------

def test_configuration_resolver_sets_microservices_parameters():
    req = _req(
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="2M users",
            confidence=0.90,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (40 engineers)",
            confidence=0.85,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="enterprise",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="platform",
            bounded_contexts=["auth", "catalog", "order", "payment", "notification", "analytics"],
            confidence=0.85,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Kafka"],
            real_time=True,
            confidence=0.90,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MICROSERVICES, "platform"), req)

    primary = plan.selected_partners[0]
    assert primary.partner_name == "microservices_design_partner"
    config = primary.configuration.parameters
    assert "service_count_threshold" in config
    assert "use_service_mesh" in config
    assert "event_driven_mode" in config
    assert config["event_driven_mode"] is True
    assert config["use_service_mesh"] is True  # 6 bounded contexts > 5


def test_configuration_resolver_sets_monolith_parameters():
    req = _req(
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="startup",
            confidence=0.95,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="1-5 engineers",
            confidence=0.90,
        ),
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="saas",
            bounded_contexts=[],
            confidence=0.80,
        ),
    )
    plan = _selector().select(_decision(ArchitecturePattern.MONOLITH, "saas"), req)

    primary = plan.selected_partners[0]
    assert primary.partner_name == "monolith_design_partner"
    config = primary.configuration.parameters
    assert "module_style" in config
    assert "embedded_db" in config
    assert "target_module_count" in config
