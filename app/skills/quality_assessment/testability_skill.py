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

_DI_PATTERNS: frozenset[str] = frozenset({
    "abstract_factory", "factory_method", "strategy", "proxy",
})


def _assess_testability(
    inp: NormalizedDesignInput,
    solid_violations: list[str],
    solid_warnings: list[str],
    pattern_names: list[str],
) -> QualityAttributeScore:
    score = _BASE_SCORE
    notes: list[str] = []

    isp_violations = solid_violations.count("isp")
    dip_violations = solid_violations.count("dip")
    isp_warnings = solid_warnings.count("isp")
    dip_warnings = solid_warnings.count("dip")

    isp_penalty = min(isp_violations * _VIOLATION_PENALTY + isp_warnings * _WARNING_PENALTY,
                      _MAX_PENALTY_PER_PRINCIPLE)
    dip_penalty = min(dip_violations * _VIOLATION_PENALTY + dip_warnings * _WARNING_PENALTY,
                      _MAX_PENALTY_PER_PRINCIPLE)

    score -= isp_penalty + dip_penalty

    if isp_violations:
        notes.append(
            f"ISP violated ({isp_violations}x): fat interfaces force test doubles to implement "
            "unnecessary methods, increasing test complexity."
        )
    if dip_violations:
        notes.append(
            f"DIP violated ({dip_violations}x): concrete dependencies cannot be substituted "
            "with test doubles."
        )
    if isp_warnings:
        notes.append(f"ISP warning ({isp_warnings}x): some interface segregation opportunities exist.")
    if dip_warnings:
        notes.append(f"DIP warning ({dip_warnings}x): some concrete dependencies detected.")

    if inp.has_ports_and_adapters:
        score += 10.0
        notes.append(
            "Ports-and-adapters architecture enables port-level test isolation without real adapters."
        )

    if inp.has_repositories:
        score += 5.0
        notes.append("Repository pattern allows in-memory or mock repository substitution in tests.")

    di_patterns = {p.lower() for p in pattern_names} & _DI_PATTERNS
    if di_patterns:
        bonus = min(len(di_patterns) * 3.0, 9.0)
        score += bonus
        notes.append(
            f"DI-friendly patterns present: {', '.join(sorted(di_patterns))} — facilitate mocking."
        )

    score = max(10.0, min(100.0, score))

    if not notes:
        notes.append("Testability-relevant SOLID principles fully satisfied.")

    return QualityAttributeScore(
        attribute=QualityAttribute.TESTABILITY,
        score=round(score, 1),
        justification=" | ".join(notes),
    )


@SkillRegistry.register
class TestabilityAssessSkill(BaseSkill):
    name = "quality_assessment.testability_assess"
    description = (
        "Assesses testability quality attribute (0–100) based on ISP and DIP compliance. "
        "A high score indicates the architecture supports isolated, dependency-injected tests "
        "with focused interfaces."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    tags = ["quality", "testability", "isp", "dip", "architecture"]
    parameters = [
        SkillParameter("design_input", "Serialized NormalizedDesignInput dict.", type="object"),
        SkillParameter("solid_violations", "List of violated SOLID principle ids.", type="array"),
        SkillParameter("solid_warnings", "List of warned SOLID principle ids.", type="array"),
        SkillParameter("pattern_names", "List of recommended design pattern names.", type="array", required=False),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        solid_violations: list[str] | None = None,
        solid_warnings: list[str] | None = None,
        pattern_names: list[str] | None = None,
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        result = _assess_testability(
            inp,
            solid_violations or [],
            solid_warnings or [],
            pattern_names or [],
        )
        return SkillResult(
            success=True,
            summary=f"Testability score: {result.score}",
            artifacts=[
                CodeArtifact(
                    filename="quality_testability.json",
                    content=json.dumps(result.model_dump(), indent=2),
                    language="json",
                    description="Testability quality assessment result",
                )
            ],
        )
