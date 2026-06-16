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


def _analyze_lsp(inp: NormalizedDesignInput) -> PrincipleResult:
    violations: list[AffectedComponent] = []
    recommendations: list[str] = []

    for port in inp.ports:
        name = port.get("name", "")
        port_type = port.get("port_type", "")
        adapters: list[str] = port.get("adapter_implementations", [])

        if port_type == "driven" and not adapters:
            violations.append(AffectedComponent(
                component_name=name,
                violation_description=(
                    f"Driven port '{name}' declares no adapter implementations. "
                    "Substitutable implementations are required for LSP to be meaningful; "
                    "without at least one concrete adapter, the contract cannot be verified."
                ),
                layer="port",
                component_type="driven_port",
            ))

    protocol_map: dict[str, list[str]] = {}
    for comp in inp.components:
        comp_type = comp.get("type", "")
        if comp_type == "service":
            protocols: list[str] = comp.get("protocols", [])
            for proto in protocols:
                protocol_map.setdefault(proto.lower(), []).append(comp.get("name", ""))

    if inp.bounded_contexts:
        bc_protocols: dict[str, list[str]] = {}
        for bc in inp.bounded_contexts:
            comm = bc.get("communication_style", "").lower()
            bc_protocols.setdefault(comm, []).append(bc.get("name", ""))

        if len(bc_protocols) > 1:
            styles = list(bc_protocols.keys())
            affected = [bc.get("name", "") for bc in inp.bounded_contexts]
            violations.append(AffectedComponent(
                component_name="Bounded Context Communication",
                violation_description=(
                    f"Bounded contexts use inconsistent communication styles "
                    f"({', '.join(styles)}). When services are substituted, callers "
                    "that depend on a uniform communication contract will break."
                ),
                layer="service",
                component_type="bounded_context",
            ))

    if inp.domain_services:
        for ds in inp.domain_services:
            name = ds.get("name", "")
            deps: list[str] = ds.get("dependencies", [])
            if deps:
                infra_deps = [d for d in deps if any(
                    k in d.lower() for k in ("database", "repository", "cache", "queue", "storage")
                )]
                if infra_deps:
                    violations.append(AffectedComponent(
                        component_name=name,
                        violation_description=(
                            f"Domain service '{name}' has explicit dependencies on infrastructure concepts "
                            f"({', '.join(infra_deps)}). If the infrastructure implementation is substituted, "
                            "the domain service's behaviour may change, violating LSP."
                        ),
                        layer="domain",
                        component_type="domain_service",
                    ))

    if violations:
        recommendations += [
            "Every port (abstract interface) must have at least one substitutable adapter implementation.",
            "Ensure all bounded contexts communicate through a consistent protocol contract.",
            "Domain services should depend on abstract port interfaces, not concrete infrastructure names.",
            "Verify that each adapter fully satisfies its port contract without strengthening preconditions or weakening postconditions.",
        ]
        level = ComplianceLevel.VIOLATION
        summary = (
            f"LSP violated in {len(violations)} area(s). Substitutable implementations must honour "
            "the contracts established by their abstract interfaces."
        )
    else:
        level = ComplianceLevel.COMPLIANT
        summary = "All components satisfy the Liskov Substitution Principle."

    return PrincipleResult(
        principle=SOLIDPrinciple.LSP,
        compliance_level=level,
        affected_components=violations,
        recommendations=recommendations,
        summary=summary,
    )


@SkillRegistry.register
class LSPAnalyzeSkill(BaseSkill):
    name = "solid.lsp_analyze"
    description = (
        "Analyzes an architecture design for Liskov Substitution Principle (LSP) compliance. "
        "Detects interface contracts that are violated or overly constrained in derived adapters or implementations."
    )
    category = SkillCategory.SOLID
    tags = ["solid", "lsp", "liskov", "substitution", "architecture", "design-quality"]
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
        result = _analyze_lsp(inp)
        return SkillResult(
            success=True,
            summary=result.summary,
            artifacts=[
                CodeArtifact(
                    filename="solid_lsp_result.json",
                    content=result.model_dump_json(indent=2),
                    language="json",
                    description="LSP compliance analysis result",
                )
            ],
        )
