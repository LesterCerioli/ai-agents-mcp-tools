import uuid
from enum import Enum

from pydantic import BaseModel, Field


class QualityAttribute(str, Enum):
    MAINTAINABILITY = "maintainability"
    EXTENSIBILITY = "extensibility"
    TESTABILITY = "testability"
    SCALABILITY = "scalability"
    SECURITY_BOUNDARY_CLARITY = "security_boundary_clarity"


class EffortLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImpactLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_EFFORT_WEIGHT: dict[EffortLevel, float] = {
    EffortLevel.LOW: 1.0,
    EffortLevel.MEDIUM: 2.0,
    EffortLevel.HIGH: 3.0,
}

_IMPACT_WEIGHT: dict[ImpactLevel, float] = {
    ImpactLevel.LOW: 1.0,
    ImpactLevel.MEDIUM: 2.0,
    ImpactLevel.HIGH: 3.0,
}

ATTRIBUTE_WEIGHTS: dict[QualityAttribute, float] = {
    QualityAttribute.MAINTAINABILITY: 0.25,
    QualityAttribute.EXTENSIBILITY: 0.20,
    QualityAttribute.TESTABILITY: 0.20,
    QualityAttribute.SCALABILITY: 0.20,
    QualityAttribute.SECURITY_BOUNDARY_CLARITY: 0.15,
}


class ImprovementAction(BaseModel):
    rank: int
    title: str
    description: str
    affected_attribute: QualityAttribute
    effort: EffortLevel
    impact: ImpactLevel
    priority_score: float = 0.0


class LayerQualityScore(BaseModel):
    layer: str
    score: float
    issues: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)


class QualityAttributeScore(BaseModel):
    attribute: QualityAttribute
    score: float
    justification: str = ""


def _health_grade(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Needs Improvement"
    return "Critical"


class ArchitectureQualityReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    architecture_pattern: str = ""
    attribute_scores: list[QualityAttributeScore] = Field(default_factory=list)
    layer_quality_breakdown: list[LayerQualityScore] = Field(default_factory=list)
    improvement_actions: list[ImprovementAction] = Field(default_factory=list)
    overall_health_score: float = 0.0
    health_grade: str = ""
    analysis_summary: str = ""

    def get_attribute_score(self, attribute: QualityAttribute) -> float:
        result = next((a for a in self.attribute_scores if a.attribute == attribute), None)
        return result.score if result else 0.0
