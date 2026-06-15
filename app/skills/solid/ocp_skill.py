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


def _analyze_ocp(inp: NormalizedDesignInput) -> PrincipleResult:
    violations: list[AffectedComponent] = []
    recommendations: list[str] = []
    pattern = inp.pattern.lower()

    if pattern in ("hexagonal",) and not inp.has_ports_and_adapters and not inp.ports:
        violations.append(AffectedComponent(
            component_name="Hexagonal Architecture",
            violation_description=(
                "The design declares a hexagonal architecture pattern but defines no Ports or Adapters. "
                "Without ports, the domain cannot be extended with new adapters; every change requires "
                "modifying core domain logic (closed to extension, not closed to modification)."
            ),
            layer="architecture",
            component_type="pattern",
        ))
        recommendations.append(
            "Define driving ports (e.g., REST, gRPC, CLI) and driven ports (e.g., repository, message bus) "
            "as abstract interfaces in the domain layer."
        )

    if not inp.has_gateway and inp.service_count > 2:
        violations.append(AffectedComponent(
            component_name="API Layer",
            violation_description=(
                f"No API Gateway is present despite {inp.service_count} services. "
                "Without a gateway abstraction, adding new clients or cross-cutting features (auth, rate-limiting) "
                "requires modifying each service individually."
            ),
            layer="application",
            component_type="gateway",
        ))
        recommendations.append(
            "Introduce an API Gateway to centralise cross-cutting concerns, "
            "allowing new client types to be added without touching existing services."
        )

    for comp in inp.components:
        name = comp.get("name", "")
        layer = comp.get("layer", "")
        comp_type = comp.get("type", "")
        tech_hints: list[str] = comp.get("technology_hints", [])
        protocols: list[str] = comp.get("protocols", [])

        if comp_type == "service" and layer == "domain" and not protocols:
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"Domain service '{name}' declares no communication protocol. "
                    "Without a well-defined interface contract, the service cannot be extended "
                    "via new protocol adapters without modifying its internals."
                ),
                layer=layer,
                component_type=comp_type,
            ))

    for port in inp.ports:
        name = port.get("name", "")
        adapters: list[str] = port.get("adapter_implementations", [])
        if not adapters:
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"Port '{name}' has no adapter implementations registered. "
                    "A port without at least one concrete adapter is an unimplemented extension point."
                ),
                layer="port",
                component_type="port",
            ))

    if violations:
        if not recommendations:
            recommendations = [
                "Design to abstractions (interfaces/ports) rather than concrete implementations.",
                "Use the Adapter pattern to add new implementations without changing existing code.",
                "Identify stable abstractions (what) and vary implementations (how).",
            ]
        level = ComplianceLevel.VIOLATION
        summary = (
            f"OCP violated in {len(violations)} area(s). Components must be open for extension "
            "but closed for modification."
        )
    else:
        level = ComplianceLevel.COMPLIANT
        summary = "All components satisfy the Open/Closed Principle."

    return PrincipleResult(
        principle=SOLIDPrinciple.OCP,
        compliance_level=level,
        affected_components=violations,
        recommendations=recommendations,
        summary=summary,
    )


@SkillRegistry.register
class OCPAnalyzeSkill(BaseSkill):
    name = "solid.ocp_analyze"
    description = (
        "Analyzes an architecture design for Open/Closed Principle (OCP) compliance. "
        "Identifies missing extension points and components that are closed to extension without modification."
    )
    category = SkillCategory.SOLID
    tags = ["solid", "ocp", "open-closed", "architecture", "design-quality"]
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
        result = _analyze_ocp(inp)
        return SkillResult(
            success=True,
            summary=result.summary,
            artifacts=[
                CodeArtifact(
                    filename="solid_ocp_result.json",
                    content=result.model_dump_json(indent=2),
                    language="json",
                    description="OCP compliance analysis result",
                )
            ],
        )
