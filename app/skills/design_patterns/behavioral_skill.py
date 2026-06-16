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


def _analyze_behavioral(
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
    lsp_violated = "lsp" in solid_violations

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
    has_messaging = bool(all_tech & {"kafka", "rabbitmq", "activemq", "sqs", "pubsub", "nats"})

    
    st_score = 2.5
    if ocp_violated:
        st_score += 3.0
    if dip_violated:
        st_score += 1.5
    candidates.append(_PatternCandidate(
        pattern_name="strategy",
        category=PatternCategory.BEHAVIORAL,
        target_components=service_names[:2] or all_components[:2],
        problem_solved=(
            "Algorithm selection is hardcoded with switch/if-else blocks, "
            "requiring modification of existing classes every time a new variant is needed."
        ),
        implementation_sketch=(
            "class IDiscountStrategy(ABC):\n"
            "    @abstractmethod\n"
            "    def apply(self, price: Decimal) -> Decimal: ...\n\n"
            "class PercentageDiscount(IDiscountStrategy):\n"
            "    def __init__(self, pct: float): self._pct = pct\n"
            "    def apply(self, price: Decimal) -> Decimal:\n"
            "        return price * Decimal(1 - self._pct)\n\n"
            "class OrderPricer:\n"
            "    def __init__(self, strategy: IDiscountStrategy): ...\n"
            "    def price(self, order: Order) -> Decimal:\n"
            "        return self._strategy.apply(order.base_price)"
        ),
        solid_principles_reinforced=["OCP", "DIP"],
        rationale=(
            "Strategy replaces conditional logic with polymorphism, "
            "directly addressing OCP violations and enabling DIP through injected algorithms."
        ),
        score=st_score,
    ))

    
    ob_score = 1.5
    if is_microservices:
        ob_score += 2.5
    if has_messaging:
        ob_score += 2.0
    if dip_violated:
        ob_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="observer",
        category=PatternCategory.BEHAVIORAL,
        target_components=service_names[:3] or all_components[:2],
        problem_solved=(
            "Multiple components need to react to domain events without the producer "
            "being coupled to the list of consumers."
        ),
        implementation_sketch=(
            "class IEventHandler(ABC):\n"
            "    @abstractmethod\n"
            "    def handle(self, event: DomainEvent) -> None: ...\n\n"
            "class EventBus:\n"
            "    def __init__(self): self._handlers: dict[type, list[IEventHandler]] = {}\n"
            "    def subscribe(self, event_type: type, handler: IEventHandler) -> None:\n"
            "        self._handlers.setdefault(event_type, []).append(handler)\n"
            "    def publish(self, event: DomainEvent) -> None:\n"
            "        for handler in self._handlers.get(type(event), []):\n"
            "            handler.handle(event)"
        ),
        solid_principles_reinforced=["OCP", "DIP"],
        rationale=(
            "Observer decouples event producers from consumers, enabling independent extension. "
            + ("Essential for event-driven microservices." if is_microservices else "")
        ),
        score=ob_score,
    ))

    
    cm_score = 1.5
    if ocp_violated:
        cm_score += 1.5
    if srp_violated:
        cm_score += 1.0
    if is_microservices:
        cm_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="command",
        category=PatternCategory.BEHAVIORAL,
        target_components=service_names[:2] or all_components[:2],
        problem_solved=(
            "Operations need to be parameterized, queued, logged for audit, "
            "or support undo/redo — but they are hardcoded procedurally."
        ),
        implementation_sketch=(
            "class ICommand(ABC):\n"
            "    @abstractmethod\n"
            "    def execute(self) -> CommandResult: ...\n"
            "    @abstractmethod\n"
            "    def undo(self) -> None: ...\n\n"
            "class CreateOrderCommand(ICommand):\n"
            "    def __init__(self, repo: IOrderRepository, dto: CreateOrderDTO):\n"
            "        self._repo = repo; self._dto = dto\n"
            "    def execute(self) -> CommandResult:\n"
            "        order = Order.create(self._dto)\n"
            "        self._repo.save(order)\n"
            "        return CommandResult(id=order.id)\n"
            "    def undo(self) -> None:\n"
            "        self._repo.delete(self._result.id)"
        ),
        solid_principles_reinforced=["SRP", "OCP"],
        rationale=(
            "Command encapsulates requests as objects, enabling queuing, logging, and CQRS."
        ),
        score=cm_score,
    ))

    
    cor_score = 1.5
    if isp_violated:
        cor_score += 2.0
    if srp_violated:
        cor_score += 1.5
    if inp.has_gateway:
        cor_score += 1.5
    candidates.append(_PatternCandidate(
        pattern_name="chain_of_responsibility",
        category=PatternCategory.BEHAVIORAL,
        target_components=["APIGateway"] if inp.has_gateway else all_components[:2],
        problem_solved=(
            "Multiple handlers (auth, rate-limit, validation, logging) need to process "
            "a request sequentially without hardcoding the handler pipeline."
        ),
        implementation_sketch=(
            "class IMiddleware(ABC):\n"
            "    def __init__(self, next: 'IMiddleware | None' = None):\n"
            "        self._next = next\n"
            "    @abstractmethod\n"
            "    def handle(self, request: Request) -> Response: ...\n"
            "    def _pass(self, request: Request) -> Response:\n"
            "        if self._next: return self._next.handle(request)\n"
            "        raise HandlerNotFoundError\n\n"
            "class AuthMiddleware(IMiddleware):\n"
            "    def handle(self, request: Request) -> Response:\n"
            "        if not request.has_valid_token(): raise UnauthorizedError\n"
            "        return self._pass(request)"
        ),
        solid_principles_reinforced=["SRP", "OCP"],
        rationale=(
            "Chain of Responsibility builds composable middleware pipelines "
            "without coupling each handler to the next."
        ),
        score=cor_score,
    ))

    
    tm_score = 1.0
    if ocp_violated:
        tm_score += 1.5
    if lsp_violated:
        tm_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="template_method",
        category=PatternCategory.BEHAVIORAL,
        target_components=all_components[:2],
        problem_solved=(
            "Multiple use-cases share the same algorithmic skeleton but differ in specific steps, "
            "leading to code duplication or violation of LSP in inheritance hierarchies."
        ),
        implementation_sketch=(
            "class DataExporter(ABC):\n"
            "    def export(self, data: list[Entity]) -> bytes:\n"
            "        rows = self._prepare(data)      # hook\n"
            "        body = self._serialize(rows)    # hook\n"
            "        return self._compress(body)     # invariant\n"
            "    @abstractmethod\n"
            "    def _prepare(self, data: list[Entity]) -> list[dict]: ...\n"
            "    @abstractmethod\n"
            "    def _serialize(self, rows: list[dict]) -> bytes: ...\n"
            "    def _compress(self, body: bytes) -> bytes: return gzip.compress(body)\n\n"
            "class CsvExporter(DataExporter):\n"
            "    def _prepare(self, data): return [e.to_dict() for e in data]\n"
            "    def _serialize(self, rows): return csv_write(rows)"
        ),
        solid_principles_reinforced=["OCP", "LSP"],
        rationale=(
            "Template Method defines the invariant part of an algorithm while deferring "
            "variant steps to subclasses, satisfying OCP and LSP."
        ),
        score=tm_score,
    ))

    
    state_score = 1.0
    if srp_violated:
        state_score += 2.0
    if ocp_violated:
        state_score += 1.5
    domain_names_lower = " ".join(str(c) for c in all_components).lower()
    if any(kw in domain_names_lower for kw in ("order", "workflow", "process", "approval", "status")):
        state_score += 2.0
    candidates.append(_PatternCandidate(
        pattern_name="state",
        category=PatternCategory.BEHAVIORAL,
        target_components=all_components[:2],
        problem_solved=(
            "Domain objects whose behaviour changes dramatically based on internal state "
            "are modelled with large if/switch blocks, violating SRP and OCP."
        ),
        implementation_sketch=(
            "class IOrderState(ABC):\n"
            "    @abstractmethod\n"
            "    def pay(self, order: 'Order') -> None: ...\n"
            "    @abstractmethod\n"
            "    def ship(self, order: 'Order') -> None: ...\n\n"
            "class DraftState(IOrderState):\n"
            "    def pay(self, order: 'Order') -> None:\n"
            "        order.transition_to(PaidState())\n"
            "    def ship(self, order: 'Order') -> None:\n"
            "        raise InvalidTransitionError('Cannot ship an unpaid order')\n\n"
            "class Order:\n"
            "    def __init__(self): self._state: IOrderState = DraftState()\n"
            "    def transition_to(self, state: IOrderState): self._state = state\n"
            "    def pay(self): self._state.pay(self)\n"
            "    def ship(self): self._state.ship(self)"
        ),
        solid_principles_reinforced=["SRP", "OCP"],
        rationale=(
            "State pattern externalises state-dependent behaviour into dedicated classes, "
            "eliminating conditional logic in the context class."
        ),
        score=state_score,
    ))

    
    med_score = 0.8
    if isp_violated:
        med_score += 2.5
    if srp_violated:
        med_score += 1.0
    if len(service_names) > 3:
        med_score += 1.5
    candidates.append(_PatternCandidate(
        pattern_name="mediator",
        category=PatternCategory.BEHAVIORAL,
        target_components=service_names[:3] or all_components[:2],
        problem_solved=(
            "Many components communicate directly with each other, "
            "creating a tangled web of dependencies that violates ISP and SRP."
        ),
        implementation_sketch=(
            "class IMediator(ABC):\n"
            "    @abstractmethod\n"
            "    def notify(self, sender: 'IComponent', event: str, data: Any) -> None: ...\n\n"
            "class CheckoutMediator(IMediator):\n"
            "    def __init__(self, inventory, payment, shipping): ...\n"
            "    def notify(self, sender, event, data):\n"
            "        if event == 'order_placed':\n"
            "            self._inventory.reserve(data)\n"
            "            self._payment.charge(data)\n"
            "            self._shipping.schedule(data)"
        ),
        solid_principles_reinforced=["ISP", "SRP"],
        rationale=(
            "Mediator centralises complex inter-component communication, "
            "reducing direct dependencies and satisfying ISP."
        ),
        score=med_score,
    ))

    return candidates


@SkillRegistry.register
class BehavioralPatternsSkill(BaseSkill):
    name = "design_patterns.behavioral_analyze"
    description = (
        "Analyzes architecture design and SOLID violations to recommend GoF Behavioral patterns "
        "(Strategy, Observer, Command, Chain of Responsibility, Template Method, State, Mediator). "
        "Returns scored candidates sorted by contextual fitness."
    )
    category = SkillCategory.DESIGN_PATTERNS
    tags = ["design-patterns", "gof", "behavioral", "architecture", "solid"]
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
        candidates = _analyze_behavioral(inp, violations, style)
        return SkillResult(
            success=True,
            summary=f"Behavioral analysis complete: {len(candidates)} pattern candidate(s) identified.",
            artifacts=[
                CodeArtifact(
                    filename="design_patterns_behavioral.json",
                    content=json.dumps([c.to_dict() for c in candidates], indent=2),
                    language="json",
                    description="Behavioral GoF pattern candidates",
                )
            ],
        )
