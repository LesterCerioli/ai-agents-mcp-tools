from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.lifecycle import (
    OPERATIONAL_STATES,
    AgentState,
    HealthStatus,
    assert_transition,
)

if TYPE_CHECKING:
    from app.llm.base import BaseLLMProvider


class BaseArchitectureAgent(ABC):
    """Standardized interface for every architecture agent in the MCP layer.

    Concrete agents declare ``name``, ``description`` and ``capabilities`` and
    implement :meth:`run`. The lifecycle methods (``initialize``, ``shutdown``,
    ``health_check``) are provided by this base class and drive a per-agent
    state machine; subclasses customize behaviour via the ``_on_initialize``,
    ``_on_shutdown`` and ``_compute_health`` hooks.
    """

    name: str
    description: str
    capabilities: ClassVar[list[str]] = []
    system_prompt: str = ""

    def __init__(self, llm: "BaseLLMProvider | None" = None):
        self.llm = llm
        self._state = AgentState.UNREGISTERED
        self._last_error: str | None = None

    @property
    def agent_id(self) -> str:
        return self.name

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @abstractmethod
    async def run(self, context: PipelineContext) -> PipelineContext: ...

    async def initialize(self) -> None:
        """Transition UNREGISTERED -> INITIALIZING -> READY."""
        self._transition(AgentState.INITIALIZING)
        try:
            await self._on_initialize()
        except Exception as exc:
            self._last_error = f"initialization failed: {exc}"
            self._transition(AgentState.SHUTTING_DOWN)
            self._transition(AgentState.TERMINATED)
            raise
        self._transition(AgentState.READY)

    async def shutdown(self) -> None:
        """Transition any operational state -> SHUTTING_DOWN -> TERMINATED."""
        self._transition(AgentState.SHUTTING_DOWN)
        try:
            await self._on_shutdown()
        except Exception as exc:
            self._last_error = f"shutdown failed: {exc}"
        finally:
            self._transition(AgentState.TERMINATED)

    async def health_check(self) -> HealthStatus:
        return self._compute_health()

    def activate(self) -> None:
        self._transition(AgentState.RUNNING)

    def pause(self) -> None:
        self._transition(AgentState.PAUSED)

    def resume(self) -> None:
        self._transition(AgentState.RUNNING)

    def _transition(self, target: AgentState) -> None:
        assert_transition(self._state, target)
        self._state = target

    async def _on_initialize(self) -> None:
        return None

    async def _on_shutdown(self) -> None:
        return None

    def _compute_health(self) -> HealthStatus:
        if self._state in OPERATIONAL_STATES:
            return HealthStatus.DEGRADED if self._last_error else HealthStatus.HEALTHY
        if self._state in (AgentState.INITIALIZING, AgentState.SHUTTING_DOWN):
            return HealthStatus.DEGRADED
        return HealthStatus.UNHEALTHY

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} state={self._state.value}>"
