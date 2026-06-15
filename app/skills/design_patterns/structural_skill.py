import json
from dataclasses import dataclass
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


def _analyze_structural(
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
    isp_violated = "isp" in solid_violations

    all_components = (
        [c.get("name", "") for c in inp.components]
        + [m.get("name", "") for m in inp.modules]
        + [bc.get("name", "") for bc in inp.bounded_contexts]
    )
    service_names = [c.get("name", "") for c in inp.components if c.get("type") == "service"]

    all_tech: set[str] = set()
    for c in inp.components:
        for h in c.get("technology_hints", []):
            all_tech.add(h.lower())
    has_cache_tech = bool(all_tech & {"redis", "memcached"})

    # Adapter
    ad_score = 2.0
    if dip_violated:
        ad_score += 3.0
    if is_hexagonal:
        ad_score += 2.5
    if inp.has_ports_and_adapters:
        ad_score += 2.0
    driven_ports = [p.get("name", "") for p in inp.ports if p.get("port_type") == "driven"]
    candidates.append(_PatternCandidate(
        pattern_name="adapter",
        category=PatternCategory.STRUCTURAL,
        target_components=driven_ports[:3] or all_components[:2],
        problem_solved=(
            "External library or system interfaces are incompatible with the domain's expected "
            "abstractions, forcing domain code to depend on third-party concretions."
        ),
        implementation_sketch=(
            "class IPaymentGateway(ABC):\n"
            "    @abstractmethod\n"
            "    def charge(self, amount: Decimal, currency: str) -> PaymentResult: ...\n\n"
            "class StripeAdapter(IPaymentGateway):\n"
            "    def __init__(self, stripe_client: stripe.Client): ...\n"
            "    def charge(self, amount: Decimal, currency: str) -> PaymentResult:\n"
            "        result = self._client.charges.create(amount=int(amount*100), currency=currency)\n"
            "        return PaymentResult(id=result.id, status=result.status)"
        ),
        solid_principles_reinforced=["DIP", "OCP"],
        rationale=(
            "Adapter makes external interfaces conform to domain abstractions, satisfying DIP. "
            + ("Hexagonal ports are the natural adapter boundary." if is_hexagonal else "")
        ),
        score=ad_score,
    ))

    # Facade
    fa_score = 1.5
    if is_microservices:
        fa_score += 2.5
    if srp_violated:
        fa_score += 1.5
    if inp.has_gateway:
        fa_score += 1.5
    if len(all_components) > 4:
        fa_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="facade",
        category=PatternCategory.STRUCTURAL,
        target_components=["APIGateway"] if inp.has_gateway else all_components[:2],
        problem_solved=(
            "Subsystem complexity leaks into client code; callers must coordinate multiple "
            "service calls to accomplish a single high-level operation."
        ),
        implementation_sketch=(
            "class OrderFacade:\n"
            "    def __init__(self, inventory: IInventoryService,\n"
            "                 payment: IPaymentService,\n"
            "                 notification: INotificationService): ...\n\n"
            "    def place_order(self, order: Order) -> OrderResult:\n"
            "        self._inventory.reserve(order.items)\n"
            "        charge = self._payment.charge(order.total)\n"
            "        self._notification.send_confirmation(order, charge)\n"
            "        return OrderResult(order_id=order.id, status='confirmed')"
        ),
        solid_principles_reinforced=["SRP", "ISP"],
        rationale=(
            "Facade reduces coupling between clients and subsystem internals. "
            + ("The API gateway is the natural facade boundary in microservices." if is_microservices else "")
        ),
        score=fa_score,
    ))

    # Decorator
    de_score = 1.5
    if ocp_violated:
        de_score += 3.0
    if srp_violated:
        de_score += 1.5
    candidates.append(_PatternCandidate(
        pattern_name="decorator",
        category=PatternCategory.STRUCTURAL,
        target_components=service_names[:2] or all_components[:2],
        problem_solved=(
            "Cross-cutting behaviour (logging, caching, retry, auth) is mixed into service "
            "methods, violating OCP and SRP — modifying the service class for each new concern."
        ),
        implementation_sketch=(
            "class LoggingServiceDecorator(IService):\n"
            "    def __init__(self, inner: IService, logger: ILogger):\n"
            "        self._inner = inner\n"
            "        self._logger = logger\n\n"
            "    def process(self, request: Request) -> Response:\n"
            "        self._logger.info(f'Calling process with {request}')\n"
            "        result = self._inner.process(request)\n"
            "        self._logger.info(f'Result: {result}')\n"
            "        return result"
        ),
        solid_principles_reinforced=["OCP", "SRP"],
        rationale=(
            "Decorator layers cross-cutting concerns without modifying existing classes, "
            "directly addressing OCP violations."
        ),
        score=de_score,
    ))

    # Proxy
    pr_score = 1.0
    if dip_violated:
        pr_score += 1.5
    if has_cache_tech:
        pr_score += 2.0
    if is_microservices:
        pr_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="proxy",
        category=PatternCategory.STRUCTURAL,
        target_components=service_names[:2] or all_components[:1],
        problem_solved=(
            "Expensive or sensitive resource access needs interception for caching, "
            "lazy loading, or access control without modifying the real object."
        ),
        implementation_sketch=(
            "class CachingRepositoryProxy(IRepository):\n"
            "    def __init__(self, real: IRepository, cache: ICache):\n"
            "        self._real = real; self._cache = cache\n\n"
            "    def find_by_id(self, entity_id: UUID) -> Entity | None:\n"
            "        cached = self._cache.get(str(entity_id))\n"
            "        if cached is not None:\n"
            "            return cached\n"
            "        entity = self._real.find_by_id(entity_id)\n"
            "        if entity:\n"
            "            self._cache.set(str(entity_id), entity, ttl=300)\n"
            "        return entity"
        ),
        solid_principles_reinforced=["OCP", "DIP"],
        rationale=(
            "Proxy adds behaviour transparently through the same interface, "
            "satisfying OCP and enabling DIP through abstraction."
        ),
        score=pr_score,
    ))

    # Bridge
    br_score = 0.8
    if isp_violated:
        br_score += 2.5
    if ocp_violated:
        br_score += 1.5
    if len(inp.ports) > 2:
        br_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="bridge",
        category=PatternCategory.STRUCTURAL,
        target_components=all_components[:2],
        problem_solved=(
            "Abstraction and implementation are tightly bound, making it impossible "
            "to vary them independently — especially when fat interfaces violate ISP."
        ),
        implementation_sketch=(
            "class IMessageSender(ABC):      # Implementation\n"
            "    @abstractmethod\n"
            "    def send(self, body: str) -> None: ...\n\n"
            "class INotification(ABC):        # Abstraction\n"
            "    def __init__(self, sender: IMessageSender): self._sender = sender\n"
            "    @abstractmethod\n"
            "    def notify(self, event: Event) -> None: ...\n\n"
            "class OrderNotification(INotification):\n"
            "    def notify(self, event: Event) -> None:\n"
            "        self._sender.send(f'Order {event.order_id} updated to {event.status}')"
        ),
        solid_principles_reinforced=["OCP", "ISP"],
        rationale=(
            "Bridge decouples abstraction from implementation so both can evolve independently."
        ),
        score=br_score,
    ))

    # Composite — for hierarchical structures
    co_score = 0.8
    if any("tree" in str(bc).lower() or "hierarchy" in str(bc).lower() or "category" in str(bc).lower()
           for bc in inp.bounded_contexts + inp.modules):
        co_score += 2.0
    candidates.append(_PatternCandidate(
        pattern_name="composite",
        category=PatternCategory.STRUCTURAL,
        target_components=all_components[:2],
        problem_solved=(
            "Hierarchical tree-like structures (menus, categories, organisations) "
            "need uniform treatment regardless of whether the node is a leaf or a container."
        ),
        implementation_sketch=(
            "class IComponent(ABC):\n"
            "    @abstractmethod\n"
            "    def execute(self) -> Result: ...\n\n"
            "class Leaf(IComponent):\n"
            "    def execute(self) -> Result: return self._do_work()\n\n"
            "class Composite(IComponent):\n"
            "    def __init__(self): self._children: list[IComponent] = []\n"
            "    def add(self, c: IComponent) -> None: self._children.append(c)\n"
            "    def execute(self) -> Result:\n"
            "        return Result.merge(c.execute() for c in self._children)"
        ),
        solid_principles_reinforced=["OCP"],
        rationale=(
            "Composite allows treating individual objects and compositions uniformly, "
            "enabling recursive structures without special-casing."
        ),
        score=co_score,
    ))

    return candidates


@SkillRegistry.register
class StructuralPatternsSkill(BaseSkill):
    name = "design_patterns.structural_analyze"
    description = (
        "Analyzes architecture design and SOLID violations to recommend GoF Structural patterns "
        "(Adapter, Facade, Decorator, Proxy, Bridge, Composite). "
        "Returns scored candidates sorted by contextual fitness."
    )
    category = SkillCategory.DESIGN_PATTERNS
    tags = ["design-patterns", "gof", "structural", "architecture", "solid"]
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
        candidates = _analyze_structural(inp, violations, style)
        return SkillResult(
            success=True,
            summary=f"Structural analysis complete: {len(candidates)} pattern candidate(s) identified.",
            artifacts=[
                CodeArtifact(
                    filename="design_patterns_structural.json",
                    content=json.dumps([c.to_dict() for c in candidates], indent=2),
                    language="json",
                    description="Structural GoF pattern candidates",
                )
            ],
        )
