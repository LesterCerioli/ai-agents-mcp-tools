from typing import Any

from app.architecture.schemas.solid import (
    AffectedComponent,
    ComplianceLevel,
    NormalizedDesignInput,
    PrincipleResult,
    SOLIDPrinciple,
)
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_ISP_GATEWAY_CONTEXT_THRESHOLD = 4
_ISP_MODULE_RESPONSIBILITY_THRESHOLD = 4


def _analyze_isp(inp: NormalizedDesignInput) -> PrincipleResult:
    violations: list[AffectedComponent] = []
    recommendations: list[str] = []

    gateway_components = [
        c for c in inp.components
        if c.get("type", "").lower() == "gateway"
    ]
    for gw in gateway_components:
        name = gw.get("name", "")
        if inp.service_count > _ISP_GATEWAY_CONTEXT_THRESHOLD:
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"API Gateway '{name}' routes traffic to {inp.service_count} services. "
                    f"A single gateway acting as a universal interface for more than "
                    f"{_ISP_GATEWAY_CONTEXT_THRESHOLD} heterogeneous services forces every client "
                    "to be aware of unrelated service capabilities (fat interface)."
                ),
                layer=gw.get("layer", "application"),
                component_type="gateway",
            ))

    if inp.has_shared_database:
        violations.append(AffectedComponent(
            component_name="Shared Database",
            violation_description=(
                "A shared database forces all services to depend on the full data schema, "
                "exposing each service to models it does not own. This is the ISP violation "
                "at the data-contract level — services cannot consume only what they need."
            ),
            layer="infrastructure",
            component_type="database",
        ))

    for module in inp.modules:
        name = module.get("name", "")
        responsibilities: list[str] = module.get("responsibilities", [])
        if len(responsibilities) > _ISP_MODULE_RESPONSIBILITY_THRESHOLD:
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"Module '{name}' exposes {len(responsibilities)} responsibilities to its clients "
                    f"({'; '.join(responsibilities[:3])}...). Clients that need only a subset are forced "
                    "to depend on the full interface."
                ),
                layer="module",
                component_type="module",
            ))

    ext_count = sum(
        1 for c in inp.components
        if c.get("type", "").lower() == "external"
    )
    if ext_count > 1:
        external_adapters = [
            c for c in inp.components if c.get("type", "").lower() == "external"
        ]
        if len(external_adapters) > 1:
            adapter_names = [c.get("name", "") for c in external_adapters]
            violations.append(AffectedComponent(
                component_name="External Integration Layer",
                violation_description=(
                    f"Multiple external systems ({', '.join(adapter_names[:3])}) are represented "
                    "by a single integration layer. Clients integrating with one external system "
                    "must accept the full interface including all other external dependencies."
                ),
                layer="infrastructure",
                component_type="external",
            ))

    if violations:
        recommendations += [
            "Split fat interfaces into role-specific interfaces so clients depend only on what they use.",
            "Replace a single monolithic gateway with Backend-for-Frontend (BFF) gateways per client type.",
            "Use Database-per-Service pattern to eliminate shared schema dependencies.",
            "Decompose large module interfaces into smaller, cohesive port contracts.",
        ]
        level = ComplianceLevel.VIOLATION
        summary = (
            f"ISP violated in {len(violations)} area(s). Clients must not be forced to depend "
            "on interfaces they do not use."
        )
    else:
        level = ComplianceLevel.COMPLIANT
        summary = "All components satisfy the Interface Segregation Principle."

    return PrincipleResult(
        principle=SOLIDPrinciple.ISP,
        compliance_level=level,
        affected_components=violations,
        recommendations=recommendations,
        summary=summary,
    )


@SkillRegistry.register
class ISPAnalyzeSkill(BaseSkill):
    name = "solid.isp_analyze"
    description = (
        "Analyzes an architecture design for Interface Segregation Principle (ISP) compliance. "
        "Flags fat interfaces with methods unused by all clients and recommends interface segregation."
    )
    category = SkillCategory.SOLID
    tags = ["solid", "isp", "interface-segregation", "architecture", "design-quality"]
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
        result = _analyze_isp(inp)
        return SkillResult(
            success=True,
            summary=result.summary,
            artifacts=[
                CodeArtifact(
                    filename="solid_isp_result.json",
                    content=result.model_dump_json(indent=2),
                    language="json",
                    description="ISP compliance analysis result",
                )
            ],
        )
