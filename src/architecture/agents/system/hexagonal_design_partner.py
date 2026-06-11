from src.architecture.agents.base import BaseArchitectureAgent
from src.architecture.context.pipeline_context import PipelineContext
from src.architecture.schemas.requirements import ArchitectureRequirements
from src.architecture.schemas.solution import (
    ArchitectureLayer,
    ComponentType,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
)
from src.architecture.schemas.system_design import (
    ApplicationCore,
    DependencyComplianceMap,
    DependencyRule,
    DomainEntity,
    HexagonalArchitectureDesign,
    HexagonalDomainService,
    HexagonalPort,
    HexagonalSystemDesign,
    HexagonalTestingStrategy,
    LayerTestingStrategy,
    PortType,
    SystemDesignOutput,
    UseCase,
    ValueObject,
)


def _driving_ports(req: ArchitectureRequirements, primary_domain: str) -> list[HexagonalPort]:
    domain_title = primary_domain.title().replace("-", "").replace(" ", "")
    ports = [
        HexagonalPort(
            name="RestApiPort",
            port_type=PortType.DRIVING,
            interface_name=f"I{domain_title}UseCase",
            description="HTTP REST entry point that drives application use cases",
            adapter_implementations=["FastAPI Controller", "Flask Blueprint"],
        ),
    ]
    if req.integration.real_time is True or any(
        kw in " ".join(req.integration.integration_patterns).lower()
        for kw in ("event", "kafka", "rabbitmq", "pubsub")
    ):
        ports.append(HexagonalPort(
            name="EventSubscriberPort",
            port_type=PortType.DRIVING,
            interface_name="IEventHandler",
            description="Inbound event consumer that drives domain commands",
            adapter_implementations=["Kafka Consumer", "RabbitMQ Consumer"],
        ))
    if req.integration.external_systems:
        ports.append(HexagonalPort(
            name="WebhookPort",
            port_type=PortType.DRIVING,
            interface_name="IWebhookHandler",
            description="Receives inbound webhook calls from external partners",
            adapter_implementations=["FastAPI Webhook Controller"],
        ))
    return ports


def _driven_ports(req: ArchitectureRequirements, primary_domain: str) -> list[HexagonalPort]:
    domain_title = primary_domain.title().replace("-", "").replace(" ", "")
    ports = [
        HexagonalPort(
            name="RepositoryPort",
            port_type=PortType.DRIVEN,
            interface_name=f"I{domain_title}Repository",
            description="Persistence abstraction shielding domain from storage technology",
            adapter_implementations=["SQLAlchemy Adapter", "MongoDB Adapter"],
        ),
    ]
    for system in req.integration.external_systems[:4]:
        slug = system.replace(" ", "").replace("-", "")
        ports.append(HexagonalPort(
            name=f"{slug}Port",
            port_type=PortType.DRIVEN,
            interface_name=f"I{slug}Gateway",
            description=f"Outbound adapter for {system} integration",
            adapter_implementations=[f"{system} HTTP Client", f"{system} SDK Adapter"],
        ))
    if req.integration.real_time is True:
        ports.append(HexagonalPort(
            name="EventPublisherPort",
            port_type=PortType.DRIVEN,
            interface_name="IEventPublisher",
            description="Outbound event publisher for domain events",
            adapter_implementations=["Kafka Producer", "RabbitMQ Publisher"],
        ))
    return ports


def _domain_services(req: ArchitectureRequirements, primary_domain: str) -> list[HexagonalDomainService]:
    sources = (
        req.domain_boundaries.bounded_contexts
        or req.domain_boundaries.subdomains
        or [primary_domain]
    )
    return [
        HexagonalDomainService(
            name=f"{ctx.title().replace('-', '').replace(' ', '')}DomainService",
            responsibilities=[
                f"Encapsulates {ctx} business rules and domain invariants",
                f"Orchestrates {ctx} use cases via inbound ports",
            ],
            dependencies=["RepositoryPort"],
        )
        for ctx in sources
    ]


def _application_core(
    req: ArchitectureRequirements,
    solution: SolutionFlowDiagram,
    primary_domain: str,
    domain_services: list[HexagonalDomainService],
) -> ApplicationCore:
    sources = (
        req.domain_boundaries.bounded_contexts
        or req.domain_boundaries.subdomains
        or [primary_domain]
    )
    domain_title = primary_domain.title().replace("-", "").replace(" ", "")
    
    entity_names: list[str] = [ctx.title().replace("-", "").replace(" ", "") for ctx in sources]
    seen = set(entity_names)
    for node in solution.component_view.nodes:
        if node.layer == ArchitectureLayer.DOMAIN and node.type == ComponentType.SERVICE:
            slug = node.label.replace(" ", "").replace("-", "")
            if slug not in seen:
                entity_names.append(slug)
                seen.add(slug)

    entities = [
        DomainEntity(
            name=name,
            attributes=["id: UUID", "created_at: datetime", "updated_at: datetime"],
            invariants=[f"{name} business invariants enforced at entity level"],
        )
        for name in entity_names
    ]

    value_objects = [
        ValueObject(name=f"{domain_title}Id", attributes=["value: UUID"]),
        ValueObject(name=f"{domain_title}Status", attributes=["value: str"]),
    ]
    
    use_cases: list[UseCase] = []
    for node in solution.component_view.nodes:
        if node.layer == ArchitectureLayer.APPLICATION:
            use_cases.append(UseCase(
                name=node.label.replace(" ", ""),
                description=node.responsibility,
                driving_port="RestApiPort",
                driven_ports=["RepositoryPort"],
            ))
    if not use_cases:
        use_cases = [
            UseCase(
                name=f"Create{domain_title}UseCase",
                description=f"Creates a new {primary_domain} entity through the application service",
                driving_port="RestApiPort",
                driven_ports=["RepositoryPort"],
            ),
            UseCase(
                name=f"Update{domain_title}UseCase",
                description=f"Updates an existing {primary_domain} entity",
                driving_port="RestApiPort",
                driven_ports=["RepositoryPort"],
            ),
            UseCase(
                name=f"Get{domain_title}UseCase",
                description=f"Retrieves {primary_domain} entity by id",
                driving_port="RestApiPort",
                driven_ports=["RepositoryPort"],
            ),
        ]

    return ApplicationCore(
        domain_entities=entities,
        value_objects=value_objects,
        domain_services=domain_services,
        use_cases=use_cases,
    )


def _dependency_compliance_map() -> DependencyComplianceMap:
    return DependencyComplianceMap(
        rules=[
            DependencyRule(
                layer="domain",
                allowed_dependencies=[],
                forbidden_dependencies=["infrastructure", "adapters", "frameworks"],
                compliant=True,
                violations=[],
            ),
            DependencyRule(
                layer="application",
                allowed_dependencies=["domain"],
                forbidden_dependencies=["infrastructure", "adapters"],
                compliant=True,
                violations=[],
            ),
            DependencyRule(
                layer="driving_adapters",
                allowed_dependencies=["application (via driving ports)"],
                forbidden_dependencies=["domain", "driven_adapters"],
                compliant=True,
                violations=[],
            ),
            DependencyRule(
                layer="driven_adapters",
                allowed_dependencies=["driven ports (interfaces only)"],
                forbidden_dependencies=["domain", "application use cases"],
                compliant=True,
                violations=[],
            ),
        ],
        overall_compliant=True,
        summary=(
            "All dependencies point inward: driven/driving adapters depend only on port interfaces; "
            "the application layer depends only on the domain; "
            "the domain layer has no outward dependencies. "
            "No infrastructure concern leaks into the Application Core."
        ),
    )


def _testing_strategy(primary_domain: str, driven_ports: list[HexagonalPort]) -> HexagonalTestingStrategy:
    domain_title = primary_domain.title().replace("-", "").replace(" ", "")
    driven_port_names = [p.name for p in driven_ports]
    return HexagonalTestingStrategy(
        domain_layer=LayerTestingStrategy(
            layer="domain",
            approach="Pure unit tests — no infrastructure, no mocks, no I/O",
            test_types=[
                "entity invariant tests",
                "value object equality and immutability tests",
                "domain service business rule tests",
            ],
            mocking_required=[],
            example_scenarios=[
                f"test_{primary_domain}_entity_rejects_invalid_state",
                f"test_{domain_title}Id_equality_is_value_based",
                f"test_{primary_domain}_domain_service_enforces_invariants",
            ],
        ),
        use_case_layer=LayerTestingStrategy(
            layer="application",
            approach="Unit tests with port mocks — real domain objects, fake adapters",
            test_types=[
                "use case orchestration tests",
                "driven-port interaction verification",
                "error and exception handling tests",
            ],
            mocking_required=driven_port_names,
            example_scenarios=[
                f"test_create_{primary_domain}_use_case_persists_via_repository_port",
                f"test_update_{primary_domain}_use_case_raises_not_found_when_missing",
                f"test_use_case_publishes_domain_event_on_success",
            ],
        ),
        adapter_layer=LayerTestingStrategy(
            layer="adapters",
            approach="Integration tests against real infrastructure (test containers or local stubs)",
            test_types=[
                "repository adapter integration tests",
                "HTTP controller contract tests",
                "event adapter end-to-end tests",
            ],
            mocking_required=[],
            example_scenarios=[
                f"test_{primary_domain}_sqlalchemy_adapter_round_trip",
                "test_fastapi_controller_returns_201_on_valid_create",
                "test_kafka_producer_publishes_correct_event_schema",
            ],
        ),
    )


class HexagonalDesignPartnerAgent(BaseArchitectureAgent):

    name = "hexagonal_design_partner"
    description = (
        "Produces a full hexagonal (ports-and-adapters) architecture design from a solution "
        "flow diagram, architecture decision, and requirements. Identifies the Application Core "
        "(domain entities, value objects, domain services, use cases), driving and driven ports, "
        "concrete technology adapters, a dependency-rule compliance map, and a per-layer "
        "testing strategy."
    )
    system_prompt = ""

    def design(
        self,
        solution: SolutionFlowDiagram,
        decision: SolutionArchitectureDecision,
        requirements: ArchitectureRequirements,
    ) -> HexagonalArchitectureDesign:
        primary_domain = (
            requirements.domain_boundaries.primary_domain or decision.domain or "core"
        )
        domain_title = primary_domain.title().replace("-", "").replace(" ", "")

        domain_svcs = _domain_services(requirements, primary_domain)
        driving = _driving_ports(requirements, primary_domain)
        driven = _driven_ports(requirements, primary_domain)
        core = _application_core(requirements, solution, primary_domain, domain_svcs)
        dep_map = _dependency_compliance_map()
        testing = _testing_strategy(primary_domain, driven)

        acl = [
            f"Anti-Corruption Layer for {sys}"
            for sys in requirements.integration.external_systems
        ]

        tech_adapters: dict[str, list[str]] = {
            "RestApiPort": ["FastAPI", "Pydantic models"],
            "RepositoryPort": ["SQLAlchemy 2.0", "Alembic migrations"],
        }
        for port in driven:
            if port.name not in tech_adapters:
                tech_adapters[port.name] = port.adapter_implementations

        return HexagonalArchitectureDesign(
            decision_id=decision.decision_id,
            domain=primary_domain,
            application_core=core,
            driving_ports=driving,
            driven_ports=driven,
            technology_adapters=tech_adapters,
            anti_corruption_layers=acl,
            dependency_compliance_map=dep_map,
            testing_strategy=testing,
            rationale=(
                f"Hexagonal architecture for '{primary_domain}' domain isolates core logic "
                f"via {len(driving)} driving port(s) and {len(driven)} driven port(s). "
                f"Application Core contains {len(core.domain_entities)} entity(ies), "
                f"{len(core.value_objects)} value object(s), and {len(core.use_cases)} use case(s). "
                f"{len(acl)} anti-corruption layer(s) guard external integrations."
            ),
            design_confidence=decision.decision_confidence,
        )

    async def run(self, context: PipelineContext) -> PipelineContext:
        if context.decision is None or context.requirements is None or context.diagram is None:
            return context

        arch_design = self.design(context.diagram, context.decision, context.requirements)

        if context.system_design is None:
            context.system_design = SystemDesignOutput(
                decision_id=context.decision.decision_id,
                active_partner=self.name,
            )

        context.system_design.hexagonal_architecture_design = arch_design
        context.system_design.active_partner = self.name
        
        context.system_design.hexagonal_design = HexagonalSystemDesign(
            decision_id=context.decision.decision_id,
            domain_services=arch_design.application_core.domain_services,
            driving_ports=arch_design.driving_ports,
            driven_ports=arch_design.driven_ports,
            anti_corruption_layers=arch_design.anti_corruption_layers,
            technology_adapters=arch_design.technology_adapters,
            rationale=arch_design.rationale,
            design_confidence=arch_design.design_confidence,
        )

        return context
