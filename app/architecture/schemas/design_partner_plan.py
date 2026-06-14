import uuid
from typing import Any

from pydantic import BaseModel, Field


class PartnerDimensionScore(BaseModel):
    dimension: str
    signal_strength: float = Field(ge=0.0, le=1.0)
    aptitude: float = Field(ge=0.0, le=1.0)
    contribution: float = Field(ge=0.0, le=1.0)


class PartnerScore(BaseModel):
    """Fitness evaluation for one design partner produced by the scoring matrix."""
    partner_name: str
    fitness_score: float = Field(ge=0.0, le=1.0)
    dimension_scores: list[PartnerDimensionScore] = Field(default_factory=list)
    selected: bool = False
    rejection_reason: str | None = None


class PartnerConfiguration(BaseModel):
    """Runtime parameters resolved for a design partner before invocation."""
    partner_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class PartnerActivation(BaseModel):
    """A single partner included in the plan, with order and resolved configuration."""
    partner_name: str
    activation_order: int
    configuration: PartnerConfiguration
    rationale: str


class SelectionRationale(BaseModel):
    """Structured explanation of why each partner was selected or rejected."""
    summary: str
    per_partner_scores: list[PartnerScore] = Field(default_factory=list)
    primary_signals: list[str] = Field(default_factory=list)
    hybrid_reason: str | None = None


class DesignPartnerPlan(BaseModel):
    """Output of ArchitecturePatternSelector.select().

    Describes which design partners to activate, in what order, with what
    configuration, and the full scoring rationale for the decision.
    """
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    selected_partners: list[PartnerActivation] = Field(default_factory=list)
    is_hybrid: bool = False
    rationale: SelectionRationale
    scoring_deterministic: bool = True
