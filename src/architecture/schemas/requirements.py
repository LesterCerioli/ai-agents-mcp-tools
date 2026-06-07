from enum import Enum
from pydantic import BaseModel, Field


class SpecificationStatus(str, Enum):
    SPECIFIED = "specified"
    NOT_SPECIFIED = "not_specified"
    AMBIGUOUS = "ambiguous"


class ScalabilityRequirement(BaseModel):
    status: SpecificationStatus = SpecificationStatus.NOT_SPECIFIED
    expected_users: str | None = None
    growth_rate: str | None = None
    peak_load: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AvailabilityRequirement(BaseModel):
    status: SpecificationStatus = SpecificationStatus.NOT_SPECIFIED
    target_uptime: str | None = None
    rto: str | None = None
    rpo: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ComplianceRequirement(BaseModel):
    status: SpecificationStatus = SpecificationStatus.NOT_SPECIFIED
    frameworks: list[str] = Field(default_factory=list)
    data_residency: str | None = None
    audit_trail: bool | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DomainBoundariesRequirement(BaseModel):
    status: SpecificationStatus = SpecificationStatus.NOT_SPECIFIED
    primary_domain: str | None = None
    subdomains: list[str] = Field(default_factory=list)
    bounded_contexts: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class IntegrationRequirement(BaseModel):
    status: SpecificationStatus = SpecificationStatus.NOT_SPECIFIED
    external_systems: list[str] = Field(default_factory=list)
    integration_patterns: list[str] = Field(default_factory=list)
    real_time: bool | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class BudgetConstraint(BaseModel):
    status: SpecificationStatus = SpecificationStatus.NOT_SPECIFIED
    tier: str | None = None
    cloud_preference: str | None = None
    cost_sensitivity: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TeamSizeSignal(BaseModel):
    status: SpecificationStatus = SpecificationStatus.NOT_SPECIFIED
    engineering_team_size: str | None = None
    organizational_maturity: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ArchitectureRequirements(BaseModel):
    raw_input: str
    scalability: ScalabilityRequirement = Field(default_factory=ScalabilityRequirement)
    availability: AvailabilityRequirement = Field(default_factory=AvailabilityRequirement)
    compliance: ComplianceRequirement = Field(default_factory=ComplianceRequirement)
    domain_boundaries: DomainBoundariesRequirement = Field(default_factory=DomainBoundariesRequirement)
    integration: IntegrationRequirement = Field(default_factory=IntegrationRequirement)
    budget: BudgetConstraint = Field(default_factory=BudgetConstraint)
    team_size: TeamSizeSignal = Field(default_factory=TeamSizeSignal)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    clarification_questions: list[str] = Field(default_factory=list)
    is_complete: bool = False

    def dimension_confidences(self) -> dict[str, float]:
        return {
            "scalability": self.scalability.confidence,
            "availability": self.availability.confidence,
            "compliance": self.compliance.confidence,
            "domain_boundaries": self.domain_boundaries.confidence,
            "integration": self.integration.confidence,
            "budget": self.budget.confidence,
            "team_size": self.team_size.confidence,
        }

    def low_confidence_dimensions(self, threshold: float = 0.4) -> list[str]:
        return [dim for dim, score in self.dimension_confidences().items() if score < threshold]
