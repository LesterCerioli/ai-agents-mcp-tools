import json
from typing import Any

from app.architecture.schemas.quality_assessment import QualityAttribute, QualityAttributeScore
from app.architecture.schemas.solid import NormalizedDesignInput, _INFRA_KEYWORDS
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_BASE_SCORE = 60.0


def _assess_security_boundary_clarity(
    inp: NormalizedDesignInput,
    solid_violations: list[str],
) -> QualityAttributeScore:
    score = _BASE_SCORE
    notes: list[str] = []

    if inp.has_gateway:
        score += 15.0
        notes.append("API gateway defines a clear security enforcement boundary for all entry points.")

    if inp.has_ports_and_adapters:
        score += 10.0
        notes.append(
            "Ports-and-adapters pattern separates the trusted domain core from external adapters."
        )

    domain_clean = not any(
        {h.lower() for h in c.get("technology_hints", [])} & _INFRA_KEYWORDS
        for c in inp.components
        if c.get("layer") == "domain"
    )
    if domain_clean:
        score += 10.0
        notes.append(
            "Domain layer carries no infrastructure technology hints — security concerns "
            "are properly isolated in the infrastructure layer."
        )
    else:
        score -= 10.0
        notes.append(
            "Domain components expose infrastructure technology hints, blurring the "
            "security boundary between domain and infrastructure."
        )

    if inp.has_repositories:
        score += 5.0
        notes.append(
            "Repository pattern centralises data-access logic, making it easier to enforce "
            "access-control policies at a single boundary."
        )

    bounded_context_count = len(inp.bounded_contexts)
    if bounded_context_count > 1:
        score += min(bounded_context_count * 2.0, 8.0)
        notes.append(
            f"{bounded_context_count} bounded contexts define clear ownership and "
            "access-control scopes."
        )

    if "srp" in solid_violations:
        score -= 5.0
        notes.append(
            "SRP violations blur component responsibilities, making it harder to enforce "
            "security policies consistently."
        )

    score = max(10.0, min(100.0, score))

    if not notes:
        notes.append("Security boundaries are clearly defined across all architectural layers.")

    return QualityAttributeScore(
        attribute=QualityAttribute.SECURITY_BOUNDARY_CLARITY,
        score=round(score, 1),
        justification=" | ".join(notes),
    )


@SkillRegistry.register
class SecurityBoundaryAssessSkill(BaseSkill):
    name = "quality_assessment.security_boundary_assess"
    description = (
        "Assesses security boundary clarity (0–100) based on presence of gateways, "
        "ports-and-adapters, clean domain layer, and bounded contexts. "
        "A high score indicates well-defined security enforcement points across all layers."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    tags = ["quality", "security", "boundaries", "architecture"]
    parameters = [
        SkillParameter("design_input", "Serialized NormalizedDesignInput dict.", type="object"),
        SkillParameter("solid_violations", "List of violated SOLID principle ids.", type="array"),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        solid_violations: list[str] | None = None,
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        result = _assess_security_boundary_clarity(inp, solid_violations or [])
        return SkillResult(
            success=True,
            summary=f"Security boundary clarity score: {result.score}",
            artifacts=[
                CodeArtifact(
                    filename="quality_security.json",
                    content=json.dumps(result.model_dump(), indent=2),
                    language="json",
                    description="Security boundary clarity assessment result",
                )
            ],
        )
