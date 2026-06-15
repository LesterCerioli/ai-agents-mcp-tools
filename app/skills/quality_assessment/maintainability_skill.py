import json
from typing import Any

from app.architecture.schemas.quality_assessment import QualityAttribute, QualityAttributeScore
from app.architecture.schemas.solid import NormalizedDesignInput, _INFRA_KEYWORDS
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_BASE_SCORE = 80.0
_VIOLATION_PENALTY = 20.0
_WARNING_PENALTY = 10.0
_MAX_PENALTY_PER_PRINCIPLE = 40.0


def _assess_maintainability(
    inp: NormalizedDesignInput,
    solid_violations: list[str],
    solid_warnings: list[str],
) -> QualityAttributeScore:
    score = _BASE_SCORE
    notes: list[str] = []

    srp_violations = solid_violations.count("srp")
    ocp_violations = solid_violations.count("ocp")
    srp_warnings = solid_warnings.count("srp")
    ocp_warnings = solid_warnings.count("ocp")

    srp_penalty = min(srp_violations * _VIOLATION_PENALTY + srp_warnings * _WARNING_PENALTY,
                      _MAX_PENALTY_PER_PRINCIPLE)
    ocp_penalty = min(ocp_violations * _VIOLATION_PENALTY + ocp_warnings * _WARNING_PENALTY,
                      _MAX_PENALTY_PER_PRINCIPLE)

    score -= srp_penalty + ocp_penalty

    if srp_violations:
        notes.append(f"SRP violated ({srp_violations}x): components have mixed responsibilities.")
    if ocp_violations:
        notes.append(f"OCP violated ({ocp_violations}x): components are not closed for modification.")
    if srp_warnings:
        notes.append(f"SRP warning ({srp_warnings}x): potential responsibility creep detected.")
    if ocp_warnings:
        notes.append(f"OCP warning ({ocp_warnings}x): limited extension points available.")

    domain_infra_violations = sum(
        1 for c in inp.components
        if c.get("layer") == "domain"
        and {h.lower() for h in c.get("technology_hints", [])} & _INFRA_KEYWORDS
    )
    if domain_infra_violations:
        score -= min(domain_infra_violations * 10.0, 20.0)
        notes.append(
            f"{domain_infra_violations} domain component(s) carry infrastructure concerns, "
            "reducing maintainability."
        )

    if inp.has_repositories and inp.has_gateway:
        score += 5.0
        notes.append("Presence of gateway and repositories supports clean layer separation.")

    score = max(10.0, min(100.0, score))

    if not notes:
        notes.append("All maintainability-relevant SOLID principles satisfied.")

    return QualityAttributeScore(
        attribute=QualityAttribute.MAINTAINABILITY,
        score=round(score, 1),
        justification=" | ".join(notes),
    )


@SkillRegistry.register
class MaintainabilityAssessSkill(BaseSkill):
    name = "quality_assessment.maintainability_assess"
    description = (
        "Assesses maintainability quality attribute (0–100) based on SRP and OCP compliance. "
        "A high score indicates components have single, stable responsibilities and are "
        "closed for modification but open for extension."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    tags = ["quality", "maintainability", "srp", "ocp", "architecture"]
    parameters = [
        SkillParameter("design_input", "Serialized NormalizedDesignInput dict.", type="object"),
        SkillParameter("solid_violations", "List of violated SOLID principle ids (e.g. ['srp','ocp']).", type="array"),
        SkillParameter("solid_warnings", "List of warned SOLID principle ids.", type="array"),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        solid_violations: list[str] | None = None,
        solid_warnings: list[str] | None = None,
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        result = _assess_maintainability(
            inp,
            solid_violations or [],
            solid_warnings or [],
        )
        return SkillResult(
            success=True,
            summary=f"Maintainability score: {result.score}",
            artifacts=[
                CodeArtifact(
                    filename="quality_maintainability.json",
                    content=json.dumps(result.model_dump(), indent=2),
                    language="json",
                    description="Maintainability quality assessment result",
                )
            ],
        )
