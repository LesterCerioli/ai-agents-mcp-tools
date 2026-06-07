from src.architecture.agents.base import BaseArchitectureAgent
from src.architecture.context.pipeline_context import PipelineContext
from src.architecture.schemas.requirements import ArchitectureRequirements
from src.architecture.schemas.solution import SolutionArchitectureDecision
from src.architecture.schemas.system_design import (
    HexagonalDomainService,
    HexagonalPort,
    HexagonalSystemDesign,
    PortType,
    SystemDesignOutput,
)


def _driving_ports(req: ArchitectureRequirements, primary_domain: str) -> list[HexagonalPort]:
    ports = [
        HexagonalPort(
            name="RestApiPort",
            port_type=PortType.DRIVING,
            interface_name=f"I{primary_domain.title().replace('-', '').replace(' ', '')}UseCase",
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


class HexagonalDesignPartnerAgent(BaseArchitectureAgent):

    name = "hexagonal_design_partner"
    description = (
        "Produces a hexagonal (ports-and-adapters) system design from a solution architecture "
        "decision. Identifies driving and driven ports, domain services, anti-corruption layers, "
        "and maps concrete technology adapters to each port."
    )
    system_prompt = ""

    def design(
        self,
        decision: SolutionArchitectureDecision,
        req: ArchitectureRequirements,
    ) -> HexagonalSystemDesign:
        primary_domain = req.domain_boundaries.primary_domain or decision.domain or "core"

        domain_services = _domain_services(req, primary_domain)
        driving = _driving_ports(req, primary_domain)
        driven = _driven_ports(req, primary_domain)

        acl = [
            f"Anti-Corruption Layer for {sys}"
            for sys in req.integration.external_systems
        ]

        tech_adapters: dict[str, list[str]] = {
            "RestApiPort": ["FastAPI", "Pydantic models"],
            "RepositoryPort": ["SQLAlchemy 2.0", "Alembic migrations"],
        }
        for port in driven:
            if port.name not in tech_adapters:
                tech_adapters[port.name] = port.adapter_implementations

        return HexagonalSystemDesign(
            decision_id=decision.decision_id,
            domain_services=domain_services,
            driving_ports=driving,
            driven_ports=driven,
            anti_corruption_layers=acl,
            technology_adapters=tech_adapters,
            rationale=(
                f"Hexagonal architecture for '{primary_domain}' domain isolates core logic "
                f"via {len(driving)} driving ports and {len(driven)} driven ports. "
                f"{len(acl)} anti-corruption layer(s) guard external integrations."
            ),
            design_confidence=decision.decision_confidence,
        )

    async def run(self, context: PipelineContext) -> PipelineContext:
        if context.decision is None or context.requirements is None:
            return context
        design = self.design(context.decision, context.requirements)
        if context.system_design is None:
            context.system_design = SystemDesignOutput(
                decision_id=context.decision.decision_id,
                active_partner=self.name,
            )
        context.system_design.hexagonal_design = design
        context.system_design.active_partner = self.name
        return context
