import pytest

from app.architecture.agents.system.monolith_architecture_design_partner import (
    MonolithArchitectureDesignPartnerAgent,
)
from app.architecture.schemas.requirements import (
    ArchitectureRequirements,
    BudgetConstraint,
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
    DiagramEdge,
    DiagramNode,
    DiagramView,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)
from app.architecture.schemas.system_design import MonolithLayering


def _agent() -> MonolithArchitectureDesignPartnerAgent:
    return MonolithArchitectureDesignPartnerAgent(llm=None)


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
            SolutionPattern(
                pattern=ArchitecturePattern.MONOLITH,
                rationale="simple",
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



def test_modules_derived_from_bounded_contexts():
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

    assert len(design.modules) == 3
    module_names = [m.name for m in design.modules]
    assert "contact" in module_names
    assert "opportunity" in module_names
    assert "pipeline" in module_names


def test_modules_derived_from_subdomains_when_no_contexts():
    agent = _agent()
    decision = _decision("erp")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="erp",
            subdomains=["hr", "finance", "inventory", "procurement", "sales"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.modules) == 5


def test_fallback_modules_generated_when_no_domain_hints():
    agent = _agent()
    decision = _decision("blog")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="blog",
            confidence=0.7,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.modules) >= 1


def test_modular_strategy_for_bounded_contexts():
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

    assert design.layering_strategy == MonolithLayering.MODULAR


def test_vertical_slices_for_many_subdomains():
    agent = _agent()
    decision = _decision("erp")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="erp",
            subdomains=["hr", "finance", "inventory", "procurement", "sales"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.layering_strategy == MonolithLayering.VERTICAL_SLICES


def test_layered_strategy_as_default():
    agent = _agent()
    decision = _decision("blog")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="blog",
            confidence=0.7,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.layering_strategy == MonolithLayering.LAYERED



def test_each_module_has_all_four_layers():
    agent = _agent()
    decision = _decision("shop")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="shop",
            bounded_contexts=["catalog", "order", "payment"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    for module in design.modules:
        ls = module.layered_structure
        assert len(ls.presentation) >= 1
        assert len(ls.application) >= 1
        assert len(ls.domain) >= 1
        assert len(ls.infrastructure) >= 1


def test_modular_strategy_layers_contain_aggregate_and_repository():
    agent = _agent()
    decision = _decision("shop")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="shop",
            bounded_contexts=["catalog"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    module = design.modules[0]
    domain_items = " ".join(module.layered_structure.domain)
    assert "Aggregate" in domain_items or "Repository" in domain_items


def test_internal_contracts_generated_for_each_module_pair():
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

    
    assert len(design.internal_api_contracts) == 3


def test_no_internal_contracts_for_single_module():
    agent = _agent()
    decision = _decision("blog")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="blog",
            bounded_contexts=["posts"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.internal_api_contracts) == 0


def test_contract_interface_name_follows_naming_convention():
    agent = _agent()
    decision = _decision("crm")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="crm",
            bounded_contexts=["contact", "opportunity"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    contract = design.internal_api_contracts[0]
    assert contract.interface_name.startswith("I")
    assert "Port" in contract.interface_name


def test_contract_description_forbids_cross_module_db_queries():
    agent = _agent()
    decision = _decision("crm")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="crm",
            bounded_contexts=["contact", "opportunity"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    for contract in design.internal_api_contracts:
        assert "cross-module" in contract.description.lower() or "database" in contract.description.lower()


def test_module_exposes_only_its_own_contracts():
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

    for module in design.modules:
        for contract in module.internal_api_contracts:
            assert contract.source_module == module.name


def test_shared_kernel_has_data_types_utilities_and_events():
    agent = _agent()
    decision = _decision("shop")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="shop",
            confidence=0.8,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    sk = design.shared_kernel
    assert len(sk.data_types) >= 1
    assert len(sk.utilities) >= 1
    assert len(sk.events) >= 1


def test_shared_kernel_includes_audit_event_for_compliance():
    agent = _agent()
    from app.architecture.schemas.requirements import ComplianceRequirement
    decision = _decision("finance")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="finance",
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

    assert "AuditEvent" in design.shared_kernel.events


def test_shared_kernel_includes_real_time_event_when_real_time():
    agent = _agent()
    decision = _decision("stream")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="stream",
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            real_time=True,
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert "RealTimeEvent" in design.shared_kernel.events



def test_no_vertical_slice_candidates_when_no_signals_and_no_external_match():
    agent = _agent()
    decision = _decision("blog")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="blog",
            bounded_contexts=["posts", "comments"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.vertical_slice_candidates) == 0


def test_vertical_slice_now_priority_for_external_system_match():
    agent = _agent()
    decision = _decision("payment")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="payment",
            bounded_contexts=["billing", "stripe", "refund"],
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "PayPal"],
            confidence=0.9,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="10 million users",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    priorities = [vs.priority for vs in design.vertical_slice_candidates]
    assert "now" in priorities


def test_vertical_slice_candidates_capped_at_four():
    agent = _agent()
    decision = _decision("platform")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="platform",
            bounded_contexts=["a", "b", "c", "d", "e", "f"],
            confidence=0.9,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="100 million users",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.vertical_slice_candidates) <= 4


def test_no_migration_path_when_no_distribution_signals():
    agent = _agent()
    decision = _decision("blog")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="blog",
            bounded_contexts=["posts", "comments"],
            confidence=0.9,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="small (2-3 engineers)",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.migration_path is None


def test_migration_path_generated_when_high_scale():
    agent = _agent()
    decision = _decision("platform")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="platform",
            bounded_contexts=["catalog", "order"],
            confidence=0.9,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="50 million users",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.migration_path is not None
    assert len(design.migration_path.distribution_signals) >= 1
    assert len(design.migration_path.strangler_fig_candidates) >= 1


def test_migration_path_generated_when_large_team():
    agent = _agent()
    decision = _decision("enterprise")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="enterprise",
            bounded_contexts=["billing", "auth"],
            confidence=0.9,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (100+ engineers)",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.migration_path is not None
    assert len(design.migration_path.strangler_fig_candidates) == len(design.modules)


def test_strangler_fig_candidates_ordered_by_extraction_order():
    agent = _agent()
    decision = _decision("platform")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="platform",
            bounded_contexts=["catalog", "order", "payment"],
            confidence=0.9,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="5 million users",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.migration_path is not None
    orders = [c.extraction_order for c in design.migration_path.strangler_fig_candidates]
    assert orders == sorted(orders)


def test_migration_path_extraction_order_matches_candidates():
    agent = _agent()
    decision = _decision("platform")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="platform",
            bounded_contexts=["catalog", "order"],
            confidence=0.9,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="2 million users",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.migration_path is not None
    candidate_names = [c.module_name for c in design.migration_path.strangler_fig_candidates]
    assert design.migration_path.extraction_order == candidate_names



def test_acl_generated_per_external_system():
    agent = _agent()
    decision = _decision("shop")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="shop",
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "SendGrid"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.anti_corruption_layers) == 2
    assert any("Stripe" in acl for acl in design.anti_corruption_layers)
    assert any("SendGrid" in acl for acl in design.anti_corruption_layers)



def test_startup_deployment_for_small_team():
    agent = _agent()
    decision = _decision("saas")
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
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert "Docker" in design.deployment_strategy or "PaaS" in design.deployment_strategy


def test_kubernetes_deployment_for_large_team():
    agent = _agent()
    decision = _decision("enterprise")
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
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert "Kubernetes" in design.deployment_strategy


def test_exactly_three_scenario_designs_always_produced():
    agent = _agent()
    decision = _decision("shop")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="shop",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert len(design.scenario_designs) == 3
    scenarios = {s.scenario for s in design.scenario_designs}
    assert "early_stage_startup" in scenarios
    assert "mid_size_saas" in scenarios
    assert "legacy_modernization" in scenarios


def test_scenario_designs_have_distinct_strategies():
    agent = _agent()
    decision = _decision("shop")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="shop",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    strategies = {s.recommended_strategy for s in design.scenario_designs}
    assert len(strategies) == 3


def test_scenario_designs_have_key_considerations():
    agent = _agent()
    decision = _decision("shop")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="shop",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    for scenario in design.scenario_designs:
        assert len(scenario.key_considerations) >= 1


def test_scenario_early_stage_startup():
    
    agent = _agent()
    decision = _decision("cms")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="cms",
            bounded_contexts=["content", "media"],
            confidence=0.9,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="small (1-3 engineers)",
            confidence=0.9,
        ),
        budget=BudgetConstraint(
            status=SpecificationStatus.SPECIFIED,
            tier="startup",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.layering_strategy == MonolithLayering.MODULAR
    assert len(design.modules) == 2
    assert len(design.internal_api_contracts) == 1
    assert design.migration_path is None
    assert "Docker" in design.deployment_strategy or "PaaS" in design.deployment_strategy
    assert len(design.scenario_designs) == 3
    for module in design.modules:
        assert len(module.layered_structure.presentation) >= 1
        assert len(module.layered_structure.domain) >= 1


def test_scenario_mid_size_saas():
    
    agent = _agent()
    decision = _decision("ecommerce")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="ecommerce",
            bounded_contexts=["catalog", "order", "payment", "shipping", "notification"],
            confidence=0.9,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="medium (20 engineers)",
            confidence=0.9,
        ),
        integration=IntegrationRequirement(
            status=SpecificationStatus.SPECIFIED,
            external_systems=["Stripe", "SendGrid", "FedEx"],
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.layering_strategy == MonolithLayering.MODULAR
    assert len(design.modules) == 5
    
    assert len(design.internal_api_contracts) == 10
    assert len(design.anti_corruption_layers) == 3
    assert len(design.shared_kernel.data_types) >= 1
    for module in design.modules:
        assert len(module.internal_api_contracts) >= 0
        for contract in module.internal_api_contracts:
            assert contract.source_module == module.name


def test_scenario_legacy_modernization():
    
    agent = _agent()
    decision = _decision("erp")
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="erp",
            subdomains=["hr", "finance", "inventory", "procurement", "sales", "reporting"],
            confidence=0.9,
        ),
        team_size=TeamSizeSignal(
            status=SpecificationStatus.SPECIFIED,
            engineering_team_size="large (80 engineers, multiple teams)",
            confidence=0.9,
        ),
        scalability=ScalabilityRequirement(
            status=SpecificationStatus.SPECIFIED,
            expected_users="2 million enterprise users",
            confidence=0.9,
        ),
    )
    design = agent.design(_diagram(decision.decision_id), decision, req)

    assert design.layering_strategy == MonolithLayering.VERTICAL_SLICES
    assert len(design.modules) == 6
    assert design.migration_path is not None
    assert len(design.migration_path.distribution_signals) >= 2
    assert len(design.migration_path.strangler_fig_candidates) == 6
    for c in design.migration_path.strangler_fig_candidates:
        assert c.extraction_order >= 1
        assert len(c.recommended_seam) > 0
    assert len(design.scenario_designs) == 3



@pytest.mark.asyncio
async def test_run_populates_monolith_architecture_design():
    from app.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    decision = _decision("clinic")
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
    ctx.decision = decision
    ctx.diagram = _diagram(decision.decision_id)

    ctx = await agent.run(ctx)

    assert ctx.system_design is not None
    assert ctx.system_design.monolith_architecture_design is not None
    assert ctx.system_design.active_partner == "monolith_architecture_design_partner"


@pytest.mark.asyncio
async def test_run_returns_context_unchanged_when_diagram_missing():
    from app.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    req = _req(
        domain_boundaries=DomainBoundariesRequirement(
            status=SpecificationStatus.SPECIFIED,
            primary_domain="clinic",
            confidence=0.9,
        ),
    )
    ctx = PipelineContext()
    ctx.requirements = req
    ctx.decision = _decision("clinic")

    ctx = await agent.run(ctx)

    assert ctx.system_design is None


@pytest.mark.asyncio
async def test_run_returns_context_unchanged_when_decision_missing():
    from app.architecture.context.pipeline_context import PipelineContext

    agent = _agent()
    ctx = PipelineContext()
    ctx.diagram = _diagram("fake-id")

    ctx = await agent.run(ctx)

    assert ctx.system_design is None
