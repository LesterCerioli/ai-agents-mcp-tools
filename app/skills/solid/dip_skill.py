from typing import Any

from app.architecture.schemas.solid import (
    AffectedComponent,
    ComplianceLevel,
    NormalizedDesignInput,
    PrincipleResult,
    SOLIDPrinciple,
    _INFRA_KEYWORDS,
)
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_DIP_INFRA_RESPONSIBILITY_KEYWORDS: frozenset[str] = frozenset({
    "database", "persistence", "storage", "cache", "queue", "message", "broker",
    "filesystem", "s3", "blob",
})


def _analyze_dip(inp: NormalizedDesignInput) -> PrincipleResult:
    violations: list[AffectedComponent] = []
    recommendations: list[str] = []

    for comp in inp.components:
        name = comp.get("name", "")
        layer = comp.get("layer", "")
        comp_type = comp.get("type", "")
        tech_hints: list[str] = comp.get("technology_hints", [])
        responsibility = comp.get("responsibility", "").lower()

        if layer in ("domain", "application"):
            infra_found = {h.lower() for h in tech_hints} & _INFRA_KEYWORDS
            if infra_found:
                violations.append(AffectedComponent(
                    component_name=name,
                    violation_description=(
                        f"High-level component '{name}' (layer: {layer}) depends directly on "
                        f"low-level infrastructure technologies: {', '.join(sorted(infra_found))}. "
                        "High-level modules must depend on abstractions, not concrete implementations."
                    ),
                    layer=layer,
                    component_type=comp_type,
                ))

            if any(kw in responsibility for kw in _DIP_INFRA_RESPONSIBILITY_KEYWORDS):
                violations.append(AffectedComponent(
                    component_name=name,
                    violation_description=(
                        f"High-level component '{name}' (layer: {layer}) has infrastructure "
                        f"concerns in its responsibility description ('{responsibility[:80]}...'). "
                        "Infrastructure concerns should be abstracted behind ports or repository interfaces."
                    ),
                    layer=layer,
                    component_type=comp_type,
                ))

    if not inp.has_repositories and not inp.has_ports_and_adapters:
        has_domain = any(c.get("layer") == "domain" for c in inp.components)
        has_infra = any(c.get("layer") == "infrastructure" for c in inp.components)
        if has_domain and has_infra:
            violations.append(AffectedComponent(
                component_name="Domain–Infrastructure Boundary",
                violation_description=(
                    "No repository pattern or port abstraction is present between domain and infrastructure layers. "
                    "Domain components likely depend directly on concrete infrastructure implementations."
                ),
                layer="architecture",
                component_type="layer_boundary",
            ))

    if inp.bounded_contexts:
        all_sync = all(
            "sync" in bc.get("communication_style", "").lower()
            for bc in inp.bounded_contexts
        )
        if all_sync and len(inp.bounded_contexts) > 2:
            violations.append(AffectedComponent(
                component_name="Service Communication",
                violation_description=(
                    f"All {len(inp.bounded_contexts)} bounded contexts communicate synchronously (REST/gRPC). "
                    "Synchronous coupling means high-level services depend on the concrete availability "
                    "and implementation details of low-level services. Introduce an event-driven abstraction."
                ),
                layer="service",
                component_type="communication",
            ))

    if violations:
        recommendations += [
            "Introduce repository interfaces in the domain layer; inject concrete implementations at the application boundary.",
            "Domain and application layers must only reference abstractions (interfaces, ports), never concrete infrastructure classes.",
            "Use Dependency Injection to wire concrete implementations at composition-root level.",
            "Consider event-driven communication between bounded contexts to remove runtime coupling.",
        ]
        level = ComplianceLevel.VIOLATION
        summary = (
            f"DIP violated in {len(violations)} area(s). High-level modules must depend on "
            "abstractions, not on low-level concrete implementations."
        )
    else:
        level = ComplianceLevel.COMPLIANT
        summary = "All components satisfy the Dependency Inversion Principle."

    return PrincipleResult(
        principle=SOLIDPrinciple.DIP,
        compliance_level=level,
        affected_components=violations,
        recommendations=recommendations,
        summary=summary,
    )


@SkillRegistry.register
class DIPAnalyzeSkill(BaseSkill):
    name = "solid.dip_analyze"
    description = (
        "Analyzes an architecture design for Dependency Inversion Principle (DIP) compliance. "
        "Detects high-level modules depending on low-level concrete implementations and recommends abstraction injection."
    )
    category = SkillCategory.SOLID
    tags = ["solid", "dip", "dependency-inversion", "architecture", "design-quality"]
    parameters = [
        SkillParameter(
            "design_input",
            "Serialized NormalizedDesignInput dict containing components, modules, and metadata.",
            type="object",
        ),
    ]

    async def execute(self, design_input: dict[str, Any] | None = None, **_: Any) -> SkillResult:
        if design_input is None:
            design_input = {}
        inp = NormalizedDesignInput.from_dict(design_input)
        result = _analyze_dip(inp)
        return SkillResult(
            success=True,
            summary=result.summary,
            artifacts=[
                CodeArtifact(
                    filename="solid_dip_result.json",
                    content=result.model_dump_json(indent=2),
                    language="json",
                    description="DIP compliance analysis result",
                )
            ],
        )
