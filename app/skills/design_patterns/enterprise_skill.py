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


def _analyze_enterprise(
    inp: NormalizedDesignInput,
    solid_violations: list[str],
    architecture_style: str,
) -> list[_PatternCandidate]:
    candidates: list[_PatternCandidate] = []
    style = architecture_style.lower()
    is_microservices = style == "microservices"
    is_hexagonal = style in ("hexagonal", "hexagonal_architecture")
    is_monolith = style in ("monolith", "layered")

    dip_violated = "dip" in solid_violations
    srp_violated = "srp" in solid_violations
    ocp_violated = "ocp" in solid_violations

    all_components = (
        [c.get("name", "") for c in inp.components]
        + [m.get("name", "") for m in inp.modules]
        + [bc.get("name", "") for bc in inp.bounded_contexts]
    )
    db_components = [c.get("name", "") for c in inp.components if c.get("type") == "database"]
    service_names = [c.get("name", "") for c in inp.components if c.get("type") == "service"]

    all_tech: set[str] = set()
    for c in inp.components:
        for h in c.get("technology_hints", []):
            all_tech.add(h.lower())
    has_messaging = bool(all_tech & {"kafka", "rabbitmq", "activemq", "sqs", "pubsub", "nats"})
    has_db = bool(all_tech & {"postgresql", "mysql", "mariadb", "mongodb", "sqlite"})
    domain_text = " ".join(str(c) for c in all_components).lower()
    has_legacy = any(kw in domain_text for kw in ("legacy", "monolith", "migration", "existing", "old"))

    # Repository
    repo_score = 3.0
    if dip_violated:
        repo_score += 4.0
    if not inp.has_repositories:
        repo_score += 3.0
    if is_hexagonal:
        repo_score += 2.0
    if has_db:
        repo_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="repository",
        category=PatternCategory.ENTERPRISE,
        target_components=db_components[:2] or all_components[:2],
        problem_solved=(
            "Domain objects are coupled to data access mechanisms (ORM sessions, SQL queries). "
            "The domain layer violates DIP by depending on infrastructure concretions."
        ),
        implementation_sketch=(
            "class IUserRepository(ABC):\n"
            "    @abstractmethod\n"
            "    def find_by_id(self, user_id: UUID) -> User | None: ...\n"
            "    @abstractmethod\n"
            "    def save(self, user: User) -> None: ...\n"
            "    @abstractmethod\n"
            "    def find_by_email(self, email: str) -> User | None: ...\n\n"
            "class PostgresUserRepository(IUserRepository):\n"
            "    def __init__(self, session: AsyncSession): self._session = session\n"
            "    async def find_by_id(self, user_id: UUID) -> User | None:\n"
            "        row = await self._session.get(UserRow, user_id)\n"
            "        return UserMapper.to_domain(row) if row else None\n"
            "    async def save(self, user: User) -> None:\n"
            "        row = UserMapper.to_row(user)\n"
            "        self._session.add(row)"
        ),
        solid_principles_reinforced=["DIP", "SRP"],
        rationale=(
            "Repository abstracts data access behind a domain-aligned interface, "
            "satisfying DIP and keeping the domain free of infrastructure concerns. "
            + ("DIP violation makes this high-priority." if dip_violated else "")
        ),
        score=repo_score,
    ))

    # Unit of Work
    uow_score = 2.0
    if inp.has_repositories or not inp.has_repositories:
        uow_score += 0.5
    if has_db:
        uow_score += 1.0
    if len(db_components) > 1 or len(service_names) > 2:
        uow_score += 1.5
    if is_microservices:
        uow_score -= 0.5
    candidates.append(_PatternCandidate(
        pattern_name="unit_of_work",
        category=PatternCategory.ENTERPRISE,
        target_components=service_names[:2] or all_components[:2],
        problem_solved=(
            "Multiple repository operations spanning a business transaction need to be "
            "committed or rolled back atomically, but each repository manages its own session."
        ),
        implementation_sketch=(
            "class IUnitOfWork(ABC):\n"
            "    users: IUserRepository\n"
            "    orders: IOrderRepository\n"
            "    @abstractmethod\n"
            "    async def __aenter__(self) -> 'IUnitOfWork': ...\n"
            "    @abstractmethod\n"
            "    async def __aexit__(self, *exc) -> None: ...\n"
            "    @abstractmethod\n"
            "    async def commit(self) -> None: ...\n"
            "    @abstractmethod\n"
            "    async def rollback(self) -> None: ...\n\n"
            "class SqlAlchemyUnitOfWork(IUnitOfWork):\n"
            "    async def __aenter__(self):\n"
            "        self._session = self._session_factory()\n"
            "        self.users = PostgresUserRepository(self._session)\n"
            "        self.orders = PostgresOrderRepository(self._session)\n"
            "        return self"
        ),
        solid_principles_reinforced=["SRP"],
        rationale=(
            "Unit of Work coordinates multiple repository operations inside a single "
            "transaction boundary, keeping the application service free of session management."
        ),
        score=uow_score,
    ))

    # CQRS
    cqrs_score = 1.5
    if is_microservices:
        cqrs_score += 3.0
    if inp.service_count > 3:
        cqrs_score += 1.5
    if srp_violated:
        cqrs_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="cqrs",
        category=PatternCategory.ENTERPRISE,
        target_components=service_names[:3] or all_components[:2],
        problem_solved=(
            "Read and write operations share the same model, causing impedance mismatches: "
            "write-side validation conflicts with read-side query flexibility."
        ),
        implementation_sketch=(
            "# Write side\n"
            "class CreateOrderCommand(BaseModel):\n"
            "    customer_id: UUID\n"
            "    items: list[OrderItemDTO]\n\n"
            "class CreateOrderCommandHandler:\n"
            "    def handle(self, cmd: CreateOrderCommand) -> OrderId:\n"
            "        order = Order.create(cmd.customer_id, cmd.items)\n"
            "        self._repo.save(order)\n"
            "        return order.id\n\n"
            "# Read side\n"
            "class OrderSummaryQuery(BaseModel):\n"
            "    customer_id: UUID\n\n"
            "class OrderSummaryQueryHandler:\n"
            "    def handle(self, q: OrderSummaryQuery) -> list[OrderSummaryView]:\n"
            "        return self._read_db.query(\n"
            "            'SELECT * FROM order_views WHERE customer_id = ?', q.customer_id)"
        ),
        solid_principles_reinforced=["SRP", "ISP"],
        rationale=(
            "CQRS separates the write model from the read model, allowing each to be "
            "optimised independently — critical in microservices with high read/write asymmetry."
        ),
        score=cqrs_score,
    ))

    # Event Sourcing
    es_score = 1.0
    if is_microservices:
        es_score += 2.0
    if has_messaging:
        es_score += 2.0
    if ocp_violated:
        es_score += 1.0
    candidates.append(_PatternCandidate(
        pattern_name="event_sourcing",
        category=PatternCategory.ENTERPRISE,
        target_components=service_names[:2] or all_components[:2],
        problem_solved=(
            "System state history and audit trails are not available; "
            "state is overwritten in place with no record of how it got there."
        ),
        implementation_sketch=(
            "class DomainEvent(BaseModel):\n"
            "    event_id: UUID = Field(default_factory=uuid4)\n"
            "    occurred_at: datetime = Field(default_factory=datetime.utcnow)\n"
            "    aggregate_id: UUID\n\n"
            "class OrderCreatedEvent(DomainEvent):\n"
            "    customer_id: UUID\n"
            "    items: list[OrderItemDTO]\n\n"
            "class Order:\n"
            "    def __init__(self): self._events: list[DomainEvent] = []\n"
            "    def create(self, cmd: CreateOrderCommand) -> None:\n"
            "        event = OrderCreatedEvent(\n"
            "            aggregate_id=uuid4(), customer_id=cmd.customer_id, items=cmd.items)\n"
            "        self._apply(event)\n"
            "        self._events.append(event)\n"
            "    def _apply(self, event: DomainEvent) -> None:\n"
            "        match event:\n"
            "            case OrderCreatedEvent(): self.status = 'draft'"
        ),
        solid_principles_reinforced=["OCP", "SRP"],
        rationale=(
            "Event Sourcing preserves full state history as an immutable event log, "
            "enabling audit, replay, and temporal queries. "
            + ("Complements CQRS naturally." if is_microservices else "")
        ),
        score=es_score,
    ))

    # Saga
    saga_score = 1.5
    if is_microservices:
        saga_score += 4.0
    if inp.service_count > 3:
        saga_score += 1.5
    if has_messaging:
        saga_score += 2.0
    if not is_microservices:
        saga_score = max(0.5, saga_score - 3.0)
    if saga_score > 1.0:
        candidates.append(_PatternCandidate(
            pattern_name="saga",
            category=PatternCategory.ENTERPRISE,
            target_components=service_names[:3] or all_components[:2],
            problem_solved=(
                "Distributed business transactions span multiple microservices "
                "without a single ACID transaction — partial failures leave data inconsistent."
            ),
            implementation_sketch=(
                "# Choreography-based Saga\n"
                "class OrderSagaOrchestrator:\n"
                "    def start(self, order_id: UUID) -> None:\n"
                "        self._event_bus.publish(OrderCreatedEvent(order_id))\n\n"
                "class InventoryService:  # saga participant\n"
                "    @event_handler(OrderCreatedEvent)\n"
                "    def on_order_created(self, event: OrderCreatedEvent):\n"
                "        try:\n"
                "            self._reserve(event.order_id)\n"
                "            self._event_bus.publish(InventoryReservedEvent(event.order_id))\n"
                "        except InsufficientStockError:\n"
                "            self._event_bus.publish(InventoryReservationFailedEvent(event.order_id))\n\n"
                "class OrderService:  # compensating transaction\n"
                "    @event_handler(InventoryReservationFailedEvent)\n"
                "    def on_reservation_failed(self, event):\n"
                "        self._cancel_order(event.order_id)"
            ),
            solid_principles_reinforced=["SRP"],
            rationale=(
                "Saga coordinates long-running distributed transactions through events and "
                "compensating actions, maintaining eventual consistency without 2PC."
            ),
            score=saga_score,
        ))

    # Outbox
    outbox_score = 1.0
    if is_microservices:
        outbox_score += 3.0
    if has_messaging:
        outbox_score += 2.5
    if is_monolith:
        outbox_score -= 1.5
    if outbox_score > 1.0:
        candidates.append(_PatternCandidate(
            pattern_name="outbox",
            category=PatternCategory.ENTERPRISE,
            target_components=service_names[:2] or all_components[:2],
            problem_solved=(
                "Events published after a database commit can be lost if the message broker "
                "is unavailable, leading to data inconsistency between the DB and event stream."
            ),
            implementation_sketch=(
                "# Step 1: Transactional Outbox table\n"
                "class OutboxEntry(Base):\n"
                "    id: UUID = Column(UUID, primary_key=True)\n"
                "    event_type: str = Column(String)\n"
                "    payload: dict = Column(JSON)\n"
                "    published_at: datetime | None = Column(DateTime, nullable=True)\n\n"
                "# Step 2: Write event atomically with domain change\n"
                "async with uow:\n"
                "    order = Order.create(cmd)\n"
                "    uow.orders.save(order)\n"
                "    uow.outbox.add(OutboxEntry(\n"
                "        event_type='OrderCreated', payload=order.to_event_dict()))\n"
                "    await uow.commit()\n\n"
                "# Step 3: Relay worker publishes unpublished entries\n"
                "class OutboxRelay:\n"
                "    async def run(self):\n"
                "        entries = await self._repo.find_unpublished()\n"
                "        for e in entries:\n"
                "            await self._broker.publish(e.event_type, e.payload)\n"
                "            e.published_at = datetime.utcnow()"
            ),
            solid_principles_reinforced=["SRP"],
            rationale=(
                "Outbox guarantees at-least-once event delivery by persisting events "
                "in the same transaction as the state change."
            ),
            score=outbox_score,
        ))

    # Strangler Fig
    sf_score = 0.5
    if has_legacy:
        sf_score += 4.5
    if is_monolith:
        sf_score += 2.0
    if is_microservices and not has_legacy:
        sf_score = 0.0
    if sf_score > 1.0:
        candidates.append(_PatternCandidate(
            pattern_name="strangler_fig",
            category=PatternCategory.ENTERPRISE,
            target_components=all_components[:2],
            problem_solved=(
                "A legacy monolith cannot be rewritten at once; "
                "a big-bang migration carries too much risk and business disruption."
            ),
            implementation_sketch=(
                "# 1. Add a facade/proxy in front of the legacy system\n"
                "class LegacyProxyGateway:\n"
                "    def route(self, request: Request) -> Response:\n"
                "        if self._new_service.can_handle(request):\n"
                "            return self._new_service.handle(request)\n"
                "        return self._legacy.forward(request)\n\n"
                "# 2. Incrementally migrate features behind the gateway\n"
                "# Feature: User Profile\n"
                "#   Before: handled by LegacyApp.UserModule\n"
                "#   After:  handled by UserProfileService (new microservice)\n\n"
                "# 3. When all features migrated, decommission the legacy system"
            ),
            solid_principles_reinforced=["OCP"],
            rationale=(
                "Strangler Fig enables incremental replacement of a legacy system "
                "by routing traffic progressively to new services."
            ),
            score=sf_score,
        ))

    # Anti-Corruption Layer
    acl_score = 1.5
    if is_hexagonal:
        acl_score += 2.5
    if inp.has_ports_and_adapters:
        acl_score += 1.5
    if dip_violated:
        acl_score += 2.0
    driven_ports = [p.get("name", "") for p in inp.ports if p.get("port_type") == "driven"]
    acl_components = driven_ports[:2] or db_components[:1] or all_components[:2]
    candidates.append(_PatternCandidate(
        pattern_name="anti_corruption_layer",
        category=PatternCategory.ENTERPRISE,
        target_components=acl_components,
        problem_solved=(
            "External domain models (third-party APIs, legacy systems) pollute the internal "
            "domain model by leaking their types, semantics, and concepts into the core."
        ),
        implementation_sketch=(
            "# External model (third-party payment provider)\n"
            "class ExternalPaymentDTO:\n"
            "    transaction_ref: str\n"
            "    amount_cents: int\n"
            "    currency_code: str\n"
            "    payment_state: str  # PENDING|COMPLETED|FAILED\n\n"
            "# Internal domain model\n"
            "class PaymentResult:\n"
            "    payment_id: PaymentId\n"
            "    amount: Money\n"
            "    status: PaymentStatus  # domain enum\n\n"
            "# ACL (Anti-Corruption Layer) translates between models\n"
            "class PaymentAntiCorruptionLayer:\n"
            "    def translate(self, ext: ExternalPaymentDTO) -> PaymentResult:\n"
            "        return PaymentResult(\n"
            "            payment_id=PaymentId(ext.transaction_ref),\n"
            "            amount=Money(ext.amount_cents / 100, ext.currency_code),\n"
            "            status=PaymentStatus.from_external(ext.payment_state))"
        ),
        solid_principles_reinforced=["DIP", "OCP"],
        rationale=(
            "ACL prevents external concepts from leaking into the domain model, "
            "protecting bounded context integrity and satisfying DIP."
        ),
        score=acl_score,
    ))

    return candidates


@SkillRegistry.register
class EnterprisePatternsSkill(BaseSkill):
    name = "design_patterns.enterprise_analyze"
    description = (
        "Analyzes architecture design and SOLID violations to recommend enterprise patterns "
        "(Repository, Unit of Work, CQRS, Event Sourcing, Saga, Outbox, "
        "Strangler Fig, Anti-Corruption Layer). "
        "Returns scored candidates sorted by contextual fitness."
    )
    category = SkillCategory.DESIGN_PATTERNS
    tags = ["design-patterns", "enterprise", "ddd", "architecture", "solid"]
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
        candidates = _analyze_enterprise(inp, violations, style)
        return SkillResult(
            success=True,
            summary=f"Enterprise analysis complete: {len(candidates)} pattern candidate(s) identified.",
            artifacts=[
                CodeArtifact(
                    filename="design_patterns_enterprise.json",
                    content=json.dumps([c.to_dict() for c in candidates], indent=2),
                    language="json",
                    description="Enterprise pattern candidates",
                )
            ],
        )
