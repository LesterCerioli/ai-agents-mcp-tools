import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from app.architecture.schemas.solid import (
    ComplianceLevel,
    CrossPrincipleCorrelation,
    NormalizedDesignInput,
    PrincipleResult,
    SOLIDComplianceReport,
    SOLIDPrinciple,
    PRINCIPLE_NAMES,
)
from app.skills.base import SkillCategory
from app.llm.prompts import SOLID_EXPERT
from .base import AgentContext, AgentResult, BaseAgent

if TYPE_CHECKING:
    from app.architecture.context.pipeline_context import PipelineContext
    from app.architecture.schemas.solution import SolutionArchitectureDecision
    from app.architecture.schemas.system_design import SystemDesignOutput
    from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_SKILL_MAP: dict[SOLIDPrinciple, str] = {
    SOLIDPrinciple.SRP: "solid.srp_analyze",
    SOLIDPrinciple.OCP: "solid.ocp_analyze",
    SOLIDPrinciple.LSP: "solid.lsp_analyze",
    SOLIDPrinciple.ISP: "solid.isp_analyze",
    SOLIDPrinciple.DIP: "solid.dip_analyze",
}


def _normalize_from_decision(decision: "SolutionArchitectureDecision") -> NormalizedDesignInput:
    components = [
        {
            "name": c.name,
            "type": c.type.value,
            "layer": c.layer.value,
            "responsibility": c.responsibility,
            "technology_hints": c.technology_hints,
            "protocols": c.protocols,
        }
        for c in decision.components
    ]
    pattern = decision.primary_pattern.pattern.value if decision.primary_pattern else ""
    has_gateway = any(c.get("type") == "gateway" for c in components)
    has_repositories = any(
        "repository" in c.get("responsibility", "").lower()
        or "repository" in " ".join(c.get("technology_hints", [])).lower()
        for c in components
    )
    service_count = sum(1 for c in components if c.get("type") == "service")

    return NormalizedDesignInput(
        pattern=pattern,
        domain=decision.domain,
        components=components,
        has_gateway=has_gateway,
        has_repositories=has_repositories,
        service_count=service_count,
    )


def _normalize_from_system_design(design: "SystemDesignOutput", pattern: str = "") -> NormalizedDesignInput:
    modules: list[dict[str, Any]] = []
    ports: list[dict[str, Any]] = []
    bounded_contexts: list[dict[str, Any]] = []
    domain_services: list[dict[str, Any]] = []
    has_ports_and_adapters = False
    has_shared_database = False
    service_count = 0

    if design.microservices_design:
        md = design.microservices_design
        pattern = pattern or "microservices"
        service_count = len(md.bounded_contexts)
        for bc in md.bounded_contexts:
            bounded_contexts.append({
                "name": bc.name,
                "service_name": bc.service_name,
                "responsibilities": bc.responsibilities,
                "communication_style": bc.communication_style.value,
                "technology_hints": bc.technology_hints,
            })
        has_shared_database = md.data_strategy.pattern.value == "shared_database"

    elif design.hexagonal_design:
        hd = design.hexagonal_design
        pattern = pattern or "hexagonal"
        for ds in hd.domain_services:
            domain_services.append({
                "name": ds.name,
                "responsibilities": ds.responsibilities,
                "dependencies": ds.dependencies,
            })
        for p in list(hd.driving_ports) + list(hd.driven_ports):
            ports.append({
                "name": p.name,
                "port_type": p.port_type.value,
                "interface_name": p.interface_name,
                "adapter_implementations": p.adapter_implementations,
            })
        has_ports_and_adapters = bool(ports)

    elif design.hexagonal_architecture_design:
        had = design.hexagonal_architecture_design
        pattern = pattern or "hexagonal"
        for ds in had.application_core.domain_services:
            domain_services.append({
                "name": ds.name,
                "responsibilities": ds.responsibilities,
                "dependencies": ds.dependencies,
            })
        for p in list(had.driving_ports) + list(had.driven_ports):
            ports.append({
                "name": p.name,
                "port_type": p.port_type.value,
                "interface_name": p.interface_name,
                "adapter_implementations": p.adapter_implementations,
            })
        has_ports_and_adapters = bool(ports)

    elif design.monolith_design:
        mnd = design.monolith_design
        pattern = pattern or "monolith"
        for m in mnd.modules:
            modules.append({
                "name": m.name,
                "responsibilities": m.responsibilities,
                "technology_hints": m.technology_hints,
                "allowed_dependencies": m.allowed_dependencies,
            })

    elif design.monolith_architecture_design:
        mad = design.monolith_architecture_design
        pattern = pattern or "monolith"
        for m in mad.modules:
            modules.append({
                "name": m.name,
                "responsibilities": m.responsibilities,
                "technology_hints": m.technology_hints,
                "allowed_dependencies": m.allowed_dependencies,
            })

    return NormalizedDesignInput(
        pattern=pattern,
        modules=modules,
        ports=ports,
        bounded_contexts=bounded_contexts,
        domain_services=domain_services,
        has_ports_and_adapters=has_ports_and_adapters,
        has_shared_database=has_shared_database,
        service_count=service_count,
    )


def _merge_inputs(a: NormalizedDesignInput, b: NormalizedDesignInput) -> NormalizedDesignInput:
    return NormalizedDesignInput(
        pattern=a.pattern or b.pattern,
        domain=a.domain or b.domain,
        components=a.components + b.components,
        modules=a.modules + b.modules,
        ports=a.ports + b.ports,
        bounded_contexts=a.bounded_contexts + b.bounded_contexts,
        domain_services=a.domain_services + b.domain_services,
        has_gateway=a.has_gateway or b.has_gateway,
        has_repositories=a.has_repositories or b.has_repositories,
        has_ports_and_adapters=a.has_ports_and_adapters or b.has_ports_and_adapters,
        has_shared_database=a.has_shared_database or b.has_shared_database,
        service_count=max(a.service_count, b.service_count),
    )


def _detect_cross_principle_correlations(
    results: list[PrincipleResult],
) -> list[CrossPrincipleCorrelation]:
    correlations: list[CrossPrincipleCorrelation] = []

    violated_by: dict[SOLIDPrinciple, set[str]] = {}
    for r in results:
        if r.compliance_level == ComplianceLevel.VIOLATION:
            violated_by[r.principle] = {ac.component_name for ac in r.affected_components}

    srp_comps = violated_by.get(SOLIDPrinciple.SRP, set())
    isp_comps = violated_by.get(SOLIDPrinciple.ISP, set())
    shared_srp_isp = srp_comps & isp_comps
    for comp in shared_srp_isp:
        correlations.append(CrossPrincipleCorrelation(
            primary_principle=SOLIDPrinciple.SRP,
            cascaded_principles=[SOLIDPrinciple.ISP],
            component_name=comp,
            description=(
                f"Component '{comp}' violates SRP (multiple responsibilities) and consequently ISP "
                "(exposes a fat interface to clients who need only a subset of its capabilities). "
                "Decomposing responsibilities will naturally segregate the interface."
            ),
        ))

    ocp_violated = SOLIDPrinciple.OCP in violated_by
    dip_violated = SOLIDPrinciple.DIP in violated_by
    if ocp_violated and dip_violated:
        ocp_comps = violated_by[SOLIDPrinciple.OCP]
        dip_comps = violated_by[SOLIDPrinciple.DIP]
        shared = ocp_comps & dip_comps or {"Architecture"}
        for comp in list(shared)[:2]:
            correlations.append(CrossPrincipleCorrelation(
                primary_principle=SOLIDPrinciple.OCP,
                cascaded_principles=[SOLIDPrinciple.DIP],
                component_name=comp,
                description=(
                    f"Missing abstractions (OCP violation) in '{comp}' cascade into DIP violations: "
                    "high-level modules cannot depend on abstractions that do not exist, "
                    "forcing them to depend on concrete low-level implementations."
                ),
            ))

    dip_comps_set = violated_by.get(SOLIDPrinciple.DIP, set())
    lsp_comps_set = violated_by.get(SOLIDPrinciple.LSP, set())
    if dip_comps_set and lsp_comps_set:
        shared = dip_comps_set & lsp_comps_set or {"Infrastructure Boundary"}
        for comp in list(shared)[:1]:
            correlations.append(CrossPrincipleCorrelation(
                primary_principle=SOLIDPrinciple.DIP,
                cascaded_principles=[SOLIDPrinciple.LSP],
                component_name=comp,
                description=(
                    f"DIP violation in '{comp}' (direct dependency on concrete implementations) "
                    "undermines LSP: when the concrete implementation is replaced, the high-level module "
                    "that bypasses the abstraction cannot guarantee substitutability."
                ),
            ))

    srp_comps_set = violated_by.get(SOLIDPrinciple.SRP, set())
    ocp_comps_set = violated_by.get(SOLIDPrinciple.OCP, set())
    shared_srp_ocp = srp_comps_set & ocp_comps_set
    for comp in list(shared_srp_ocp)[:1]:
        correlations.append(CrossPrincipleCorrelation(
            primary_principle=SOLIDPrinciple.SRP,
            cascaded_principles=[SOLIDPrinciple.OCP],
            component_name=comp,
            description=(
                f"Component '{comp}' violates SRP (multiple responsibilities) and OCP: "
                "a component with multiple concerns must be modified whenever any of those concerns changes, "
                "making it inherently closed to extension."
            ),
        ))

    return correlations


def _compute_overall_compliance(results: list[PrincipleResult]) -> ComplianceLevel:
    if any(r.compliance_level == ComplianceLevel.VIOLATION for r in results):
        return ComplianceLevel.VIOLATION
    if any(r.compliance_level == ComplianceLevel.WARNING for r in results):
        return ComplianceLevel.WARNING
    return ComplianceLevel.COMPLIANT


class SOLIDPrinciplesEnforcerAgent(BaseAgent):
    """
    Architecture-level SOLID Principles Enforcer Agent.

    Automatically triggered after a design partner produces a system design artifact.
    Dispatches each principle to its dedicated skill and aggregates a SOLIDComplianceReport.
    """

    name = "solid"
    description = (
        "SOLID Principles Enforcer — analyses any architecture design artifact and evaluates "
        "compliance with all five SOLID principles (SRP, OCP, LSP, ISP, DIP). "
        "Produces a per-principle report with affected components, recommendations, and "
        "cross-principle cascade correlations."
    )
    category = SkillCategory.SOLID
    system_prompt = SOLID_EXPERT

    async def analyze(
        self,
        design_artifact: "SolutionArchitectureDecision | SystemDesignOutput | PipelineContext | NormalizedDesignInput",
    ) -> SOLIDComplianceReport:
        """
        Main entry point: evaluate all five SOLID principles against a design artifact.

        Accepts any of the pipeline design output types. The agent normalises the input
        internally and dispatches to the five principle skills in parallel.
        """
        inp = self._normalize(design_artifact)
        input_dict = inp.to_dict()
        component_count = len(inp.components) + len(inp.modules) + len(inp.bounded_contexts)

        skill_names = list(_SKILL_MAP.values())
        raw_results: list[Any] = await asyncio.gather(
            *[self.execute_skill(sk, design_input=input_dict) for sk in skill_names],
            return_exceptions=True,
        )

        principle_results: list[PrincipleResult] = []
        for principle, skill_result in zip(_SKILL_MAP.keys(), raw_results):
            if isinstance(skill_result, Exception):
                logger.warning("SOLID skill %s raised: %s", _SKILL_MAP[principle], skill_result)
                principle_results.append(PrincipleResult(
                    principle=principle,
                    compliance_level=ComplianceLevel.WARNING,
                    summary=f"Analysis could not be completed: {skill_result}",
                ))
                continue

            if skill_result.success and skill_result.artifacts:
                try:
                    data = json.loads(skill_result.artifacts[0].content)
                    principle_results.append(PrincipleResult(**data))
                except Exception as exc:
                    logger.warning("Failed to parse %s result: %s", principle, exc)
                    principle_results.append(PrincipleResult(
                        principle=principle,
                        compliance_level=ComplianceLevel.WARNING,
                        summary="Result parsing failed.",
                    ))
            else:
                principle_results.append(PrincipleResult(
                    principle=principle,
                    compliance_level=ComplianceLevel.WARNING,
                    summary=skill_result.error or "Skill returned no artifacts.",
                ))

        correlations = _detect_cross_principle_correlations(principle_results)
        overall = _compute_overall_compliance(principle_results)

        violated = [r for r in principle_results if r.compliance_level == ComplianceLevel.VIOLATION]
        summary_parts = [
            f"SOLID analysis complete for {inp.pattern or 'unknown'} architecture. "
            f"{component_count} design element(s) analyzed.",
        ]
        if violated:
            names = ", ".join(PRINCIPLE_NAMES[r.principle] for r in violated)
            summary_parts.append(f"Violations detected in: {names}.")
        if correlations:
            summary_parts.append(f"{len(correlations)} cross-principle cascade(s) identified.")
        if not violated:
            summary_parts.append("All five SOLID principles are satisfied.")

        return SOLIDComplianceReport(
            principle_results=principle_results,
            cross_principle_correlations=correlations,
            overall_compliance=overall,
            components_analyzed=component_count,
            analysis_summary=" ".join(summary_parts),
            architecture_pattern=inp.pattern,
        )

    def _normalize(
        self,
        artifact: "SolutionArchitectureDecision | SystemDesignOutput | PipelineContext | NormalizedDesignInput",
    ) -> NormalizedDesignInput:
        from app.architecture.schemas.system_design import SystemDesignOutput
        from app.architecture.schemas.solution import SolutionArchitectureDecision
        from app.architecture.context.pipeline_context import PipelineContext

        if isinstance(artifact, NormalizedDesignInput):
            return artifact

        if isinstance(artifact, PipelineContext):
            ctx: PipelineContext = artifact
            decision_inp = (
                _normalize_from_decision(ctx.decision) if ctx.decision else NormalizedDesignInput()
            )
            design_inp = (
                _normalize_from_system_design(
                    ctx.system_design,
                    pattern=decision_inp.pattern,
                )
                if ctx.system_design
                else NormalizedDesignInput()
            )
            merged = _merge_inputs(decision_inp, design_inp)
            if not merged.domain and ctx.requirements and ctx.requirements.domain_boundaries:
                merged.domain = ctx.requirements.domain_boundaries.primary_domain or ""
            return merged

        if isinstance(artifact, SolutionArchitectureDecision):
            return _normalize_from_decision(artifact)

        if isinstance(artifact, SystemDesignOutput):
            return _normalize_from_system_design(artifact)

        return NormalizedDesignInput()

    async def run(self, context: AgentContext) -> AgentResult:
        """Standard BaseAgent interface — wraps analyze() for orchestrator dispatch."""
        from app.architecture.schemas.solid import NormalizedDesignInput as NDI

        inp: NDI | None = context.metadata.get("design_input")
        if inp is None:
            inp = NDI()

        try:
            report = await self.analyze(inp)
            return AgentResult(
                success=True,
                summary=report.analysis_summary,
                agent_name=self.name,
            )
        except Exception as exc:
            logger.exception("SOLID analysis failed")
            return AgentResult(
                success=False,
                summary="SOLID analysis failed.",
                agent_name=self.name,
                error=str(exc),
            )
