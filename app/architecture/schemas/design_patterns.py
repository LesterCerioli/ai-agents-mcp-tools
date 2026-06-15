import uuid
from enum import Enum
from pydantic import BaseModel, Field


class PatternCategory(str, Enum):
    CREATIONAL = "creational"
    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    ENTERPRISE = "enterprise"


class GoFPattern(str, Enum):
    # Creational (5)
    ABSTRACT_FACTORY = "abstract_factory"
    BUILDER = "builder"
    FACTORY_METHOD = "factory_method"
    PROTOTYPE = "prototype"
    SINGLETON = "singleton"
    # Structural (7)
    ADAPTER = "adapter"
    BRIDGE = "bridge"
    COMPOSITE = "composite"
    DECORATOR = "decorator"
    FACADE = "facade"
    FLYWEIGHT = "flyweight"
    PROXY = "proxy"
    # Behavioral (11)
    CHAIN_OF_RESPONSIBILITY = "chain_of_responsibility"
    COMMAND = "command"
    INTERPRETER = "interpreter"
    ITERATOR = "iterator"
    MEDIATOR = "mediator"
    MEMENTO = "memento"
    OBSERVER = "observer"
    STATE = "state"
    STRATEGY = "strategy"
    TEMPLATE_METHOD = "template_method"
    VISITOR = "visitor"


class EnterprisePattern(str, Enum):
    REPOSITORY = "repository"
    UNIT_OF_WORK = "unit_of_work"
    CQRS = "cqrs"
    EVENT_SOURCING = "event_sourcing"
    SAGA = "saga"
    OUTBOX = "outbox"
    STRANGLER_FIG = "strangler_fig"
    ANTI_CORRUPTION_LAYER = "anti_corruption_layer"


_CONFLICT_PAIRS: list[tuple[str, str, str]] = [
    (
        "singleton",
        "repository",
        "microservices",
        # reason template filled at conflict-detection time
    ),
    (
        "event_sourcing",
        "unit_of_work",
        "*",
    ),
    (
        "strangler_fig",
        "saga",
        "microservices",
    ),
    (
        "outbox",
        "unit_of_work",
        "monolith",
    ),
]

CONFLICT_RULES: list[dict] = [
    {
        "pattern_a": "singleton",
        "pattern_b": "repository",
        "arch_style": "microservices",
        "reason": (
            "Singleton breaks horizontal scalability in microservices. "
            "Use dependency injection with scoped lifetimes instead of global singletons."
        ),
    },
    {
        "pattern_a": "event_sourcing",
        "pattern_b": "unit_of_work",
        "arch_style": "*",
        "reason": (
            "Event Sourcing replaces the traditional Unit of Work pattern. "
            "They use incompatible persistence models: event log vs. transactional snapshot. "
            "Choose one data strategy."
        ),
    },
    {
        "pattern_a": "strangler_fig",
        "pattern_b": "cqrs",
        "arch_style": "microservices",
        "reason": (
            "Strangler Fig is a migration pattern for incrementally replacing a monolith. "
            "Recommending it alongside CQRS for a greenfield microservices design is contradictory; "
            "apply Strangler Fig only when migrating an existing system."
        ),
    },
    {
        "pattern_a": "outbox",
        "pattern_b": "unit_of_work",
        "arch_style": "monolith",
        "reason": (
            "The Outbox pattern targets reliable async event publishing in distributed systems. "
            "Combining it with Unit of Work in a monolith adds unnecessary complexity; "
            "use simple transactional event publishing instead."
        ),
    },
]


class PatternRecommendation(BaseModel):
    rank: int
    pattern_name: str
    category: PatternCategory
    target_components: list[str] = Field(default_factory=list)
    problem_solved: str
    implementation_sketch: str
    solid_principles_reinforced: list[str] = Field(default_factory=list)
    rationale: str = ""
    score: float = 0.0


class PatternConflict(BaseModel):
    pattern_a: str
    pattern_b: str
    target_component: str
    reason: str


class PatternRecommendationReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recommendations: list[PatternRecommendation] = Field(default_factory=list)
    conflicts: list[PatternConflict] = Field(default_factory=list)
    total_patterns_evaluated: int = 0
    architecture_style: str = ""
    solid_violations_addressed: int = 0
    analysis_summary: str = ""

    def get_recommendation(self, pattern_name: str) -> "PatternRecommendation | None":
        return next(
            (r for r in self.recommendations if r.pattern_name == pattern_name), None
        )
