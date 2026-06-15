import json
from typing import Any

from app.architecture.schemas.solid import (
    AffectedComponent,
    ComplianceLevel,
    NormalizedDesignInput,
    PrincipleResult,
    SOLIDPrinciple,
    _INFRA_KEYWORDS,
    _MULTI_RESPONSIBILITY_INDICATORS,
)
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


def _analyze_srp(inp: NormalizedDesignInput) -> PrincipleResult:
    violations: list[AffectedComponent] = []
    recommendations: list[str] = []

    for comp in inp.components:
        name = comp.get("name", "")
        layer = comp.get("layer", "")
        responsibility = comp.get("responsibility", "").lower()
        tech_hints: list[str] = comp.get("technology_hints", [])
        comp_type = comp.get("type", "")

        if any(ind in responsibility for ind in _MULTI_RESPONSIBILITY_INDICATORS):
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"'{name}' describes multiple responsibilities in a single statement. "
                    "A component should have exactly one reason to change."
                ),
                layer=layer,
                component_type=comp_type,
            ))

        if layer == "domain":
            infra_found = {h.lower() for h in tech_hints} & _INFRA_KEYWORDS
            if infra_found:
                violations.append(AffectedComponent(
                    component_name=name,
                    violation_description=(
                        f"Domain component '{name}' declares infrastructure technology hints "
                        f"({', '.join(sorted(infra_found))}). Domain components should not carry "
                        "infrastructure concerns."
                    ),
                    layer=layer,
                    component_type=comp_type,
                ))

        if len(tech_hints) > 4:
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"Component '{name}' references {len(tech_hints)} distinct technologies "
                    f"({', '.join(tech_hints[:4])}, ...). Excessive technology breadth suggests "
                    "multiple cross-cutting concerns in a single component."
                ),
                layer=layer,
                component_type=comp_type,
            ))

    for module in inp.modules:
        name = module.get("name", "")
        responsibilities: list[str] = module.get("responsibilities", [])
        if len(responsibilities) > 3:
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"Module '{name}' lists {len(responsibilities)} responsibilities "
                    f"({'; '.join(responsibilities[:3])}...). A module should encapsulate "
                    "a single cohesive concern."
                ),
                layer="module",
                component_type="module",
            ))

    services_by_type: dict[str, list[str]] = {}
    for bc in inp.bounded_contexts:
        svc_name = bc.get("service_name", "").lower()
        ctx_name = bc.get("name", "")
        if svc_name:
            services_by_type.setdefault(svc_name, []).append(ctx_name)
    for svc, contexts in services_by_type.items():
        if len(contexts) > 1:
            violations.append(AffectedComponent(
                component_name=svc,
                violation_description=(
                    f"Service '{svc}' is referenced by multiple bounded contexts "
                    f"({', '.join(contexts)}). This centralises unrelated responsibilities."
                ),
                layer="service",
                component_type="service",
            ))

    if violations:
        recommendations += [
            "Extract each distinct responsibility into a dedicated component or service.",
            "Remove infrastructure concerns from domain-layer components; use repository or port abstractions instead.",
            "Apply the Interface Segregation Principle alongside SRP to keep interfaces focused.",
            "Limit module responsibilities to a maximum of three cohesive concerns.",
        ]
        level = ComplianceLevel.VIOLATION
        summary = f"SRP violated in {len(violations)} component(s). Each component must have a single reason to change."
    else:
        level = ComplianceLevel.COMPLIANT
        summary = "All components satisfy the Single Responsibility Principle."

    return PrincipleResult(
        principle=SOLIDPrinciple.SRP,
        compliance_level=level,
        affected_components=violations,
        recommendations=recommendations,
        summary=summary,
    )


@SkillRegistry.register
class SRPAnalyzeSkill(BaseSkill):
    name = "solid.srp_analyze"
    description = (
        "Analyzes an architecture design for Single Responsibility Principle (SRP) compliance. "
        "Flags components, modules, or services that carry more than one primary responsibility."
    )
    category = SkillCategory.SOLID
    tags = ["solid", "srp", "single-responsibility", "architecture", "design-quality"]
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
        result = _analyze_srp(inp)
        return SkillResult(
            success=True,
            summary=result.summary,
            artifacts=[
                CodeArtifact(
                    filename="solid_srp_result.json",
                    content=result.model_dump_json(indent=2),
                    language="json",
                    description="SRP compliance analysis result",
                )
            ],
        )
