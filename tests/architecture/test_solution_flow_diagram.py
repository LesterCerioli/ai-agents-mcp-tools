import pytest

from app.architecture.agents.solution_flow_diagram import SolutionFlowDiagramAgent
from app.architecture.schemas.solution import (
    ArchitectureLayer,
    ArchitecturePattern,
    ComponentType,
    DecisionComponent,
    DiagramView,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
    SolutionPattern,
)


@pytest.fixture
def agent() -> SolutionFlowDiagramAgent:
    return SolutionFlowDiagramAgent(llm=None)



def _comp(
    name: str,
    type: ComponentType,
    layer: ArchitectureLayer,
    responsibility: str,
    technology_hints: list[str] | None = None,
    protocols: list[str] | None = None,
) -> DecisionComponent:
    return DecisionComponent(
        name=name,
        type=type,
        layer=layer,
        responsibility=responsibility,
        technology_hints=technology_hints or [],
        protocols=protocols or [],
    )


def _pattern(p: ArchitecturePattern, rationale: str = "Selected based on requirements") -> SolutionPattern:
    return SolutionPattern(pattern=p, rationale=rationale, confidence=0.9)


def _assert_view_populated(view: DiagramView) -> None:
    assert view.mermaid, "mermaid string must not be empty"
    assert len(view.nodes) > 0, "view must contain at least one node"


def _assert_all_nodes_have_metadata(diagram: SolutionFlowDiagram) -> None:
    for node in diagram.component_view.nodes:
        assert node.type is not None
        assert node.responsibility



ECOMMERCE_DECISION = SolutionArchitectureDecision(
    decision_id="ecom-001",
    domain="e-commerce",
    patterns=[
        _pattern(ArchitecturePattern.MICROSERVICES, "High team count; independent deployability needed"),
        _pattern(ArchitecturePattern.EVENT_DRIVEN, "Async order events between services"),
    ],
    components=[
        _comp("Web Storefront", ComponentType.CLIENT, ArchitectureLayer.PRESENTATION,
              "Customer-facing shopping UI", ["React", "Next.js"], ["HTTP/REST"]),
        _comp("API Gateway", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION,
              "Routes requests to microservices", ["Kong"], ["HTTP/REST"]),
        _comp("Order Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Manages order lifecycle", ["Python", "FastAPI"], ["HTTP/REST", "gRPC"]),
        _comp("Product Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Product catalog and inventory", ["Python", "FastAPI"], ["HTTP/REST"]),
        _comp("Order DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "Stores orders", ["PostgreSQL"], ["SQL"]),
        _comp("Product DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "Stores product catalog", ["PostgreSQL"], ["SQL"]),
        _comp("Event Bus", ComponentType.QUEUE, ArchitectureLayer.INFRASTRUCTURE,
              "Async order event streaming", ["Kafka"], ["AMQP"]),
    ],
    external_integrations=["Stripe", "SendGrid"],
)


class TestEcommerceScenario:
    def test_returns_solution_flow_diagram(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        assert isinstance(diagram, SolutionFlowDiagram)

    def test_decision_id_preserved(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        assert diagram.decision_id == "ecom-001"

    def test_all_three_views_populated(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        _assert_view_populated(diagram.context_view)
        _assert_view_populated(diagram.container_view)
        _assert_view_populated(diagram.component_view)

    def test_context_view_contains_gateway(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        node_ids = {n.id for n in diagram.context_view.nodes}
        assert "api_gateway" in node_ids

    def test_context_view_contains_external_integrations(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        node_labels = {n.label for n in diagram.context_view.nodes}
        assert "Stripe" in node_labels
        assert "SendGrid" in node_labels

    def test_container_view_has_subgraph_per_layer(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        mermaid = diagram.container_view.mermaid
        assert "Presentation Layer" in mermaid
        assert "Application Layer" in mermaid
        assert "Domain Layer" in mermaid
        assert "Infrastructure Layer" in mermaid

    def test_component_view_nodes_include_all_components(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        labels = {n.label for n in diagram.component_view.nodes}
        assert "Order Service" in labels
        assert "Product Service" in labels
        assert "Event Bus" in labels

    def test_annotations_contain_pattern_names(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        combined = " ".join(diagram.annotations)
        assert "microservices" in combined
        assert "event_driven" in combined

    def test_annotations_list_external_integrations(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        combined = " ".join(diagram.annotations)
        assert "Stripe" in combined
        assert "SendGrid" in combined

    def test_all_nodes_have_type_and_responsibility(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        _assert_all_nodes_have_metadata(diagram)

    def test_mermaid_starts_with_graph_directive(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(ECOMMERCE_DECISION)
        assert diagram.context_view.mermaid.startswith("graph ")
        assert diagram.container_view.mermaid.startswith("graph ")
        assert diagram.component_view.mermaid.startswith("graph ")

    def test_generation_is_idempotent(self, agent: SolutionFlowDiagramAgent):
        d1 = agent.generate(ECOMMERCE_DECISION)
        d2 = agent.generate(ECOMMERCE_DECISION)
        assert d1.context_view.mermaid == d2.context_view.mermaid
        assert d1.container_view.mermaid == d2.container_view.mermaid
        assert d1.component_view.mermaid == d2.component_view.mermaid



HEALTHCARE_DECISION = SolutionArchitectureDecision(
    decision_id="health-001",
    domain="healthcare",
    patterns=[
        _pattern(ArchitecturePattern.MONOLITH, "Small team; HIPAA constraints favour single deployment unit"),
        _pattern(ArchitecturePattern.LAYERED, "Clear separation for auditability"),
    ],
    components=[
        _comp("Patient Portal", ComponentType.CLIENT, ArchitectureLayer.PRESENTATION,
              "Patient-facing appointment UI", ["React"], ["HTTP/REST"]),
        _comp("REST API", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION,
              "Central API handling all clinical flows", ["Django REST Framework"], ["HTTP/REST"]),
        _comp("Appointment Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Appointment scheduling and management", ["Python"], ["HTTP/REST"]),
        _comp("EHR Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Electronic health record access", ["Python"], ["HL7/FHIR"]),
        _comp("Clinical DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "HIPAA-compliant patient data store", ["PostgreSQL"], ["SQL"]),
        _comp("Audit Log", ComponentType.STORAGE, ArchitectureLayer.INFRASTRUCTURE,
              "Immutable audit trail for compliance", ["S3"], ["S3 API"]),
    ],
    external_integrations=["EHR Provider", "Video Platform"],
)


class TestHealthcareScenario:
    def test_all_three_views_populated(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(HEALTHCARE_DECISION)
        _assert_view_populated(diagram.context_view)
        _assert_view_populated(diagram.container_view)
        _assert_view_populated(diagram.component_view)

    def test_domain_nodes_present(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(HEALTHCARE_DECISION)
        domain_nodes = [
            n for n in diagram.container_view.nodes
            if n.layer == ArchitectureLayer.DOMAIN
        ]
        assert len(domain_nodes) == 2

    def test_infrastructure_nodes_present(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(HEALTHCARE_DECISION)
        infra_nodes = [
            n for n in diagram.container_view.nodes
            if n.layer == ArchitectureLayer.INFRASTRUCTURE
        ]
        assert len(infra_nodes) == 2

    def test_external_integrations_appear_in_context(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(HEALTHCARE_DECISION)
        labels = {n.label for n in diagram.context_view.nodes}
        assert "EHR Provider" in labels
        assert "Video Platform" in labels

    def test_annotations_reference_domain_components(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(HEALTHCARE_DECISION)
        combined = " ".join(diagram.annotations)
        assert "Appointment Service" in combined or "EHR Service" in combined

    def test_idempotent(self, agent: SolutionFlowDiagramAgent):
        d1 = agent.generate(HEALTHCARE_DECISION)
        d2 = agent.generate(HEALTHCARE_DECISION)
        assert d1.component_view.mermaid == d2.component_view.mermaid



IOT_DECISION = SolutionArchitectureDecision(
    decision_id="iot-001",
    domain="iot",
    patterns=[
        _pattern(ArchitecturePattern.EVENT_DRIVEN, "High-throughput sensor telemetry requires async processing"),
        _pattern(ArchitecturePattern.CQRS, "Separate read/write paths for time-series queries"),
    ],
    components=[
        _comp("Device Dashboard", ComponentType.CLIENT, ArchitectureLayer.PRESENTATION,
              "Operations dashboard for factory floor", ["React"], ["WebSocket"]),
        _comp("Ingestion API", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION,
              "Receives telemetry from devices at scale", ["Python", "FastAPI"], ["HTTP/REST", "MQTT"]),
        _comp("Telemetry Processor", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Transforms and enriches raw sensor data", ["Python"], ["gRPC"]),
        _comp("Alert Engine", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Detects anomalies and triggers alerts", ["Python"], ["gRPC"]),
        _comp("Kafka Cluster", ComponentType.QUEUE, ArchitectureLayer.INFRASTRUCTURE,
              "Event streaming backbone", ["Kafka"], ["AMQP"]),
        _comp("Time-Series DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "Stores sensor telemetry", ["InfluxDB"], ["SQL"]),
    ],
    external_integrations=["AWS IoT Core", "PagerDuty"],
)


class TestIoTScenario:
    def test_all_three_views_populated(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(IOT_DECISION)
        _assert_view_populated(diagram.context_view)
        _assert_view_populated(diagram.container_view)
        _assert_view_populated(diagram.component_view)

    def test_queue_node_present_in_infrastructure(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(IOT_DECISION)
        queue_nodes = [
            n for n in diagram.component_view.nodes
            if n.type == ComponentType.QUEUE
        ]
        assert len(queue_nodes) == 1
        assert queue_nodes[0].label == "Kafka Cluster"

    def test_component_view_has_edges(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(IOT_DECISION)
        assert len(diagram.component_view.edges) > 0

    def test_mermaid_contains_node_labels(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(IOT_DECISION)
        assert "Telemetry Processor" in diagram.component_view.mermaid
        assert "Alert Engine" in diagram.component_view.mermaid

    def test_external_integrations_in_context(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(IOT_DECISION)
        labels = {n.label for n in diagram.context_view.nodes}
        assert "AWS IoT Core" in labels

    def test_idempotent(self, agent: SolutionFlowDiagramAgent):
        d1 = agent.generate(IOT_DECISION)
        d2 = agent.generate(IOT_DECISION)
        assert d1.container_view.mermaid == d2.container_view.mermaid



SAAS_DECISION = SolutionArchitectureDecision(
    decision_id="saas-001",
    domain="saas",
    patterns=[
        _pattern(ArchitecturePattern.CQRS, "Read-heavy CRM workload with separate query model"),
        _pattern(ArchitecturePattern.HEXAGONAL, "Isolate domain from infra for testability"),
    ],
    components=[
        _comp("CRM Web App", ComponentType.CLIENT, ArchitectureLayer.PRESENTATION,
              "Multi-tenant CRM UI", ["React", "TypeScript"], ["HTTP/REST"]),
        _comp("BFF Service", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION,
              "Backend-for-frontend aggregation layer", ["Node.js"], ["HTTP/REST", "GraphQL"]),
        _comp("Command Handler", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Processes write commands", ["Python"], ["gRPC"]),
        _comp("Query Handler", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Serves read-optimised projections", ["Python"], ["HTTP/REST"]),
        _comp("Write Store", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "Event store for commands", ["PostgreSQL"], ["SQL"]),
        _comp("Read Store", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "Denormalised projection store", ["Redis"], ["Redis Protocol"]),
        _comp("Message Bus", ComponentType.QUEUE, ArchitectureLayer.INFRASTRUCTURE,
              "Domain event propagation", ["RabbitMQ"], ["AMQP"]),
    ],
    external_integrations=["Salesforce", "Stripe"],
)


class TestSaasScenario:
    def test_all_three_views_populated(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SAAS_DECISION)
        _assert_view_populated(diagram.context_view)
        _assert_view_populated(diagram.container_view)
        _assert_view_populated(diagram.component_view)

    def test_both_domain_services_in_component_view(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SAAS_DECISION)
        labels = {n.label for n in diagram.component_view.nodes}
        assert "Command Handler" in labels
        assert "Query Handler" in labels

    def test_container_view_excludes_external_nodes(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SAAS_DECISION)
        external_in_container = [
            n for n in diagram.container_view.nodes
            if n.type == ComponentType.EXTERNAL
        ]
        assert len(external_in_container) == 0

    def test_annotations_contain_cqrs(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SAAS_DECISION)
        combined = " ".join(diagram.annotations)
        assert "cqrs" in combined

    def test_idempotent(self, agent: SolutionFlowDiagramAgent):
        d1 = agent.generate(SAAS_DECISION)
        d2 = agent.generate(SAAS_DECISION)
        assert d1.context_view.mermaid == d2.context_view.mermaid
        assert d1.annotations == d2.annotations



SERVERLESS_DECISION = SolutionArchitectureDecision(
    decision_id="startup-001",
    domain="marketplace",
    patterns=[
        _pattern(ArchitecturePattern.SERVERLESS, "Minimal ops overhead for a 3-person startup team"),
    ],
    components=[
        _comp("Next.js Frontend", ComponentType.CLIENT, ArchitectureLayer.PRESENTATION,
              "Server-rendered storefront", ["Next.js", "Vercel"], ["HTTP/REST"]),
        _comp("API Routes", ComponentType.GATEWAY, ArchitectureLayer.APPLICATION,
              "Serverless API endpoints", ["Next.js API Routes"], ["HTTP/REST"]),
        _comp("Business Logic", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Core marketplace rules", ["TypeScript"], ["HTTP/REST"]),
        _comp("Managed DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "Managed relational store", ["Neon PostgreSQL"], ["SQL"]),
    ],
    external_integrations=["Stripe"],
)


class TestServerlessStartupScenario:
    def test_all_three_views_populated(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SERVERLESS_DECISION)
        _assert_view_populated(diagram.context_view)
        _assert_view_populated(diagram.container_view)
        _assert_view_populated(diagram.component_view)

    def test_diagram_id_auto_generated(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SERVERLESS_DECISION)
        assert diagram.diagram_id
        assert diagram.diagram_id != diagram.decision_id

    def test_context_view_contains_stripe(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SERVERLESS_DECISION)
        labels = {n.label for n in diagram.context_view.nodes}
        assert "Stripe" in labels

    def test_component_view_contains_all_four_components(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SERVERLESS_DECISION)
        internal = [n for n in diagram.component_view.nodes if n.type != ComponentType.EXTERNAL]
        assert len(internal) == 4

    def test_all_nodes_have_type_and_responsibility(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SERVERLESS_DECISION)
        _assert_all_nodes_have_metadata(diagram)

    def test_annotations_contain_serverless(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(SERVERLESS_DECISION)
        combined = " ".join(diagram.annotations)
        assert "serverless" in combined

    def test_idempotent(self, agent: SolutionFlowDiagramAgent):
        d1 = agent.generate(SERVERLESS_DECISION)
        d2 = agent.generate(SERVERLESS_DECISION)
        assert d1.component_view.mermaid == d2.component_view.mermaid
        assert d1.container_view.mermaid == d2.container_view.mermaid



class TestDiagramSchemaIntegrity:
    @pytest.mark.parametrize("decision", [
        ECOMMERCE_DECISION,
        HEALTHCARE_DECISION,
        IOT_DECISION,
        SAAS_DECISION,
        SERVERLESS_DECISION,
    ])
    def test_all_scenarios_produce_valid_diagram(
        self,
        agent: SolutionFlowDiagramAgent,
        decision: SolutionArchitectureDecision,
    ):
        diagram = agent.generate(decision)
        assert isinstance(diagram, SolutionFlowDiagram)
        assert diagram.decision_id == decision.decision_id
        _assert_view_populated(diagram.context_view)
        _assert_view_populated(diagram.container_view)
        _assert_view_populated(diagram.component_view)

    @pytest.mark.parametrize("decision", [
        ECOMMERCE_DECISION,
        HEALTHCARE_DECISION,
        IOT_DECISION,
        SAAS_DECISION,
        SERVERLESS_DECISION,
    ])
    def test_mermaid_strings_contain_graph_keyword(
        self,
        agent: SolutionFlowDiagramAgent,
        decision: SolutionArchitectureDecision,
    ):
        diagram = agent.generate(decision)
        assert "graph" in diagram.context_view.mermaid
        assert "graph" in diagram.container_view.mermaid
        assert "graph" in diagram.component_view.mermaid

    @pytest.mark.parametrize("decision", [
        ECOMMERCE_DECISION,
        HEALTHCARE_DECISION,
        IOT_DECISION,
        SAAS_DECISION,
        SERVERLESS_DECISION,
    ])
    def test_all_component_nodes_have_technology_hints(
        self,
        agent: SolutionFlowDiagramAgent,
        decision: SolutionArchitectureDecision,
    ):
        diagram = agent.generate(decision)
        for node in diagram.component_view.nodes:
            if node.type != ComponentType.EXTERNAL:
                assert len(node.technology_hints) > 0, (
                    f"Node '{node.label}' missing technology hints"
                )



NO_EXTERNAL_DECISION = SolutionArchitectureDecision(
    decision_id="no-ext-001",
    domain="internal-tool",
    patterns=[
        _pattern(ArchitecturePattern.LAYERED, "Simple internal tool with no external dependencies"),
    ],
    components=[
        _comp("Web UI", ComponentType.CLIENT, ArchitectureLayer.PRESENTATION,
              "Internal admin interface", ["React"], ["HTTP/REST"]),
        _comp("App Service", ComponentType.SERVICE, ArchitectureLayer.DOMAIN,
              "Business logic", ["FastAPI"], ["HTTP/REST"]),
        _comp("App DB", ComponentType.DATABASE, ArchitectureLayer.INFRASTRUCTURE,
              "Persistent storage", ["PostgreSQL"], ["TCP"]),
    ],
    external_integrations=[],
)


class TestNoExternalIntegrationsScenario:
    def test_context_view_has_no_external_nodes(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(NO_EXTERNAL_DECISION)
        external_nodes = [n for n in diagram.context_view.nodes if n.type == ComponentType.EXTERNAL]
        assert external_nodes == [], "context_view must not contain EXTERNAL nodes when there are no external integrations"

    def test_container_view_is_valid_mermaid(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(NO_EXTERNAL_DECISION)
        assert diagram.container_view.mermaid.startswith("graph")
        assert "EXTERNAL" not in diagram.container_view.mermaid

    def test_annotations_omit_external_integrations_line(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(NO_EXTERNAL_DECISION)
        assert not any(
            "External integrations:" in ann for ann in diagram.annotations
        ), "annotations must not include external integrations line when list is empty"

    def test_all_views_populated(self, agent: SolutionFlowDiagramAgent):
        diagram = agent.generate(NO_EXTERNAL_DECISION)
        _assert_view_populated(diagram.context_view)
        _assert_view_populated(diagram.container_view)
        _assert_view_populated(diagram.component_view)
