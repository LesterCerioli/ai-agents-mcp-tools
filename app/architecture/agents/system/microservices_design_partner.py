import re

from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.requirements import ArchitectureRequirements
from app.architecture.schemas.solution import ArchitecturePattern, ComponentType, SolutionArchitectureDecision
from app.architecture.schemas.system_design import (
    ApiGatewayRecommendation,
    ApiGatewayType,
    BoundedContext,
    CommunicationStyle,
    DataDistributionPattern,
    DistributedDataStrategy,
    MicroservicesSystemDesign,
    ServiceContract,
    ServiceMeshRecommendation,
    SystemDesignOutput,
)

_SERVICE_MESH_DEFAULT_THRESHOLD = 5
_EVENT_KEYWORDS = {"kafka", "rabbitmq", "sqs", "pubsub", "nats", "kinesis", "eventbridge", "event"}
_MULTI_CLIENT_DOMAINS = {"ecommerce", "e-commerce", "retail", "marketplace", "platform", "saas", "shop"}


def _is_real_time_or_event(req: ArchitectureRequirements) -> bool:
    if req.integration.real_time is True:
        return True
    text = " ".join(req.integration.external_systems + req.integration.integration_patterns).lower()
    return any(kw in text for kw in _EVENT_KEYWORDS)


def _is_high_scale(req: ArchitectureRequirements) -> bool:
    raw = (req.scalability.expected_users or "").lower()
    for pattern, threshold in [
        (r"(\d+)m", 1),
        (r"(\d+)k", 100),
        (r"(\d+),?000,?000", 1),
        (r"(\d+),?000", 100),
    ]:
        m = re.search(pattern, raw)
        if m and int(m.group(1)) >= threshold:
            return True
    return False


def _communication_style(req: ArchitectureRequirements) -> CommunicationStyle:
    if _is_real_time_or_event(req):
        return CommunicationStyle.ASYNC_EVENT
    if _is_high_scale(req):
        return CommunicationStyle.SYNC_GRPC
    return CommunicationStyle.SYNC_REST


def _data_distribution_pattern(
    decision: SolutionArchitectureDecision,
    req: ArchitectureRequirements,
) -> DataDistributionPattern:
    primary = decision.primary_pattern
    if primary and primary.pattern == ArchitecturePattern.EVENT_DRIVEN:
        return DataDistributionPattern.EVENT_SOURCING
    if any(p.pattern == ArchitecturePattern.CQRS for p in decision.patterns):
        return DataDistributionPattern.CQRS
    return DataDistributionPattern.DATABASE_PER_SERVICE


def _resolve_context_names(
    decision: SolutionArchitectureDecision,
    req: ArchitectureRequirements,
) -> list[str]:
    if req.domain_boundaries.bounded_contexts:
        return req.domain_boundaries.bounded_contexts
    if req.domain_boundaries.subdomains:
        return req.domain_boundaries.subdomains
    service_components = [c for c in decision.components if c.type == ComponentType.SERVICE]
    if service_components:
        return [c.name for c in service_components]
    primary = req.domain_boundaries.primary_domain or "core"
    return [primary, f"{primary}-auth", f"{primary}-notifications"]


def _api_gateway_type(req: ArchitectureRequirements, services_count: int) -> ApiGatewayType:
    domain = (req.domain_boundaries.primary_domain or "").lower()
    if len(req.integration.external_systems) >= 6 or services_count >= 8:
        return ApiGatewayType.FEDERATED
    if any(kw in domain for kw in _MULTI_CLIENT_DOMAINS):
        return ApiGatewayType.BFF
    return ApiGatewayType.SINGLE


def _tech_hints_for_style(style: CommunicationStyle) -> list[str]:
    if style == CommunicationStyle.ASYNC_EVENT:
        return ["Apache Kafka", "RabbitMQ", "AWS SQS/SNS"]
    if style == CommunicationStyle.SYNC_GRPC:
        return ["gRPC", "Protobuf", "Envoy"]
    return ["FastAPI", "Express.js", "Spring Boot"]


def _protocols_for_style(style: CommunicationStyle) -> list[str]:
    if style == CommunicationStyle.ASYNC_EVENT:
        return ["AMQP", "Kafka Protocol"]
    if style == CommunicationStyle.SYNC_GRPC:
        return ["gRPC", "HTTP/2"]
    return ["HTTP/REST", "JSON"]


_GATEWAY_TECH: dict[ApiGatewayType, list[str]] = {
    ApiGatewayType.SINGLE: ["Kong", "AWS API Gateway", "Nginx"],
    ApiGatewayType.BFF: ["Next.js API Routes", "Apollo Gateway", "Express Gateway"],
    ApiGatewayType.FEDERATED: ["Apollo Federation", "Kong Enterprise", "AWS API Gateway"],
}

_GATEWAY_RATIONALE: dict[ApiGatewayType, str] = {
    ApiGatewayType.SINGLE: (
        "Single gateway provides unified entry point with auth, routing, and rate limiting."
    ),
    ApiGatewayType.BFF: (
        "Backend-for-Frontend pattern optimises API responses per client type (web/mobile)."
    ),
    ApiGatewayType.FEDERATED: (
        "Federated gateway distributes API surface across team boundaries, "
        "reducing bottlenecks at enterprise scale."
    ),
}

_DATA_RATIONALE: dict[DataDistributionPattern, str] = {
    DataDistributionPattern.EVENT_SOURCING: (
        "Event-driven primary pattern mandates event sourcing: "
        "full audit trail and event replay capability."
    ),
    DataDistributionPattern.CQRS: (
        "CQRS separates read and write stores, optimising throughput for each path independently."
    ),
    DataDistributionPattern.DATABASE_PER_SERVICE: (
        "Database-per-service enforces service autonomy and prevents tight coupling via shared data."
    ),
}


class MicroservicesDesignPartnerAgent(BaseArchitectureAgent):

    name = "microservices_design_partner"
    description = (
        "Produces a concrete microservices system design from a solution architecture decision. "
        "Performs DDD-based service decomposition, selects communication patterns, "
        "recommends API gateway style, service mesh (when services exceed threshold), "
        "distributed data strategy, and generates service contracts."
    )
    system_prompt = ""

    def __init__(self, llm=None, service_mesh_threshold: int = _SERVICE_MESH_DEFAULT_THRESHOLD):
        super().__init__(llm)
        self.service_mesh_threshold = service_mesh_threshold

    def design(
        self,
        decision: SolutionArchitectureDecision,
        req: ArchitectureRequirements,
    ) -> MicroservicesSystemDesign:
        comm_style = _communication_style(req)
        data_pattern = _data_distribution_pattern(decision, req)
        context_names = _resolve_context_names(decision, req)

        bounded_contexts = [
            BoundedContext(
                name=ctx,
                service_name=f"{ctx.lower().replace(' ', '-')}-service",
                subdomain=ctx,
                responsibilities=[f"Manages {ctx} domain logic and data ownership"],
                communication_style=comm_style,
                database_strategy=data_pattern,
                technology_hints=_tech_hints_for_style(comm_style),
            )
            for ctx in context_names
        ]

        services_count = len(bounded_contexts)
        gateway_type = _api_gateway_type(req, services_count)
        api_gateway = ApiGatewayRecommendation(
            gateway_type=gateway_type,
            rationale=_GATEWAY_RATIONALE[gateway_type],
            technology_hints=_GATEWAY_TECH[gateway_type],
            bff_clients=["web", "mobile"] if gateway_type == ApiGatewayType.BFF else [],
        )

        mesh_required = services_count >= self.service_mesh_threshold
        service_mesh = ServiceMeshRecommendation(
            required=mesh_required,
            rationale=(
                f"Service mesh required: {services_count} services meet or exceed "
                f"threshold of {self.service_mesh_threshold}. "
                "Enables mTLS, observability, and traffic management."
                if mesh_required
                else f"Service mesh not required: {services_count} services below "
                f"threshold of {self.service_mesh_threshold}."
            ),
            mesh_technology=["Istio", "Linkerd", "AWS App Mesh"] if mesh_required else [],
            services_count=services_count,
        )

        event_bus: str | None = None
        cqrs_stores: list[str] = []
        if data_pattern == DataDistributionPattern.EVENT_SOURCING:
            event_bus = "Apache Kafka"
        elif data_pattern == DataDistributionPattern.CQRS:
            event_bus = "RabbitMQ"
            cqrs_stores = ["PostgreSQL (write store)", "Elasticsearch (read store)"]
        elif comm_style == CommunicationStyle.ASYNC_EVENT:
            # async inter-service communication requires an event bus even with database-per-service
            event_bus = "Apache Kafka"

        data_strategy = DistributedDataStrategy(
            pattern=data_pattern,
            rationale=_DATA_RATIONALE[data_pattern],
            event_bus=event_bus,
            cqrs_stores=cqrs_stores,
        )

        sla = req.availability.target_uptime or "99.9%"
        protocols = _protocols_for_style(comm_style)
        service_contracts = [
            ServiceContract(
                service_name=bc.service_name,
                owner_domain=bc.subdomain,
                sla=sla,
                protocols=protocols,
                schema_summary=f"OpenAPI/Protobuf schema for {bc.name} operations",
                owner_team=f"{bc.name.lower().replace(' ', '-')}-team",
            )
            for bc in bounded_contexts
        ]

        return MicroservicesSystemDesign(
            decision_id=decision.decision_id,
            bounded_contexts=bounded_contexts,
            api_gateway=api_gateway,
            service_mesh=service_mesh,
            data_strategy=data_strategy,
            service_contracts=service_contracts,
            rationale=(
                f"Microservices design for '{decision.domain}' with "
                f"{services_count} bounded contexts. "
                f"Communication: {comm_style.value}. "
                f"Data strategy: {data_pattern.value}. "
                f"Gateway: {gateway_type.value}."
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
        context.system_design.microservices_design = design
        context.system_design.active_partner = self.name
        return context
