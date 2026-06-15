import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

import app.skills.quality_assessment  # noqa: F401 — registers all 5 quality skills

from app.architecture.schemas.quality_assessment import (
    ATTRIBUTE_WEIGHTS,
    ArchitectureQualityReport,
    EffortLevel,
    ImpactLevel,
    ImprovementAction,
    LayerQualityScore,
    QualityAttribute,
    QualityAttributeScore,
    _health_grade,
)
from app.architecture.schemas.solid import (
    ComplianceLevel,
    NormalizedDesignInput,
    SOLIDComplianceReport,
    _INFRA_KEYWORDS,
)
from app.skills.base import SkillCategory
from .base import AgentContext, AgentResult, BaseAgent

if TYPE_CHECKING:
    from app.architecture.context.pipeline_context import PipelineContext
    from app.architecture.schemas.design_patterns import PatternRecommendationReport
    from app.architecture.schemas.solution import SolutionArchitectureDecision
    from app.architecture.schemas.system_design import SystemDesignOutput
    from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_SKILL_NAMES = [
    "quality_assessment.maintainability_assess",
    "quality_assessment.extensibility_assess",
    "quality_assessment.testability_assess",
    "quality_assessment.scalability_assess",
    "quality_assessment.security_boundary_assess",
]

_LAYER_NAMES = ["presentation", "application", "domain", "infrastructure"]


def _extract_violations_and_warnings(
    solid_report: "SOLIDComplianceReport | None",
) -> tuple[list[str], list[str]]:
    if solid_report is None:
        return [], []
    violations = [
        r.principle.value
        for r in solid_report.principle_results
        if r.compliance_level == ComplianceLevel.VIOLATION
    ]
    warnings = [
        r.principle.value
        for r in solid_report.principle_results
        if r.compliance_level == ComplianceLevel.WARNING
    ]
    return violations, warnings


def _extract_pattern_names(
    pattern_report: "PatternRecommendationReport | None",
) -> list[str]:
    if pattern_report is None:
        return []
    return [r.pattern_name for r in pattern_report.recommendations]


def _assess_layer_breakdown(
    inp: NormalizedDesignInput,
    violations: list[str],
    warnings: list[str],
) -> list[LayerQualityScore]:
    layers: list[LayerQualityScore] = []

    # ── Presentation Layer ────────────────────────────────────────────────────
    pres_score = 40.0
    pres_issues: list[str] = []
    pres_strengths: list[str] = []

    if inp.has_gateway:
        pres_score += 30.0
        pres_strengths.append("API gateway provides a single secure entry point.")
    else:
        pres_issues.append("No API gateway detected; security and routing enforcement is scattered.")

    gateway_components = [c for c in inp.components if c.get("type") == "gateway"]
    if gateway_components:
        pres_score += 10.0
        pres_strengths.append(f"{len(gateway_components)} gateway component(s) defined.")
    if "srp" in violations:
        pres_score -= 10.0
        pres_issues.append("SRP violations may indicate mixed concerns at the presentation boundary.")

    pres_score = max(10.0, min(100.0, pres_score))
    layers.append(LayerQualityScore(
        layer="presentation",
        score=round(pres_score, 1),
        issues=pres_issues,
        strengths=pres_strengths,
    ))

    # ── Application Layer ─────────────────────────────────────────────────────
    app_score = 60.0
    app_issues: list[str] = []
    app_strengths: list[str] = []

    app_components = [c for c in inp.components if c.get("layer") == "application"]
    if app_components:
        app_score += 10.0
        app_strengths.append(f"{len(app_components)} application-layer component(s) identified.")

    if "srp" in violations:
        app_score -= 15.0
        app_issues.append("SRP violations in application services reduce cohesion.")
    elif "srp" in warnings:
        app_score -= 7.0
        app_issues.append("SRP warnings suggest potential responsibility creep in use-case services.")

    if "ocp" in violations:
        app_score -= 15.0
        app_issues.append("OCP violations mean use-case changes require modifying existing services.")
    elif "ocp" in warnings:
        app_score -= 7.0

    if not violations and not warnings:
        app_strengths.append("All application-layer SOLID concerns satisfied.")

    app_score = max(10.0, min(100.0, app_score))
    layers.append(LayerQualityScore(
        layer="application",
        score=round(app_score, 1),
        issues=app_issues,
        strengths=app_strengths,
    ))

    # ── Domain Layer ──────────────────────────────────────────────────────────
    dom_score = 60.0
    dom_issues: list[str] = []
    dom_strengths: list[str] = []

    domain_components = [c for c in inp.components if c.get("layer") == "domain"]
    domain_infra_leaks = [
        c for c in domain_components
        if {h.lower() for h in c.get("technology_hints", [])} & _INFRA_KEYWORDS
    ]

    if domain_components and not domain_infra_leaks:
        dom_score += 20.0
        dom_strengths.append("Domain layer is free of infrastructure concerns (clean architecture).")
    elif domain_infra_leaks:
        dom_score -= 20.0
        dom_issues.append(
            f"{len(domain_infra_leaks)} domain component(s) carry infrastructure hints, "
            "violating layer isolation."
        )

    if inp.domain_services:
        dom_score += 10.0
        dom_strengths.append(f"{len(inp.domain_services)} domain service(s) properly encapsulate business logic.")

    if "dip" in violations:
        dom_score -= 15.0
        dom_issues.append("DIP violations mean domain depends on concrete infrastructure implementations.")
    elif "dip" in warnings:
        dom_score -= 7.0

    dom_score = max(10.0, min(100.0, dom_score))
    layers.append(LayerQualityScore(
        layer="domain",
        score=round(dom_score, 1),
        issues=dom_issues,
        strengths=dom_strengths,
    ))

    # ── Infrastructure Layer ──────────────────────────────────────────────────
    infra_score = 50.0
    infra_issues: list[str] = []
    infra_strengths: list[str] = []

    if inp.has_repositories:
        infra_score += 15.0
        infra_strengths.append("Repository pattern abstracts data-access from domain logic.")

    if inp.has_ports_and_adapters:
        infra_score += 20.0
        infra_strengths.append("Ports-and-adapters pattern enables swappable infrastructure implementations.")

    infra_components = [c for c in inp.components if c.get("layer") == "infrastructure"]
    if infra_components:
        infra_score += 5.0
        infra_strengths.append(f"{len(infra_components)} infrastructure component(s) explicitly defined.")

    if inp.has_shared_database:
        infra_score -= 15.0
        infra_issues.append("Shared database couples services at the infrastructure level.")

    if "dip" in violations:
        infra_score -= 10.0
        infra_issues.append("DIP violations suggest missing abstractions at infrastructure boundaries.")

    if not infra_strengths:
        infra_issues.append("No repositories or ports/adapters detected; infrastructure boundaries unclear.")

    infra_score = max(10.0, min(100.0, infra_score))
    layers.append(LayerQualityScore(
        layer="infrastructure",
        score=round(infra_score, 1),
        issues=infra_issues,
        strengths=infra_strengths,
    ))

    return layers


_EFFORT_ORDER = {EffortLevel.LOW: 1, EffortLevel.MEDIUM: 2, EffortLevel.HIGH: 3}
_IMPACT_ORDER = {ImpactLevel.HIGH: 3, ImpactLevel.MEDIUM: 2, ImpactLevel.LOW: 1}


def _build_improvement_actions(
    violations: list[str],
    warnings: list[str],
    inp: NormalizedDesignInput,
    attribute_scores: list[QualityAttributeScore],
) -> list[ImprovementAction]:
    candidates: list[dict[str, Any]] = []

    if "srp" in violations:
        candidates.append({
            "title": "Decompose multi-responsibility components",
            "description": (
                "Extract each distinct responsibility from SRP-violating components into "
                "dedicated, cohesive classes or services with a single reason to change."
            ),
            "affected_attribute": QualityAttribute.MAINTAINABILITY,
            "effort": EffortLevel.MEDIUM,
            "impact": ImpactLevel.HIGH,
        })

    if "ocp" in violations:
        candidates.append({
            "title": "Introduce abstraction layers for extension",
            "description": (
                "Replace direct modifications with Strategy, Template Method, or Decorator patterns "
                "so that new behaviour can be added by extending — not modifying — existing code."
            ),
            "affected_attribute": QualityAttribute.EXTENSIBILITY,
            "effort": EffortLevel.HIGH,
            "impact": ImpactLevel.HIGH,
        })

    if "dip" in violations:
        candidates.append({
            "title": "Apply dependency injection for concrete dependencies",
            "description": (
                "Define interfaces (ports) for all concrete infrastructure dependencies and inject "
                "them at composition root. This enables easy swapping of implementations and test doubles."
            ),
            "affected_attribute": QualityAttribute.TESTABILITY,
            "effort": EffortLevel.MEDIUM,
            "impact": ImpactLevel.HIGH,
        })

    if "isp" in violations:
        candidates.append({
            "title": "Segregate fat interfaces into role-specific contracts",
            "description": (
                "Split large interfaces into smaller, client-specific contracts so that "
                "implementations only expose the methods their callers actually need."
            ),
            "affected_attribute": QualityAttribute.TESTABILITY,
            "effort": EffortLevel.LOW,
            "impact": ImpactLevel.MEDIUM,
        })

    if "lsp" in violations:
        candidates.append({
            "title": "Review and fix inheritance hierarchies",
            "description": (
                "Ensure all subclasses honour the behavioural contract of their base type. "
                "Prefer composition over inheritance where substitutability cannot be guaranteed."
            ),
            "affected_attribute": QualityAttribute.MAINTAINABILITY,
            "effort": EffortLevel.MEDIUM,
            "impact": ImpactLevel.MEDIUM,
        })

    if not inp.has_gateway:
        candidates.append({
            "title": "Introduce an API gateway at the presentation layer",
            "description": (
                "Add a dedicated API gateway to centralise authentication, rate-limiting, "
                "routing, and observability, creating a clear security enforcement boundary."
            ),
            "affected_attribute": QualityAttribute.SECURITY_BOUNDARY_CLARITY,
            "effort": EffortLevel.MEDIUM,
            "impact": ImpactLevel.HIGH,
        })

    if not inp.has_repositories:
        candidates.append({
            "title": "Adopt the Repository pattern for data access",
            "description": (
                "Wrap all data-access logic in repository interfaces and implementations. "
                "This isolates the domain from persistence details and makes tests trivial."
            ),
            "affected_attribute": QualityAttribute.TESTABILITY,
            "effort": EffortLevel.LOW,
            "impact": ImpactLevel.MEDIUM,
        })

    if not inp.has_ports_and_adapters:
        candidates.append({
            "title": "Migrate to ports-and-adapters (Hexagonal) architecture",
            "description": (
                "Define driving and driven ports as interfaces in the application core. "
                "All external systems (HTTP, DB, queues) become adapters, enabling full "
                "isolation of business logic for testing and future infrastructure swaps."
            ),
            "affected_attribute": QualityAttribute.EXTENSIBILITY,
            "effort": EffortLevel.HIGH,
            "impact": ImpactLevel.HIGH,
        })

    if inp.has_shared_database:
        candidates.append({
            "title": "Migrate to database-per-service",
            "description": (
                "Assign each service its own database schema or instance to eliminate the "
                "shared-database scalability bottleneck and enforce data ownership boundaries."
            ),
            "affected_attribute": QualityAttribute.SCALABILITY,
            "effort": EffortLevel.HIGH,
            "impact": ImpactLevel.HIGH,
        })

    if "srp" in warnings or "ocp" in warnings:
        candidates.append({
            "title": "Refactor classes nearing responsibility boundaries",
            "description": (
                "Several components show warning-level SRP/OCP concerns. Schedule refactoring "
                "sessions before they accumulate into full violations."
            ),
            "affected_attribute": QualityAttribute.MAINTAINABILITY,
            "effort": EffortLevel.LOW,
            "impact": ImpactLevel.MEDIUM,
        })

    # rank by impact / effort ratio (higher impact, lower effort → higher priority)
    def _priority(c: dict[str, Any]) -> float:
        return _IMPACT_ORDER[c["impact"]] / _EFFORT_ORDER[c["effort"]]

    ranked = sorted(candidates, key=_priority, reverse=True)[:5]

    return [
        ImprovementAction(
            rank=i + 1,
            title=c["title"],
            description=c["description"],
            affected_attribute=c["affected_attribute"],
            effort=c["effort"],
            impact=c["impact"],
            priority_score=round(_priority(c), 3),
        )
        for i, c in enumerate(ranked)
    ]


class ArchitectureQualityAssessmentAgent(BaseAgent):
    """
    Architecture Quality Assessment Agent — Issue #17.

    Combines SOLID compliance findings, design pattern recommendations, and the
    system architecture design to produce a holistic architecture quality score
    and report across five quality attributes (0–100 each).

    Auto-triggered by WorkflowCoordinator after pattern recommendation completes.
    """

    name = "quality_assessment"
    description = (
        "Architecture Quality Assessment — produces a holistic quality score and report "
        "by combining SOLID compliance findings, design pattern recommendations, and "
        "system architecture design. Scores five quality attributes (0–100): "
        "Maintainability, Extensibility, Testability, Scalability, and Security Boundary Clarity. "
        "Delivers per-layer breakdown, top-5 improvement actions, and an overall health score."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    system_prompt = (
        "You are a senior software architect specialising in architecture quality metrics, "
        "SOLID principles, design patterns, and clean architecture. You evaluate design "
        "artifacts holistically and produce actionable, evidence-based quality assessments."
    )

    async def assess(
        self,
        design: "SolutionArchitectureDecision | SystemDesignOutput | PipelineContext | NormalizedDesignInput",
        solid_report: "SOLIDComplianceReport | None" = None,
        pattern_report: "PatternRecommendationReport | None" = None,
    ) -> ArchitectureQualityReport:
        """
        Main entry point: assess architecture quality holistically.

        Accepts any pipeline design output type. All five quality skills run in
        parallel; results are combined into a single ArchitectureQualityReport.
        """
        inp = self._normalize(design)
        architecture_style = inp.pattern or ""
        violations, warnings = _extract_violations_and_warnings(solid_report)
        pattern_names = _extract_pattern_names(pattern_report)

        input_dict = inp.to_dict()

        raw_results: list[Any] = await asyncio.gather(
            self.execute_skill(
                "quality_assessment.maintainability_assess",
                design_input=input_dict,
                solid_violations=violations,
                solid_warnings=warnings,
            ),
            self.execute_skill(
                "quality_assessment.extensibility_assess",
                design_input=input_dict,
                solid_violations=violations,
                solid_warnings=warnings,
                architecture_style=architecture_style,
                pattern_names=pattern_names,
            ),
            self.execute_skill(
                "quality_assessment.testability_assess",
                design_input=input_dict,
                solid_violations=violations,
                solid_warnings=warnings,
                pattern_names=pattern_names,
            ),
            self.execute_skill(
                "quality_assessment.scalability_assess",
                design_input=input_dict,
                architecture_style=architecture_style,
                pattern_names=pattern_names,
            ),
            self.execute_skill(
                "quality_assessment.security_boundary_assess",
                design_input=input_dict,
                solid_violations=violations,
            ),
            return_exceptions=True,
        )

        attribute_scores: list[QualityAttributeScore] = []
        attributes_order = [
            QualityAttribute.MAINTAINABILITY,
            QualityAttribute.EXTENSIBILITY,
            QualityAttribute.TESTABILITY,
            QualityAttribute.SCALABILITY,
            QualityAttribute.SECURITY_BOUNDARY_CLARITY,
        ]

        for attr, skill_result in zip(attributes_order, raw_results):
            if isinstance(skill_result, Exception):
                logger.warning("Quality skill for %s raised: %s", attr.value, skill_result)
                attribute_scores.append(QualityAttributeScore(
                    attribute=attr,
                    score=50.0,
                    justification=f"Assessment could not complete: {skill_result}",
                ))
                continue

            if skill_result.success and skill_result.artifacts:
                try:
                    data = json.loads(skill_result.artifacts[0].content)
                    attribute_scores.append(QualityAttributeScore(**data))
                except Exception as exc:
                    logger.warning("Failed to parse quality result for %s: %s", attr.value, exc)
                    attribute_scores.append(QualityAttributeScore(
                        attribute=attr,
                        score=50.0,
                        justification="Result parsing failed.",
                    ))
            else:
                attribute_scores.append(QualityAttributeScore(
                    attribute=attr,
                    score=50.0,
                    justification=skill_result.error or "Skill returned no artifacts.",
                ))

        overall_health_score = round(
            sum(
                ATTRIBUTE_WEIGHTS[s.attribute] * s.score
                for s in attribute_scores
            ),
            1,
        )

        layer_breakdown = _assess_layer_breakdown(inp, violations, warnings)
        improvement_actions = _build_improvement_actions(
            violations, warnings, inp, attribute_scores
        )

        grade = _health_grade(overall_health_score)
        violation_note = (
            f" SOLID violations: {', '.join(v.upper() for v in violations)}."
            if violations else " No SOLID violations."
        )
        pattern_note = (
            f" Top patterns: {', '.join(pattern_names[:3])}."
            if pattern_names else ""
        )

        summary = (
            f"Architecture quality assessment complete for '{architecture_style or 'unknown'}' "
            f"architecture. Overall health: {overall_health_score:.1f}/100 ({grade}).{violation_note}"
            f"{pattern_note} {len(improvement_actions)} improvement action(s) identified."
        )

        return ArchitectureQualityReport(
            architecture_pattern=architecture_style,
            attribute_scores=attribute_scores,
            layer_quality_breakdown=layer_breakdown,
            improvement_actions=improvement_actions,
            overall_health_score=overall_health_score,
            health_grade=grade,
            analysis_summary=summary,
        )

    def _normalize(
        self,
        artifact: "SolutionArchitectureDecision | SystemDesignOutput | PipelineContext | NormalizedDesignInput",
    ) -> NormalizedDesignInput:
        from app.architecture.schemas.system_design import SystemDesignOutput
        from app.architecture.schemas.solution import SolutionArchitectureDecision
        from app.architecture.context.pipeline_context import PipelineContext
        from app.agents.solid_agent import (
            _normalize_from_decision,
            _normalize_from_system_design,
            _merge_inputs,
        )

        if isinstance(artifact, NormalizedDesignInput):
            return artifact

        if isinstance(artifact, PipelineContext):
            ctx: PipelineContext = artifact
            decision_inp = (
                _normalize_from_decision(ctx.decision) if ctx.decision else NormalizedDesignInput()
            )
            design_inp = (
                _normalize_from_system_design(ctx.system_design, pattern=decision_inp.pattern)
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
        """Standard BaseAgent interface — wraps assess() for orchestrator dispatch."""
        inp: NormalizedDesignInput = context.metadata.get(
            "design_input", NormalizedDesignInput()
        )
        solid_report = context.metadata.get("solid_compliance_report")
        pattern_report = context.metadata.get("pattern_recommendation_report")

        try:
            report = await self.assess(inp, solid_report=solid_report, pattern_report=pattern_report)
            return AgentResult(
                success=True,
                summary=report.analysis_summary,
                agent_name=self.name,
            )
        except Exception as exc:
            logger.exception("Architecture quality assessment failed")
            return AgentResult(
                success=False,
                summary="Architecture quality assessment failed.",
                agent_name=self.name,
                error=str(exc),
            )
