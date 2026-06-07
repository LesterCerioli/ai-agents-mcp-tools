import uuid
from enum import Enum

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    GATEWAY = "gateway"
    EXTERNAL = "external"
    CLIENT = "client"
    STORAGE = "storage"


class ArchitectureLayer(str, Enum):
    PRESENTATION = "presentation"
    APPLICATION = "application"
    DOMAIN = "domain"
    INFRASTRUCTURE = "infrastructure"


class ArchitecturePattern(str, Enum):
    MICROSERVICES = "microservices"
    MONOLITH = "monolith"
    SERVERLESS = "serverless"
    EVENT_DRIVEN = "event_driven"
    LAYERED = "layered"
    CQRS = "cqrs"
    HEXAGONAL = "hexagonal"


class TradeOffRating(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TradeOffMatrix(BaseModel):
    """Rates a pattern across five quality attributes. Higher = better for the attribute."""
    scalability: TradeOffRating
    consistency: TradeOffRating
    operational_complexity: TradeOffRating  # HIGH = complex (negative)
    time_to_market: TradeOffRating          # HIGH = fast
    cost: TradeOffRating                    # HIGH = expensive (negative)


class ArchitecturalDriver(BaseModel):
    driver: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    source_dimension: str


class RiskFactor(BaseModel):
    risk: str
    severity: str  # low | medium | high
    mitigation: str


class DecisionComponent(BaseModel):
    name: str
    type: ComponentType
    layer: ArchitectureLayer
    responsibility: str
    technology_hints: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)


class SolutionPattern(BaseModel):
    pattern: ArchitecturePattern
    rationale: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    trade_offs: list[str] = Field(default_factory=list)
    trade_off_matrix: TradeOffMatrix | None = None
    is_primary: bool = False


class SolutionArchitectureDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: str
    patterns: list[SolutionPattern]
    components: list[DecisionComponent]
    external_integrations: list[str] = Field(default_factory=list)
    rationale: str = ""
    architectural_drivers: list[ArchitecturalDriver] = Field(default_factory=list)
    risk_factors: list[RiskFactor] = Field(default_factory=list)
    decision_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    is_rule_based: bool = True

    @property
    def primary_pattern(self) -> SolutionPattern | None:
        return next((p for p in self.patterns if p.is_primary), self.patterns[0] if self.patterns else None)

    @property
    def alternative_patterns(self) -> list[SolutionPattern]:
        return [p for p in self.patterns if not p.is_primary]


class DiagramNode(BaseModel):
    id: str
    label: str
    type: ComponentType
    layer: ArchitectureLayer
    responsibility: str
    technology_hints: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)


class DiagramEdge(BaseModel):
    source_id: str
    target_id: str
    label: str
    protocol: str = ""


class DiagramView(BaseModel):
    mermaid: str
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]


class SolutionFlowDiagram(BaseModel):
    diagram_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    context_view: DiagramView
    container_view: DiagramView
    component_view: DiagramView
    annotations: list[str] = Field(default_factory=list)
