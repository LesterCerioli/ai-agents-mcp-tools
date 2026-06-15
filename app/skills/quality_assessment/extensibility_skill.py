import json
from typing import Any

from app.architecture.schemas.quality_assessment import QualityAttribute, QualityAttributeScore
from app.architecture.schemas.solid import NormalizedDesignInput
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_BASE_SCORE = 80.0
_VIOLATION_PENALTY = 20.0
_WARNING_PENALTY = 10.0
_MAX_PENALTY_PER_PRINCIPLE = 40.0

_EXTENSIBILITY_PATTERNS: frozenset[str] = frozenset({
    "strategy", "decorator", "observer", "abstract_factory", "factory_method", "bridge",
})


def _assess_extensibility(
    inp: NormalizedDesignInput,
    solid_violations: list[str],
    solid_warnings: list[str],
    architecture_style: str,
    pattern_names: list[str],
) -> QualityAttributeScore:
    score = _BASE_SCORE
    notes: list[str] = []

    ocp_violations = solid_violations.count("ocp")
    dip_violations = solid_violations.count("dip")
    ocp_warnings = solid_warnings.count("ocp")
    dip_warnings = solid_warnings.count("dip")

    ocp_penalty = min(ocp_violations * _VIOLATION_PENALTY + ocp_warnings * _WARNING_PENALTY,
                      _MAX_PENALTY_PER_PRINCIPLE)
    dip_penalty = min(dip_violations * _VIOLATION_PENALTY + dip_warnings * _WARNING_PENALTY,
                      _MAX_PENALTY_PER_PRINCIPLE)

    score -= ocp_penalty + dip_penalty

    if ocp_violations:
        notes.append(f"OCP violated ({ocp_violations}x): direct modification required for new behaviours.")
    if dip_violations:
        notes.append(f"DIP violated ({dip_violations}x): high-level modules depend on concrete implementations.")
    if ocp_warnings:
        notes.append(f"OCP warning ({ocp_warnings}x): limited abstraction coverage detected.")
    if dip_warnings:
        notes.append(f"DIP warning ({dip_warnings}x): some concrete dependencies detected.")

    style = architecture_style.lower()
    if style in ("hexagonal", "microservices"):
        score += 5.0
        notes.append(f"'{style}' architecture style naturally supports extension points.")

    if inp.has_ports_and_adapters:
        score += 5.0
        notes.append("Ports-and-adapters design enables pluggable implementations.")

    ext_patterns = {p.lower() for p in pattern_names} & _EXTENSIBILITY_PATTERNS
    if ext_patterns:
        bonus = min(len(ext_patterns) * 3.0, 10.0)
        score += bonus
        notes.append(
            f"Extensibility-friendly patterns recommended: {', '.join(sorted(ext_patterns))}."
        )

    score = max(10.0, min(100.0, score))

    if not notes:
        notes.append("Extensibility-relevant SOLID principles fully satisfied.")

    return QualityAttributeScore(
        attribute=QualityAttribute.EXTENSIBILITY,
        score=round(score, 1),
        justification=" | ".join(notes),
    )


@SkillRegistry.register
class ExtensibilityAssessSkill(BaseSkill):
    name = "quality_assessment.extensibility_assess"
    description = (
        "Assesses extensibility quality attribute (0–100) based on OCP and DIP compliance. "
        "A high score indicates the architecture supports new behaviours without modifying "
        "existing components and depends on abstractions."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    tags = ["quality", "extensibility", "ocp", "dip", "architecture"]
    parameters = [
        SkillParameter("design_input", "Serialized NormalizedDesignInput dict.", type="object"),
        SkillParameter("solid_violations", "List of violated SOLID principle ids.", type="array"),
        SkillParameter("solid_warnings", "List of warned SOLID principle ids.", type="array"),
        SkillParameter("architecture_style", "Architecture style (microservices, hexagonal, monolith).", type="string", required=False),
        SkillParameter("pattern_names", "List of recommended design pattern names.", type="array", required=False),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        solid_violations: list[str] | None = None,
        solid_warnings: list[str] | None = None,
        architecture_style: str = "",
        pattern_names: list[str] | None = None,
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        result = _assess_extensibility(
            inp,
            solid_violations or [],
            solid_warnings or [],
            architecture_style,
            pattern_names or [],
        )
        return SkillResult(
            success=True,
            summary=f"Extensibility score: {result.score}",
            artifacts=[
                CodeArtifact(
                    filename="quality_extensibility.json",
                    content=json.dumps(result.model_dump(), indent=2),
                    language="json",
                    description="Extensibility quality assessment result",
                )
            ],
        )
