import json
from dataclasses import dataclass, field
from typing import Any

from app.architecture.schemas.design_patterns import PatternCategory
from app.architecture.schemas.solid import NormalizedDesignInput
from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@dataclass
class _PatternCandidate:
    pattern_name: str
    category: PatternCategory
    target_components: list[str]
    problem_solved: str
    implementation_sketch: str
    solid_principles_reinforced: list[str]
    rationale: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "category": self.category.value,
            "target_components": self.target_components,
            "problem_solved": self.problem_solved,
            "implementation_sketch": self.implementation_sketch,
            "solid_principles_reinforced": self.solid_principles_reinforced,
            "rationale": self.rationale,
            "score": self.score,
        }


def _analyze_creational(
    inp: NormalizedDesignInput,
    solid_violations: list[str],
    architecture_style: str,
) -> list[_PatternCandidate]:
    candidates: list[_PatternCandidate] = []
    style = architecture_style.lower()
    is_microservices = style == "microservices"
    is_hexagonal = style in ("hexagonal", "hexagonal_architecture")
    is_monolith = style in ("monolith", "layered")
    ocp_violated = "ocp" in solid_violations
    dip_violated = "dip" in solid_violations
    srp_violated = "srp" in solid_violations

    all_components = (
        [c.get("name", "") for c in inp.components]
        + [m.get("name", "") for m in inp.modules]
        + [bc.get("name", "") for bc in inp.bounded_contexts]
    )
    component_count = len(all_components)
    service_names = [c.get("name", "") for c in inp.components if c.get("type") == "service"]

    # Factory Method
    fm_score = 2.0
    if ocp_violated:
        fm_score += 2.5
    if dip_violated:
        fm_score += 1.5
    if is_hexagonal:
        fm_score += 1.5
    if is_microservices:
        fm_score += 0.5
    candidates.append(_PatternCandidate(
        pattern_name="factory_method",
        category=PatternCategory.CREATIONAL,
        target_components=service_names[:3] or all_components[:2],
        problem_solved=(
            "Object creation logic is scattered or concrete classes are hardcoded, "
            "violating OCP and DIP — callers depend on concretions instead of abstractions."
        ),
        implementation_sketch=(
            "interface IServiceFactory:\n"
            "    def create(kind: str) -> IService\n\n"
            "class ConcreteServiceFactory(IServiceFactory):\n"
            "    def create(kind: str) -> IService:\n"
            "        match kind:\n"
            "            case 'payment': return PaymentService()\n"
            "            case 'notification': return NotificationService()\n"
            "            case _: raise ValueError(f'Unknown service: {kind}')"
        ),
        solid_principles_reinforced=["OCP", "DIP"],
        rationale=(
            "Factory Method decouples client code from concrete instantiation, "
            "enabling extension without modification. "
            + ("OCP and " if ocp_violated else "")
            + ("DIP violations make this pattern high priority." if dip_violated else "this pattern improves extensibility.")
        ),
        score=fm_score,
    ))

    # Abstract Factory
    af_score = 1.5
    if inp.has_ports_and_adapters:
        af_score += 2.5
    if len(inp.bounded_contexts) > 1:
        af_score += 1.5
    if is_hexagonal:
        af_score += 2.0
    if dip_violated:
        af_score += 1.0
    driving_ports = [p for p in inp.ports if p.get("port_type") == "driving"]
    driven_ports = [p for p in inp.ports if p.get("port_type") == "driven"]
    if driving_ports and driven_ports:
        af_score += 1.5
    candidates.append(_PatternCandidate(
        pattern_name="abstract_factory",
        category=PatternCategory.CREATIONAL,
        target_components=[p.get("name", "") for p in inp.ports[:3]] or all_components[:2],
        problem_solved=(
            "Multiple families of related objects (adapters, repositories, services) "
            "need to be created consistently without coupling to concrete implementations."
        ),
        implementation_sketch=(
            "class IInfrastructureFactory(ABC):\n"
            "    @abstractmethod\n"
            "    def create_repository(self) -> IRepository: ...\n"
            "    @abstractmethod\n"
            "    def create_cache(self) -> ICache: ...\n\n"
            "class PostgresInfraFactory(IInfrastructureFactory):\n"
            "    def create_repository(self) -> IRepository:\n"
            "        return PostgresRepository(self._session)\n"
            "    def create_cache(self) -> ICache:\n"
            "        return RedisCache(self._redis)"
        ),
        solid_principles_reinforced=["OCP", "DIP", "ISP"],
        rationale=(
            "Abstract Factory ensures consistent creation of infrastructure families. "
            + ("Hexagonal ports make this the natural factory boundary." if is_hexagonal else "")
        ),
        score=af_score,
    ))

    # Builder
    b_score = 1.5
    if component_count > 4:
        b_score += 1.5
    if srp_violated:
        b_score += 1.0
    if is_microservices:
        b_score += 0.5
    candidates.append(_PatternCandidate(
        pattern_name="builder",
        category=PatternCategory.CREATIONAL,
        target_components=all_components[:2],
        problem_solved=(
            "Complex objects with many optional parameters are constructed inline, "
            "producing telescoping constructors and unclear initialization sequences."
        ),
        implementation_sketch=(
            "class ServiceConfigBuilder:\n"
            "    def __init__(self): self._cfg = ServiceConfig()\n"
            "    def with_timeout(self, ms: int) -> 'ServiceConfigBuilder':\n"
            "        self._cfg.timeout = ms; return self\n"
            "    def with_retry(self, n: int) -> 'ServiceConfigBuilder':\n"
            "        self._cfg.retry = n; return self\n"
            "    def with_circuit_breaker(self) -> 'ServiceConfigBuilder':\n"
            "        self._cfg.circuit_breaker = True; return self\n"
            "    def build(self) -> ServiceConfig:\n"
            "        return self._cfg"
        ),
        solid_principles_reinforced=["SRP"],
        rationale=(
            "Builder separates the construction of a complex object from its representation, "
            "keeping each step single-purpose."
        ),
        score=b_score,
    ))

    # Singleton — applicable mainly for shared config/logging in monolith
    sing_score = 1.0
    if is_monolith:
        sing_score += 1.5
    if is_microservices:
        sing_score -= 3.0  # anti-pattern in distributed systems
    if sing_score > 0.5:
        candidates.append(_PatternCandidate(
            pattern_name="singleton",
            category=PatternCategory.CREATIONAL,
            target_components=["AppConfig", "Logger"],
            problem_solved=(
                "Shared infrastructure resources (configuration, logging) need exactly "
                "one instance throughout the application lifecycle."
            ),
            implementation_sketch=(
                "class AppConfig:\n"
                "    _instance: 'AppConfig | None' = None\n\n"
                "    def __new__(cls) -> 'AppConfig':\n"
                "        if cls._instance is None:\n"
                "            cls._instance = super().__new__(cls)\n"
                "            cls._instance._load()\n"
                "        return cls._instance\n\n"
                "    def _load(self) -> None:\n"
                "        self.db_url = os.getenv('DATABASE_URL', '')"
            ),
            solid_principles_reinforced=["SRP"],
            rationale=(
                "Singleton is appropriate for application-level shared state in single-process deployments. "
                "Avoid in distributed or multi-process contexts."
            ),
            score=sing_score,
        ))

    # Prototype — for domain objects cloning
    proto_score = 0.8
    if len(inp.bounded_contexts) > 0 or len(inp.domain_services) > 0:
        proto_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="prototype",
        category=PatternCategory.CREATIONAL,
        target_components=[ds.get("name", "") for ds in inp.domain_services[:2]] or all_components[:1],
        problem_solved=(
            "Domain objects that are expensive to create need to be cloned "
            "without coupling to their concrete classes."
        ),
        implementation_sketch=(
            "class DomainEntity:\n"
            "    def clone(self) -> 'DomainEntity':\n"
            "        return copy.deepcopy(self)\n\n"
            "# Usage:\n"
            "template = OrderTemplate(status='draft', items=[])\n"
            "new_order = template.clone()\n"
            "new_order.customer_id = customer.id"
        ),
        solid_principles_reinforced=["DIP"],
        rationale=(
            "Prototype allows copying domain aggregates without depending on their concrete class."
        ),
        score=proto_score,
    ))

    return candidates


@SkillRegistry.register
class CreationalPatternsSkill(BaseSkill):
    name = "design_patterns.creational_analyze"
    description = (
        "Analyzes architecture design and SOLID violations to recommend GoF Creational patterns "
        "(Factory Method, Abstract Factory, Builder, Singleton, Prototype). "
        "Returns scored candidates sorted by contextual fitness."
    )
    category = SkillCategory.DESIGN_PATTERNS
    tags = ["design-patterns", "gof", "creational", "architecture", "solid"]
    parameters = [
        SkillParameter(
            "design_input",
            "Serialized NormalizedDesignInput dict.",
            type="object",
        ),
        SkillParameter(
            "solid_violations",
            "List of violated SOLID principle codes (srp, ocp, lsp, isp, dip).",
            type="array",
            required=False,
            default=None,
        ),
        SkillParameter(
            "architecture_style",
            "Architecture style: microservices, hexagonal, monolith, or layered.",
            type="string",
            required=False,
            default="",
        ),
    ]

    async def execute(
        self,
        design_input: dict[str, Any] | None = None,
        solid_violations: list[str] | None = None,
        architecture_style: str = "",
        **_: Any,
    ) -> SkillResult:
        inp = NormalizedDesignInput.from_dict(design_input or {})
        violations = solid_violations or []
        style = architecture_style or inp.pattern or ""
        candidates = _analyze_creational(inp, violations, style)
        return SkillResult(
            success=True,
            summary=f"Creational analysis complete: {len(candidates)} pattern candidate(s) identified.",
            artifacts=[
                CodeArtifact(
                    filename="design_patterns_creational.json",
                    content=json.dumps([c.to_dict() for c in candidates], indent=2),
                    language="json",
                    description="Creational GoF pattern candidates",
                )
            ],
        )
