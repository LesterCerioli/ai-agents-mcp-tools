import pytest

from src.architecture.agents.business_objective_parser import BusinessObjectiveParserAgent
from src.architecture.context.pipeline_context import PipelineContext
from src.architecture.schemas.requirements import ArchitectureRequirements, SpecificationStatus


@pytest.fixture
def agent() -> BusinessObjectiveParserAgent:
    return BusinessObjectiveParserAgent(llm=None)


@pytest.fixture
def context() -> PipelineContext:
    return PipelineContext()



class TestEcommerceScenario:
    
    OBJECTIVE = (
        "Build an online marketplace for handmade goods with Stripe payment integration, "
        "supporting 50,000 concurrent shoppers and fast checkout flows."
    )

    async def test_domain_is_ecommerce(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.status == SpecificationStatus.SPECIFIED
        assert req.domain_boundaries.primary_domain == "e-commerce"

    async def test_stripe_detected_as_integration(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.integration.status == SpecificationStatus.SPECIFIED
        assert "Stripe" in req.integration.external_systems

    async def test_scalability_peak_load_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.scalability.status == SpecificationStatus.SPECIFIED
        assert req.scalability.peak_load is not None

    async def test_overall_confidence_above_threshold(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.overall_confidence >= 0.3

    async def test_is_complete_when_critical_dims_filled(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.is_complete is True



class TestHealthcareScenario:
    
    OBJECTIVE = (
        "Create a HIPAA-compliant telemedicine platform for 10,000 concurrent patients "
        "with video consultations, EHR integration, and 99.9% uptime SLA."
    )

    async def test_domain_is_healthcare(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "healthcare"

    async def test_hipaa_compliance_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.compliance.status == SpecificationStatus.SPECIFIED
        assert "HIPAA" in req.compliance.frameworks

    async def test_availability_uptime_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.availability.status == SpecificationStatus.SPECIFIED
        assert "99.9" in (req.availability.target_uptime or "")

    async def test_audit_trail_enabled_for_hipaa(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.compliance.audit_trail is True

    async def test_compliance_confidence_high(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.compliance.confidence >= 0.8



class TestFintechScenario:
    
    OBJECTIVE = (
        "Build a lending platform with PCI-DSS compliance for a mid-sized bank, "
        "integrating with Stripe and PayPal, supporting real-time payment processing."
    )

    async def test_domain_is_fintech(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "fintech"

    async def test_pci_dss_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "PCI-DSS" in req.compliance.frameworks

    async def test_multiple_payment_systems_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        systems = req.integration.external_systems
        assert "Stripe" in systems
        assert "PayPal" in systems

    async def test_real_time_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.integration.real_time is True


class TestSaasScenario:
    
    OBJECTIVE = (
        "Build a multi-tenant SaaS CRM for enterprise clients with 99.9% uptime SLA, "
        "Salesforce integration, and SOC2 compliance. Team of 20 engineers."
    )

    async def test_domain_is_saas(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "saas"

    async def test_soc2_compliance_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "SOC2" in req.compliance.frameworks

    async def test_salesforce_integration_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "Salesforce" in req.integration.external_systems

    async def test_team_size_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.team_size.status == SpecificationStatus.SPECIFIED
        assert req.team_size.engineering_team_size == "5-20"

    async def test_budget_tier_enterprise(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.budget.tier == "enterprise"



class TestIoTScenario:
    
    OBJECTIVE = (
        "Design a real-time IoT sensor monitoring system for smart factories, "
        "processing telemetry from 100,000 devices using Kafka event streaming "
        "and AWS infrastructure."
    )

    async def test_domain_is_iot(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "iot"

    async def test_kafka_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "Kafka" in req.integration.external_systems

    async def test_real_time_integration(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.integration.real_time is True

    async def test_aws_cloud_preference(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.budget.cloud_preference == "aws"

    async def test_scalability_signal_present(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.scalability.status != SpecificationStatus.NOT_SPECIFIED



class TestLogisticsScenario:
    
    OBJECTIVE = (
        "Build a fleet management and delivery tracking system for a logistics startup "
        "with Google Maps integration. Small team of 3 developers, MVP phase, low cost."
    )

    async def test_domain_is_logistics(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "logistics"

    async def test_google_maps_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "Google Maps" in req.integration.external_systems

    async def test_team_size_small(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.team_size.engineering_team_size == "1-5"

    async def test_budget_tier_startup(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.budget.tier == "startup"

    async def test_cost_sensitivity_high(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.budget.cost_sensitivity == "high"

    async def test_org_maturity_startup(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.team_size.organizational_maturity == "startup"



class TestEducationScenario:
    
    OBJECTIVE = (
        "Create an LMS for 50,000 students with video streaming capabilities, "
        "course management, and FERPA compliance for a university."
    )

    async def test_domain_is_education(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "education"

    async def test_ferpa_compliance_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "FERPA" in req.compliance.frameworks

    async def test_scalability_specified(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.scalability.status == SpecificationStatus.SPECIFIED



class TestSocialNetworkScenario:
    
    OBJECTIVE = (
        "Build a social network for professional communities with real-time feeds, "
        "WebSocket notifications, Redis caching, and event-driven architecture. "
        "Scale-up company with 30 engineers on GCP."
    )

    async def test_domain_is_social(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "social"

    async def test_websocket_pattern_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "WebSocket" in req.integration.integration_patterns

    async def test_redis_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "Redis" in req.integration.external_systems

    async def test_event_driven_pattern_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "Event-driven" in req.integration.integration_patterns

    async def test_gcp_cloud_preference(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.budget.cloud_preference == "gcp"

    async def test_team_size_20_100(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.team_size.engineering_team_size == "20-100"



class TestMediaStreamingScenario:
    
    OBJECTIVE = (
        "Build a video streaming platform with CDN content delivery, "
        "supporting 1 million concurrent viewers and fault-tolerant infrastructure on AWS."
    )

    async def test_domain_is_media(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.domain_boundaries.primary_domain == "media"

    async def test_scalability_million_users(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.scalability.status == SpecificationStatus.SPECIFIED
        assert req.scalability.expected_users is not None

    async def test_availability_fault_tolerant(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.availability.status != SpecificationStatus.NOT_SPECIFIED

    async def test_aws_cloud(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.budget.cloud_preference == "aws"



class TestEnterpriseERPScenario:
    
    OBJECTIVE = (
        "Build a large enterprise ERP system on AWS for a Fortune 500 company "
        "with SOX compliance, ISO 27001 certification, and a team of 150 engineers."
    )

    async def test_budget_tier_enterprise(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.budget.tier == "enterprise"

    async def test_sox_compliance_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "SOX" in req.compliance.frameworks

    async def test_iso27001_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert "ISO 27001" in req.compliance.frameworks

    async def test_team_size_100_plus(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.team_size.engineering_team_size == "100+"

    async def test_org_maturity_enterprise(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.team_size.organizational_maturity == "enterprise"



class TestMinimalInputScenario:
    
    OBJECTIVE = "Build a web app"

    async def test_returns_architecture_requirements(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert isinstance(req, ArchitectureRequirements)

    async def test_most_dims_not_specified(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        not_specified = [
            dim for dim, score in req.dimension_confidences().items()
            if score == 0.0
        ]
        assert len(not_specified) >= 3

    async def test_generates_clarification_questions(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert len(req.clarification_questions) >= 3

    async def test_is_not_complete(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.is_complete is False

    async def test_raw_input_preserved(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse(self.OBJECTIVE)
        assert req.raw_input == self.OBJECTIVE



class TestMultiTurnClarification:
    
    INITIAL_OBJECTIVE = "Build a healthcare appointment booking platform."
    CLARIFICATION_1 = "We need HIPAA compliance and 99.9% uptime. Startup with a team of 5 developers."
    CLARIFICATION_2 = "We'll use AWS and integrate with Stripe for appointment fees. Real-time notifications via WebSocket."
    CLARIFICATION_3 = "We expect 10,000 concurrent bookings and plan to grow to 500,000 users in 2 years."

    async def test_initial_parse_identifies_domain(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        req = await agent.parse(self.INITIAL_OBJECTIVE, context)
        assert req.domain_boundaries.primary_domain == "healthcare"

    async def test_clarification_adds_compliance(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        req = await agent.clarify(self.CLARIFICATION_1, context)
        assert "HIPAA" in req.compliance.frameworks

    async def test_clarification_adds_availability(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        req = await agent.clarify(self.CLARIFICATION_1, context)
        assert req.availability.status == SpecificationStatus.SPECIFIED

    async def test_clarification_preserves_prior_domain(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        req = await agent.clarify(self.CLARIFICATION_2, context)
        assert req.domain_boundaries.primary_domain == "healthcare"

    async def test_second_clarification_adds_integration(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        await agent.clarify(self.CLARIFICATION_1, context)
        req = await agent.clarify(self.CLARIFICATION_2, context)
        assert req.integration.status == SpecificationStatus.SPECIFIED
        assert "Stripe" in req.integration.external_systems

    async def test_third_clarification_adds_scalability(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        await agent.clarify(self.CLARIFICATION_1, context)
        await agent.clarify(self.CLARIFICATION_2, context)
        req = await agent.clarify(self.CLARIFICATION_3, context)
        assert req.scalability.status == SpecificationStatus.SPECIFIED

    async def test_context_turn_count_increases(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        await agent.clarify(self.CLARIFICATION_1, context)
        assert context.turn_count() == 2

    async def test_clarify_raises_without_prior_parse(self, agent: BusinessObjectiveParserAgent):
        fresh_context = PipelineContext()
        with pytest.raises(ValueError, match="parse\\(\\)"):
            await agent.clarify("Some answer", fresh_context)

    async def test_context_stores_requirements(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        assert context.requirements is not None

    async def test_context_ready_after_full_clarification(self, agent: BusinessObjectiveParserAgent, context: PipelineContext):
        await agent.parse(self.INITIAL_OBJECTIVE, context)
        await agent.clarify(self.CLARIFICATION_1, context)
        await agent.clarify(self.CLARIFICATION_2, context)
        await agent.clarify(self.CLARIFICATION_3, context)
        assert context.is_ready_for_next_stage() is True



class TestPipelineContext:
    def test_session_id_auto_generated(self):
        ctx = PipelineContext()
        assert isinstance(ctx.session_id, str)
        assert len(ctx.session_id) > 0

    def test_two_contexts_have_different_session_ids(self):
        ctx1 = PipelineContext()
        ctx2 = PipelineContext()
        assert ctx1.session_id != ctx2.session_id

    def test_add_turn_increments_turn_count(self):
        ctx = PipelineContext()
        ctx.add_turn("user", "hello")
        ctx.add_turn("assistant", "hi")
        assert ctx.turn_count() == 2

    def test_is_ready_false_when_no_requirements(self):
        ctx = PipelineContext()
        assert ctx.is_ready_for_next_stage() is False

    async def test_store_requirements_appends_to_history(self, agent: BusinessObjectiveParserAgent):
        ctx = PipelineContext()
        req = await agent.parse("Build an e-commerce app", ctx)
        system_events = [t for t in ctx.conversation_history if t.get("event") == "requirements_parsed"]
        assert len(system_events) >= 1



class TestArchitectureRequirementsModel:
    async def test_dimension_confidences_returns_all_seven(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse("Build a SaaS app")
        confs = req.dimension_confidences()
        assert set(confs.keys()) == {
            "scalability", "availability", "compliance",
            "domain_boundaries", "integration", "budget", "team_size",
        }

    async def test_low_confidence_dimensions_detected(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse("Build a web app")
        low = req.low_confidence_dimensions(threshold=0.4)
        assert len(low) >= 1

    async def test_confidence_scores_in_valid_range(self, agent: BusinessObjectiveParserAgent):
        req = await agent.parse("Build a HIPAA-compliant SaaS platform on AWS")
        for score in req.dimension_confidences().values():
            assert 0.0 <= score <= 1.0
