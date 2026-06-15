import json
from typing import Any

from app.architecture.schemas.quality_assessment import QualityAttribute, QualityAttributeScore
from app.architecture.schemas.solid import NormalizedDesignInput
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_BASE_SCORE_BY_STYLE: dict[str, float] = {
    "microservices": 75.0,
    "hexagonal": 65.0,
    "monolith": 55.0,
}

_SCALABILITY_PATTERNS: frozenset[str] = frozenset({
    "cqrs", "event_sourcing", "saga", "outbox", "observer",
})

_HIGH_IMPACT_SCALABILITY: frozenset[str] = frozenset({"cqrs", "event_sourcing"})
_MEDIUM_IMPACT_SCALABILITY: frozenset[str] = frozenset({"saga", "outbox", "observer"})


def _assess_scalability(
    inp: NormalizedDesignInput,
    architecture_style: str,
    pattern_names: list[str],
) -> QualityAttributeScore:
    style = architecture_style.lower()
    score = _BASE_SCORE_BY_STYLE.get(style, 60.0)
    notes: list[str] = [f"Base scalability for '{style or 'unknown'}' architecture: {score}."]

    if inp.has_gateway:
        score += 10.0
        notes.append("API gateway enables load balancing and horizontal scaling.")

    if inp.service_count > 3:
        score += 5.0
        notes.append(f"{inp.service_count} services allow independent scaling per workload.")

    if inp.has_shared_database:
        score -= 15.0
        notes.append(
            "Shared database is a scalability bottleneck; consider database-per-service."
        )

    patterns_lower = {p.lower() for p in pattern_names}
    high_impact = patterns_lower & _HIGH_IMPACT_SCALABILITY
    medium_impact = patterns_lower & _MEDIUM_IMPACT_SCALABILITY

    if high_impact:
        bonus = min(len(high_impact) * 6.0, 12.0)
        score += bonus
        notes.append(f"High-impact scalability patterns: {', '.join(sorted(high_impact))}.")

    if medium_impact:
        bonus = min(len(medium_impact) * 4.0, 8.0)
        score += bonus
        notes.append(f"Medium-impact scalability patterns: {', '.join(sorted(medium_impact))}.")

    score = max(10.0, min(100.0, score))

    return QualityAttributeScore(
        attribute=QualityAttribute.SCALABILITY,
        score=round(score, 1),
        justification=" | ".join(notes),
    )


@SkillRegistry.register
class ScalabilityAssessSkill(BaseSkill):
    name = "quality_assessment.scalability_assess"
    description = (
        "Assesses scalability quality attribute (0–100) based on the chosen architecture style "
        "and recommended patterns. Microservices with CQRS/event-driven patterns score highest; "
        "monoliths with a shared database score lowest."
    )
    category = SkillCategory.QUALITY_ASSESSMENT
    tags = ["quality", "scalability", "architecture", "patterns"]
    parameters = [
        SkillParameter("design_input", "Serialized NormalizedDesignInput dict.", type="object"),
        SkillParameter("architecture_style", "Architecture style (microservices, hexagonal, monolith).", type="string", required=False),
        SkillParameter("pattern_names", "List of recommended design pattern names.", type="array", required=False),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        architecture_style: str = "",
        pattern_names: list[str] | None = None,
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        result = _assess_scalability(inp, architecture_style, pattern_names or [])
        return SkillResult(
            success=True,
            summary=f"Scalability score: {result.score}",
            artifacts=[
                CodeArtifact(
                    filename="quality_scalability.json",
                    content=json.dumps(result.model_dump(), indent=2),
                    language="json",
                    description="Scalability quality assessment result",
                )
            ],
        )
