from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.requirements import ArchitectureRequirements
from app.architecture.schemas.solution import (
    ArchitectureLayer,
    ComponentType,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
)
from app.architecture.schemas.system_design import (
    MigrationPathPlan,
    MonolithArchitectureDesign,
    MonolithArchitectureModule,
    MonolithInternalAPIContract,
    MonolithLayering,
    MonolithModuleLayer,
    MonolithScenarioDesign,
    SharedKernelIdentification,
    StranglerFigCandidate,
    SystemDesignOutput,
    VerticalSliceCandidate,
)

_SHARED_KERNEL_DATA_TYPES = ["UUID", "DateTime", "Money", "Pagination", "ErrorResponse"]
_SHARED_KERNEL_UTILITIES = ["logging", "error-handling", "validation", "serialization"]
_SHARED_KERNEL_EVENTS = ["DomainEvent", "IntegrationEvent", "EventEnvelope"]

_SCENARIO_DESIGNS: list[MonolithScenarioDesign] = [
    MonolithScenarioDesign(
        scenario="early_stage_startup",
        description=(
            "Early-stage startup: 1-5 engineers, speed-to-market priority, minimal operational overhead. "
            "Single deployable monolith on a managed PaaS (Railway, Render, or Heroku)."
        ),
        recommended_strategy=MonolithLayering.LAYERED,
        module_count=2,
        key_considerations=[
            "Favor simplicity: 2-3 modules maximum",
            "No message queues or event buses initially",
            "Single PostgreSQL database with schema-level module separation",
            "Define module boundaries via folder structure and import rules (enforce with Ruff)",
            "Add integration tests from day one to protect module boundaries",
        ],
    ),
    MonolithScenarioDesign(
        scenario="mid_size_saas",
        description=(
            "Mid-size SaaS: 10-50 engineers, multiple product teams, reliability and scalability needs. "
            "Modular monolith containerised on Kubernetes with HPA."
        ),
        recommended_strategy=MonolithLayering.MODULAR,
        module_count=5,
        key_considerations=[
            "Strict module ownership: each module owned by one product team",
            "Module boundaries enforced by Python package structure with explicit __all__",
            "Separate database schemas per module (same PostgreSQL cluster)",
            "In-process event bus for cross-module async communication",
            "Contract tests per internal API interface to detect breakage early",
            "Per-module metrics, traces, and structured logging for observability",
        ],
    ),
    MonolithScenarioDesign(
        scenario="legacy_modernization",
        description=(
            "Legacy modernization: inherited monolith with unclear boundaries and technical debt. "
            "Incremental modularisation via Strangler Fig pattern toward well-bounded modules or microservices."
        ),
        recommended_strategy=MonolithLayering.VERTICAL_SLICES,
        module_count=7,
        key_considerations=[
            "Introduce module boundaries incrementally — do not big-bang refactor",
            "Use vertical slices to separate features without touching the legacy core first",
            "Add anti-corruption layers around legacy components before extracting",
            "Identify seams using event storming or domain storytelling",
            "Track coupling metrics (fan-in/fan-out) to guide extraction order",
            "Each extracted slice becomes a testable unit before full extraction as a service",
        ],
    ),
]


def _is_small_startup(req: ArchitectureRequirements) -> bool:
    raw = (req.team_size.engineering_team_size or "").lower()
    budget = (req.budget.tier or "").lower()
    return (
        any(kw in raw for kw in ("small", "1-5", "startup", "solo", "1-3", "2-3"))
        or any(kw in budget for kw in ("startup", "free", "low", "bootstrap", "seed"))
    )


def _detect_distribution_signals(req: ArchitectureRequirements) -> list[str]:
    signals: list[str] = []
    users = (req.scalability.expected_users or "").lower()
    if any(kw in users for kw in ("million", "m+", "1m", "100k")):
        signals.append("High user scale indicates future distribution need")
    team = (req.team_size.engineering_team_size or "").lower()
    if any(kw in team for kw in ("large", "50+", "100+", "multiple teams")):
        signals.append("Large team size creates module ownership pressure")
    if req.integration.real_time is True:
        signals.append("Real-time requirements may warrant event-driven service extraction")
    if len(req.integration.external_systems) >= 4:
        signals.append(
            f"{len(req.integration.external_systems)} external integrations suggest bounded service extraction"
        )
    if len(req.domain_boundaries.bounded_contexts) >= 5:
        signals.append(
            f"{len(req.domain_boundaries.bounded_contexts)} bounded contexts indicate natural service boundaries"
        )
    return signals


def _resolve_module_names(
    decision: SolutionArchitectureDecision,
    req: ArchitectureRequirements,
    solution: SolutionFlowDiagram,
) -> list[str]:
    if req.domain_boundaries.bounded_contexts:
        return req.domain_boundaries.bounded_contexts
    if req.domain_boundaries.subdomains:
        return req.domain_boundaries.subdomains
    service_components = [c for c in decision.components if c.type == ComponentType.SERVICE]
    if service_components:
        return [c.name for c in service_components]
    domain_nodes = [
        n for n in solution.component_view.nodes
        if n.layer == ArchitectureLayer.DOMAIN
    ]
    if domain_nodes:
        return [n.label for n in domain_nodes[:6]]
    primary = req.domain_boundaries.primary_domain or "core"
    return [primary, f"{primary}-auth", f"{primary}-notifications"]


def _layering_strategy(req: ArchitectureRequirements, module_count: int) -> MonolithLayering:
    if req.domain_boundaries.bounded_contexts:
        return MonolithLayering.MODULAR
    if module_count > 4:
        return MonolithLayering.VERTICAL_SLICES
    return MonolithLayering.LAYERED


def _build_module_layer(name: str, strategy: MonolithLayering) -> MonolithModuleLayer:
    slug = name.lower().replace(" ", "_").replace("-", "_")
    title = name.title().replace("-", "").replace(" ", "")
    if strategy == MonolithLayering.VERTICAL_SLICES:
        return MonolithModuleLayer(
            presentation=[f"GET/POST /api/{slug}", f"{title}Controller"],
            application=[f"Create{title}UseCase", f"Update{title}UseCase", f"Get{title}UseCase"],
            domain=[f"{title}Entity", f"{title}ValueObject", f"{title}DomainService"],
            infrastructure=[f"{title}Repository (SQLAlchemy)", f"{title}Cache (Redis)"],
        )
    if strategy == MonolithLayering.MODULAR:
        return MonolithModuleLayer(
            presentation=[f"{title}Router (FastAPI)", f"{title}Schema (Pydantic)"],
            application=[f"{title}ApplicationService", f"{title}CommandHandler", f"{title}QueryHandler"],
            domain=[f"{title}Aggregate", f"{title}DomainEvent", f"I{title}Repository"],
            infrastructure=[f"{title}SQLAlchemyRepository", f"{title}EventPublisher"],
        )
    return MonolithModuleLayer(
        presentation=[f"{title}Controller", f"{title}DTO"],
        application=[f"{title}Service"],
        domain=[f"{title}Model", f"I{title}Repository"],
        infrastructure=[f"{title}RepositoryImpl", f"{title}Migration"],
    )


def _build_internal_contracts(module_names: list[str]) -> list[MonolithInternalAPIContract]:
    contracts: list[MonolithInternalAPIContract] = []
    for i, source in enumerate(module_names):
        for target in module_names[i + 1:]:
            src_title = source.title().replace("-", "").replace(" ", "")
            tgt_title = target.title().replace("-", "").replace(" ", "")
            src_slug = source.lower().replace("-", "_").replace(" ", "_")
            contracts.append(MonolithInternalAPIContract(
                source_module=source,
                target_module=target,
                interface_name=f"I{src_title}To{tgt_title}Port",
                description=(
                    f"Interface defining what '{source}' exposes to '{target}'. "
                    "No direct cross-module database queries — all communication through this contract."
                ),
                exposed_operations=[
                    f"get_{src_slug}_by_id",
                    f"list_{src_slug}",
                ],
            ))
    return contracts


def _tech_hints(strategy: MonolithLayering) -> list[str]:
    if strategy == MonolithLayering.VERTICAL_SLICES:
        return ["FastAPI Router", "SQLAlchemy", "Pydantic schema", "pytest"]
    if strategy == MonolithLayering.MODULAR:
        return ["Python package", "Dependency Injector", "SQLAlchemy", "pytest"]
    return ["Repository pattern", "Service layer", "DTOs", "pytest"]


def _build_modules(
    module_names: list[str],
    strategy: MonolithLayering,
    shared_kernel_utilities: list[str],
    all_contracts: list[MonolithInternalAPIContract],
) -> list[MonolithArchitectureModule]:
    return [
        MonolithArchitectureModule(
            name=name,
            responsibilities=[
                f"Encapsulates all {name} business logic and domain rules",
                f"Owns {name} data schema, migrations, and persistence",
                f"Exposes {name} operations only via defined internal API contracts",
            ],
            layered_structure=_build_module_layer(name, strategy),
            allowed_dependencies=shared_kernel_utilities,
            technology_hints=_tech_hints(strategy),
            internal_api_contracts=[c for c in all_contracts if c.source_module == name],
        )
        for name in module_names
    ]


def _assess_vertical_slices(
    module_names: list[str],
    req: ArchitectureRequirements,
    signals: list[str],
) -> list[VerticalSliceCandidate]:
    candidates: list[VerticalSliceCandidate] = []
    external_lower = [s.lower() for s in req.integration.external_systems]
    for module in module_names:
        slug = module.lower().replace("-", "").replace(" ", "")
        if any(slug in ext or ext in slug for ext in external_lower):
            candidates.append(VerticalSliceCandidate(
                module_name=module,
                justification=(
                    f"Module '{module}' closely mirrors an external integration boundary, "
                    "making it a natural candidate for independent deployment."
                ),
                priority="now" if signals else "future",
                recommended_extraction_point=f"Extract '{module}' behind an anti-corruption layer first",
            ))
        elif signals:
            candidates.append(VerticalSliceCandidate(
                module_name=module,
                justification=(
                    f"{len(signals)} distribution signal(s) detected. "
                    f"Module '{module}' has independent domain boundaries and can be extracted."
                ),
                priority="future",
                recommended_extraction_point=(
                    f"Extract after internal API contracts for '{module}' are proven stable"
                ),
            ))
    return candidates[:4]


def _build_migration_path(
    module_names: list[str],
    signals: list[str],
) -> MigrationPathPlan | None:
    if not signals:
        return None
    candidates = [
        StranglerFigCandidate(
            module_name=name,
            rationale=(
                f"'{name}' has well-defined boundaries and exposed internal API contracts "
                "suitable for extraction as an independent service."
            ),
            extraction_order=i + 1,
            recommended_seam=(
                f"Route '{name}' traffic via an API Gateway before extracting the service"
            ),
        )
        for i, name in enumerate(module_names)
    ]
    return MigrationPathPlan(
        distribution_signals=signals,
        strangler_fig_candidates=candidates,
        extraction_order=[c.module_name for c in candidates],
        migration_rationale=(
            "Apply Strangler Fig pattern: incrementally route traffic to new microservices "
            "while keeping the monolith running. Extract modules in order of least coupling first. "
            "Each module's internal API contract becomes the service contract for the extracted service."
        ),
    )


def _build_shared_kernel(req: ArchitectureRequirements) -> SharedKernelIdentification:
    extra_events: list[str] = []
    if req.integration.real_time:
        extra_events.append("RealTimeEvent")
    if req.compliance.frameworks:
        extra_events.append("AuditEvent")
    return SharedKernelIdentification(
        data_types=_SHARED_KERNEL_DATA_TYPES,
        utilities=_SHARED_KERNEL_UTILITIES,
        events=_SHARED_KERNEL_EVENTS + extra_events,
        rationale=(
            "Shared kernel contains only cross-cutting types, utilities, and event envelopes. "
            "No business logic lives here. Module-specific types must stay within their module boundary."
        ),
    )


def _deployment_strategy(req: ArchitectureRequirements) -> str:
    if _is_small_startup(req):
        return (
            "Single-container Docker image deployed via CI/CD (GitHub Actions). "
            "Managed PaaS (Railway, Render, or Heroku) for minimal ops overhead. "
            "Use Blue-Green deployment to minimise downtime."
        )
    return (
        "Containerised modular monolith on Kubernetes with HorizontalPodAutoscaler. "
        "Use Helm chart for environment-specific configuration. "
        "Separate health probes per module endpoint for granular readiness checks."
    )


class MonolithArchitectureDesignPartnerAgent(BaseArchitectureAgent):

    name = "monolith_architecture_design_partner"
    description = (
        "Produces a full Modular Monolith Architecture Design from a solution flow diagram, "
        "architecture decision, and requirements. Defines DDD bounded context module boundaries, "
        "internal API contracts (no cross-module DB queries), per-module layered structure "
        "(presentation/application/domain/infrastructure), vertical slice assessment, "
        "conditional Strangler Fig migration path, and shared kernel identification. "
        "Includes scenario designs for early-stage startup, mid-size SaaS, and legacy modernization."
    )
    system_prompt = ""

    def design(
        self,
        solution: SolutionFlowDiagram,
        decision: SolutionArchitectureDecision,
        requirements: ArchitectureRequirements,
    ) -> MonolithArchitectureDesign:
        module_names = _resolve_module_names(decision, requirements, solution)
        strategy = _layering_strategy(requirements, len(module_names))
        signals = _detect_distribution_signals(requirements)
        shared_kernel = _build_shared_kernel(requirements)
        contracts = _build_internal_contracts(module_names)
        modules = _build_modules(module_names, strategy, shared_kernel.utilities, contracts)
        vertical_slices = _assess_vertical_slices(module_names, requirements, signals)
        migration_path = _build_migration_path(module_names, signals)
        acl = [
            f"Anti-Corruption Layer for {sys}"
            for sys in requirements.integration.external_systems
        ]
        return MonolithArchitectureDesign(
            decision_id=decision.decision_id,
            modules=modules,
            layering_strategy=strategy,
            internal_api_contracts=contracts,
            shared_kernel=shared_kernel,
            vertical_slice_candidates=vertical_slices,
            migration_path=migration_path,
            anti_corruption_layers=acl,
            deployment_strategy=_deployment_strategy(requirements),
            scenario_designs=_SCENARIO_DESIGNS,
            rationale=(
                f"Modular Monolith design for '{decision.domain}' with {len(modules)} DDD bounded context "
                f"module(s) using {strategy.value} strategy. "
                f"{len(contracts)} internal API contract(s) enforce module boundaries — "
                "no cross-module database queries. "
                f"Shared kernel provides {len(shared_kernel.data_types)} shared data type(s) and "
                f"{len(shared_kernel.events)} event type(s). "
                + (
                    f"Migration path generated ({len(signals)} distribution signal(s) detected)."
                    if migration_path
                    else "No migration path required (no distribution signals detected)."
                )
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
        context.system_design.monolith_architecture_design = arch_design
        context.system_design.active_partner = self.name
        return context
