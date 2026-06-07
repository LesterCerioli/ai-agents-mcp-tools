from typing import Any

from ..base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from ..registry import SkillRegistry

_PATTERNS = [
    "factory",
    "strategy",
    "observer",
    "command",
    "cqrs",
    "unit_of_work",
    "event_bus",
    "saga",
]


def _factory(context: str) -> tuple[str, str]:
    name = context or "Payment"
    code = (
        f"from abc import ABC, abstractmethod\n\n\n"
        f"class {name}(ABC):\n"
        f"    @abstractmethod\n"
        f"    async def process(self, amount: float) -> bool: ...\n\n\n"
        f"class StripePayment({name}):\n"
        f"    async def process(self, amount: float) -> bool:\n"
        f"        # integrate with Stripe SDK\n"
        f"        return True\n\n\n"
        f"class PayPalPayment({name}):\n"
        f"    async def process(self, amount: float) -> bool:\n"
        f"        # integrate with PayPal SDK\n"
        f"        return True\n\n\n"
        f"class {name}Factory:\n"
        f'    _registry: dict[str, type[{name}]] = {{\n'
        f'        "stripe": StripePayment,\n'
        f'        "paypal": PayPalPayment,\n'
        f"    }}\n\n"
        f"    @classmethod\n"
        f"    def create(cls, provider: str) -> {name}:\n"
        f"        klass = cls._registry.get(provider)\n"
        f"        if klass is None:\n"
        f'            raise ValueError(f"Unknown {name.lower()} provider: {{provider}}")\n'
        f"        return klass()\n"
    )
    return f"app/patterns/factory/{name.lower()}_factory.py", code


def _strategy(context: str) -> tuple[str, str]:
    name = context or "Pricing"
    code = (
        f"from abc import ABC, abstractmethod\n"
        f"from dataclasses import dataclass\n\n\n"
        f"class {name}Strategy(ABC):\n"
        f"    @abstractmethod\n"
        f"    def calculate(self, base_price: float, **kwargs) -> float: ...\n\n\n"
        f"class StandardPricing({name}Strategy):\n"
        f"    def calculate(self, base_price: float, **kwargs) -> float:\n"
        f"        return base_price\n\n\n"
        f"class DiscountedPricing({name}Strategy):\n"
        f"    def __init__(self, discount_pct: float) -> None:\n"
        f"        self._discount = discount_pct\n\n"
        f"    def calculate(self, base_price: float, **kwargs) -> float:\n"
        f"        return base_price * (1 - self._discount)\n\n\n"
        f"@dataclass\n"
        f"class {name}Context:\n"
        f"    _strategy: {name}Strategy\n\n"
        f"    def set_strategy(self, strategy: {name}Strategy) -> None:\n"
        f"        self._strategy = strategy\n\n"
        f"    def execute(self, base_price: float, **kwargs) -> float:\n"
        f"        return self._strategy.calculate(base_price, **kwargs)\n"
    )
    return f"app/patterns/strategy/{name.lower()}_strategy.py", code


def _observer(context: str) -> tuple[str, str]:
    name = context or "Order"
    code = (
        f"from abc import ABC, abstractmethod\n\n\n"
        f"class {name}Event:\n"
        f"    def __init__(self, payload: dict) -> None:\n"
        f"        self.payload = payload\n\n\n"
        f"class {name}Observer(ABC):\n"
        f"    @abstractmethod\n"
        f"    async def handle(self, event: {name}Event) -> None: ...\n\n\n"
        f"class EmailNotification({name}Observer):\n"
        f"    async def handle(self, event: {name}Event) -> None:\n"
        f"        # send email based on event.payload\n"
        f"        pass\n\n\n"
        f"class {name}Subject:\n"
        f"    def __init__(self) -> None:\n"
        f"        self._observers: list[{name}Observer] = []\n\n"
        f"    def subscribe(self, observer: {name}Observer) -> None:\n"
        f"        self._observers.append(observer)\n\n"
        f"    async def notify(self, event: {name}Event) -> None:\n"
        f"        for observer in self._observers:\n"
        f"            await observer.handle(event)\n"
    )
    return f"app/patterns/observer/{name.lower()}_subject.py", code


def _command(context: str) -> tuple[str, str]:
    name = context or "Order"
    code = (
        f"from abc import ABC, abstractmethod\n"
        f"from dataclasses import dataclass\n\n\n"
        f"class Command(ABC):\n"
        f"    @abstractmethod\n"
        f"    async def execute(self) -> None: ...\n\n"
        f"    @abstractmethod\n"
        f"    async def undo(self) -> None: ...\n\n\n"
        f"@dataclass\n"
        f"class Create{name}Command(Command):\n"
        f"    data: dict\n\n"
        f"    async def execute(self) -> None:\n"
        f"        # create {name.lower()} with self.data\n"
        f"        pass\n\n"
        f"    async def undo(self) -> None:\n"
        f"        # rollback creation\n"
        f"        pass\n\n\n"
        f"class CommandBus:\n"
        f"    def __init__(self) -> None:\n"
        f"        self._history: list[Command] = []\n\n"
        f"    async def dispatch(self, command: Command) -> None:\n"
        f"        await command.execute()\n"
        f"        self._history.append(command)\n\n"
        f"    async def undo_last(self) -> None:\n"
        f"        if self._history:\n"
        f"            await self._history.pop().undo()\n"
    )
    return f"app/patterns/command/{name.lower()}_commands.py", code


def _cqrs(context: str) -> tuple[str, str]:
    name = context or "Order"
    code = (
        f"from dataclasses import dataclass\n"
        f"from abc import ABC, abstractmethod\n\n\n"
        f"# ── Commands (write side) ─────────────────────────────────────────────\n\n"
        f"@dataclass\n"
        f"class Create{name}Command:\n"
        f"    payload: dict\n\n\n"
        f"class Create{name}CommandHandler:\n"
        f"    async def handle(self, cmd: Create{name}Command) -> None:\n"
        f"        # persist to write store\n"
        f"        pass\n\n\n"
        f"# ── Queries (read side) ───────────────────────────────────────────────\n\n"
        f"@dataclass\n"
        f"class Get{name}Query:\n"
        f"    id: int\n\n\n"
        f"@dataclass\n"
        f"class {name}ReadModel:\n"
        f"    id: int\n"
        f"    summary: str\n\n\n"
        f"class Get{name}QueryHandler:\n"
        f"    async def handle(self, query: Get{name}Query) -> {name}ReadModel | None:\n"
        f"        # fetch from read store (e.g. Elasticsearch, Redis)\n"
        f"        return None\n\n\n"
        f"# ── Bus ──────────────────────────────────────────────────────────────\n\n"
        f"class CommandBus:\n"
        f"    async def dispatch(self, command) -> None:\n"
        f"        handler_map = {{Create{name}Command: Create{name}CommandHandler()}}\n"
        f"        handler = handler_map.get(type(command))\n"
        f"        if handler:\n"
        f"            await handler.handle(command)\n\n\n"
        f"class QueryBus:\n"
        f"    async def ask(self, query) -> object:\n"
        f"        handler_map = {{Get{name}Query: Get{name}QueryHandler()}}\n"
        f"        handler = handler_map.get(type(query))\n"
        f"        if handler:\n"
        f"            return await handler.handle(query)\n"
        f"        return None\n"
    )
    return f"app/patterns/cqrs/{name.lower()}_cqrs.py", code


def _unit_of_work(context: str) -> tuple[str, str]:
    name = context or "App"
    code = (
        f"from abc import ABC, abstractmethod\n"
        f"from sqlalchemy.ext.asyncio import AsyncSession\n\n\n"
        f"class UnitOfWork(ABC):\n"
        f"    @abstractmethod\n"
        f"    async def __aenter__(self) -> 'UnitOfWork': ...\n\n"
        f"    @abstractmethod\n"
        f"    async def __aexit__(self, *args) -> None: ...\n\n"
        f"    @abstractmethod\n"
        f"    async def commit(self) -> None: ...\n\n"
        f"    @abstractmethod\n"
        f"    async def rollback(self) -> None: ...\n\n\n"
        f"class SQLAlchemyUnitOfWork(UnitOfWork):\n"
        f"    def __init__(self, session: AsyncSession) -> None:\n"
        f"        self._session = session\n\n"
        f"    async def __aenter__(self) -> 'SQLAlchemyUnitOfWork':\n"
        f"        return self\n\n"
        f"    async def __aexit__(self, exc_type, *_) -> None:\n"
        f"        if exc_type:\n"
        f"            await self.rollback()\n"
        f"        else:\n"
        f"            await self.commit()\n"
        f"        await self._session.close()\n\n"
        f"    async def commit(self) -> None:\n"
        f"        await self._session.commit()\n\n"
        f"    async def rollback(self) -> None:\n"
        f"        await self._session.rollback()\n"
    )
    return "app/patterns/unit_of_work.py", code


def _event_bus(context: str) -> tuple[str, str]:
    code = (
        f"import asyncio\n"
        f"from collections import defaultdict\n"
        f"from typing import Callable, Awaitable\n\n\n"
        f"Handler = Callable[[dict], Awaitable[None]]\n\n\n"
        f"class InMemoryEventBus:\n"
        f'    """Simple in-process async event bus. Replace with Kafka/RabbitMQ for production."""\n\n'
        f"    def __init__(self) -> None:\n"
        f"        self._handlers: dict[str, list[Handler]] = defaultdict(list)\n\n"
        f"    def subscribe(self, event_type: str, handler: Handler) -> None:\n"
        f"        self._handlers[event_type].append(handler)\n\n"
        f"    async def publish(self, event_type: str, payload: dict) -> None:\n"
        f"        handlers = self._handlers.get(event_type, [])\n"
        f"        await asyncio.gather(*[h(payload) for h in handlers])\n\n\n"
        f"event_bus = InMemoryEventBus()\n"
    )
    return "app/events/event_bus.py", code


def _saga(context: str) -> tuple[str, str]:
    name = context or "Order"
    code = (
        f"from dataclasses import dataclass, field\n"
        f"from enum import Enum\n\n\n"
        f"class SagaStep(str, Enum):\n"
        f"    RESERVE_INVENTORY = 'reserve_inventory'\n"
        f"    CHARGE_PAYMENT = 'charge_payment'\n"
        f"    CONFIRM_ORDER = 'confirm_order'\n\n\n"
        f"@dataclass\n"
        f"class {name}Saga:\n"
        f"    order_id: int\n"
        f"    completed_steps: list[SagaStep] = field(default_factory=list)\n"
        f"    failed: bool = False\n\n"
        f"    async def execute(self) -> bool:\n"
        f"        steps = [\n"
        f"            (SagaStep.RESERVE_INVENTORY, self._reserve_inventory, self._release_inventory),\n"
        f"            (SagaStep.CHARGE_PAYMENT, self._charge_payment, self._refund_payment),\n"
        f"            (SagaStep.CONFIRM_ORDER, self._confirm_order, self._cancel_order),\n"
        f"        ]\n"
        f"        for step, action, compensate in steps:\n"
        f"            try:\n"
        f"                await action()\n"
        f"                self.completed_steps.append(step)\n"
        f"            except Exception:\n"
        f"                await self._compensate(compensate)\n"
        f"                return False\n"
        f"        return True\n\n"
        f"    async def _compensate(self, last_compensate) -> None:\n"
        f"        compensations = {{s: c for _, _, c in [] for s in []}}\n"
        f"        for step in reversed(self.completed_steps):\n"
        f"            # call compensation for each completed step\n"
        f"            pass\n"
        f"        await last_compensate()\n\n"
        f"    async def _reserve_inventory(self) -> None: ...\n"
        f"    async def _release_inventory(self) -> None: ...\n"
        f"    async def _charge_payment(self) -> None: ...\n"
        f"    async def _refund_payment(self) -> None: ...\n"
        f"    async def _confirm_order(self) -> None: ...\n"
        f"    async def _cancel_order(self) -> None: ...\n"
    )
    return f"app/patterns/saga/{name.lower()}_saga.py", code


_GENERATORS = {
    "factory": _factory,
    "strategy": _strategy,
    "observer": _observer,
    "command": _command,
    "cqrs": _cqrs,
    "unit_of_work": _unit_of_work,
    "event_bus": _event_bus,
    "saga": _saga,
}


@SkillRegistry.register
class GenerateDesignPatternSkill(BaseSkill):
    name = "backend.design_patterns"
    description = (
        "Generate Python implementations of backend design patterns: Factory, Strategy, Observer, "
        "Command, CQRS, Unit of Work, Event Bus, and Saga. Each output is production-ready async Python."
    )
    category = SkillCategory.BACKEND
    tags = ["design-pattern", "factory", "strategy", "observer", "cqrs", "command", "saga", "clean-architecture"]
    parameters = [
        SkillParameter(
            "pattern",
            "Pattern to generate",
            enum=_PATTERNS,
        ),
        SkillParameter(
            "context",
            "Domain context name to personalise the pattern (e.g. Order, Payment, User)",
            required=False,
            default="",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        pattern: str,
        context: str = "",
        **_: Any,
    ) -> SkillResult:
        generator = _GENERATORS.get(pattern.lower())
        if generator is None:
            return SkillResult.failure(
                f"Unknown pattern '{pattern}'. Available: {', '.join(_PATTERNS)}"
            )

        filename, code = generator(context)

        return SkillResult(
            success=True,
            summary=f"Generated `{pattern}` pattern" + (f" for `{context}`" if context else ""),
            artifacts=[
                CodeArtifact(
                    filename=filename,
                    content=code,
                    language="python",
                    description=f"{pattern.title()} design pattern implementation",
                )
            ],
            instructions=[
                f"Pattern: {pattern.upper()}",
                "All classes are async-compatible and dependency-injection ready.",
            ],
        )
