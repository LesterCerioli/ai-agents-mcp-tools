from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.requirements import ArchitectureRequirements
from app.architecture.schemas.solution import SolutionArchitectureDecision
from app.architecture.schemas.system_design import (
    MonolithLayering,
    MonolithModule,
    MonolithSystemDesign,
    SystemDesignOutput,
)

_SHARED_KERNEL = ["common-utils", "domain-events", "error-handling", "logging"]


def _is_small_team(req: ArchitectureRequirements) -> bool:
    raw = (req.team_size.engineering_team_size or "").lower()
    return any(kw in raw for kw in ["small", "1-5", "2-5", "startup", "solo", "1-3", "2-3"])


def _layering_strategy(req: ArchitectureRequirements, modules_count: int) -> MonolithLayering:
    if req.domain_boundaries.bounded_contexts:
        return MonolithLayering.MODULAR
    if modules_count > 4:
        return MonolithLayering.VERTICAL_SLICES
    return MonolithLayering.LAYERED


def _deployment_strategy(req: ArchitectureRequirements) -> str:
    budget = (req.budget.tier or "").lower()
    if any(kw in budget for kw in ("startup", "free", "low", "bootstrap", "seed")) or _is_small_team(req):
        return (
            "Single-container Docker image deployed via CI/CD pipeline (GitHub Actions). "
            "Use Blue-Green or Rolling deployment to minimise downtime."
        )
    return (
        "Containerised monolith on Kubernetes with HorizontalPodAutoscaler. "
        "Use Helm chart for environment-specific configuration."
    )


def _resolve_module_names(req: ArchitectureRequirements, decision: SolutionArchitectureDecision) -> list[str]:
    if req.domain_boundaries.bounded_contexts:
        return req.domain_boundaries.bounded_contexts
    if req.domain_boundaries.subdomains:
        return req.domain_boundaries.subdomains
    from app.architecture.schemas.solution import ComponentType
    service_components = [c for c in decision.components if c.type == ComponentType.SERVICE]
    if service_components:
        return [c.name for c in service_components]
    primary = req.domain_boundaries.primary_domain or "core"
    return [primary, f"{primary}-auth", f"{primary}-notifications"]


def _build_module(name: str, strategy: MonolithLayering, allowed: list[str]) -> MonolithModule:
    tech: list[str]
    if strategy == MonolithLayering.VERTICAL_SLICES:
        tech = ["FastAPI Router", "SQLAlchemy model", "Pydantic schema"]
    elif strategy == MonolithLayering.MODULAR:
        tech = ["Python package", "Dependency Injector"]
    else:
        tech = ["Repository pattern", "Service layer", "DTOs"]
    return MonolithModule(
        name=name,
        responsibilities=[
            f"Encapsulates all {name} business logic",
            f"Owns {name} data schema and migrations",
        ],
        allowed_dependencies=allowed,
        technology_hints=tech,
    )


_STRATEGY_RATIONALE: dict[MonolithLayering, str] = {
    MonolithLayering.MODULAR: (
        "Modular monolith enforces explicit bounded contexts with strong encapsulation "
        "while keeping a single deployable unit — ideal stepping stone toward microservices."
    ),
    MonolithLayering.VERTICAL_SLICES: (
        "Vertical slices organise code by feature rather than technical layer, "
        "reducing cross-cutting coupling and simplifying onboarding for larger teams."
    ),
    MonolithLayering.LAYERED: (
        "Classic layered architecture (presentation → application → domain → infrastructure) "
        "is well-understood, fast to implement, and appropriate for moderate complexity."
    ),
}


class MonolithDesignPartnerAgent(BaseArchitectureAgent):

    name = "monolith_design_partner"
    description = (
        "Produces a monolith system design from a solution architecture decision. "
        "Chooses the optimal intra-monolith layering strategy (layered / modular / vertical slices), "
        "defines module boundaries, shared kernel, anti-corruption layers, and deployment approach."
    )
    system_prompt = ""

    def design(
        self,
        decision: SolutionArchitectureDecision,
        req: ArchitectureRequirements,
    ) -> MonolithSystemDesign:
        module_names = _resolve_module_names(req, decision)
        strategy = _layering_strategy(req, len(module_names))

        shared = list(_SHARED_KERNEL)
        modules = [
            _build_module(name, strategy, shared)
            for name in module_names
        ]

        acl = [
            f"Anti-Corruption Layer for {sys}"
            for sys in req.integration.external_systems
        ]
        deployment = _deployment_strategy(req)

        return MonolithSystemDesign(
            decision_id=decision.decision_id,
            modules=modules,
            layering_strategy=strategy,
            anti_corruption_layers=acl,
            deployment_strategy=deployment,
            shared_kernel=shared,
            rationale=(
                f"Monolith design for '{decision.domain}' with {len(modules)} modules "
                f"using {strategy.value} strategy. "
                + _STRATEGY_RATIONALE[strategy]
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
        context.system_design.monolith_design = design
        context.system_design.active_partner = self.name
        return context
