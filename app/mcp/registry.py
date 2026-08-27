"""MCP agent registry: registration, capability discovery, lifecycle and recovery.

This is the foundation of the MCP orchestration layer — no architecture agent
can participate in the pipeline without being registered here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Sequence
from pathlib import Path

from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.lifecycle import (
    OPERATIONAL_STATES,
    STABLE_STATES,
    AgentState,
    HealthStatus,
)

logger = logging.getLogger(__name__)

_SNAPSHOT_VERSION = 1


class RegistryError(Exception):
    """Base error for registry failures."""


class DuplicateAgentError(RegistryError):
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent '{agent_id}' is already registered.")


class UnknownAgentError(RegistryError, KeyError):
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent '{agent_id}' is not registered.")


class AgentRegistry:
    """Registers architecture agents and manages their lifecycle state.

    Args:
        persistence_path: optional JSON file used to snapshot the registry so
            registered agents can be recovered after an MCP restart.
    """

    def __init__(self, persistence_path: str | Path | None = None) -> None:
        self._agents: dict[str, BaseArchitectureAgent] = {}
        self._persistence_path = Path(persistence_path) if persistence_path else None
        self._recovery_targets: dict[str, AgentState] = {}
        self._snapshot: dict[str, object] | None = None
        self._lock = asyncio.Lock()
        if self._persistence_path is not None and self._persistence_path.exists():
            self._load_snapshot()

    @property
    def persistence_path(self) -> Path | None:
        return self._persistence_path

    @property
    def agent_ids(self) -> list[str]:
        return list(self._agents)

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, agent_id: object) -> bool:
        return agent_id in self._agents

    def states(self) -> dict[str, AgentState]:
        return {aid: agent.state for aid, agent in self._agents.items()}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, agent: BaseArchitectureAgent) -> None:
        if agent.agent_id in self._agents:
            raise DuplicateAgentError(agent.agent_id)
        self._agents[agent.agent_id] = agent
        persisted_state = self._persisted_state(agent.agent_id)
        if persisted_state in STABLE_STATES:
            self._recovery_targets[agent.agent_id] = persisted_state
        else:
            self._recovery_targets.pop(agent.agent_id, None)
        logger.info(
            "Registered agent '%s' with capabilities %s", agent.agent_id, agent.capabilities
        )
        self._persist()

    def deregister(self, agent_id: str) -> None:
        if agent_id not in self._agents:
            raise UnknownAgentError(agent_id)
        del self._agents[agent_id]
        self._recovery_targets.pop(agent_id, None)
        logger.info("Deregistered agent '%s'", agent_id)
        self._persist()

    def get(self, agent_id: str) -> BaseArchitectureAgent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise UnknownAgentError(agent_id) from None

    # ------------------------------------------------------------------
    # Capability-based discovery
    # ------------------------------------------------------------------

    def discover(
        self,
        capability: str,
        *,
        only_operational: bool = True,
    ) -> list[BaseArchitectureAgent]:
        """Return agents declaring ``capability``.

        By default only agents in an operational state (ready / running /
        paused) are returned, since uninitialized agents cannot join a
        pipeline. Pass ``only_operational=False`` to inspect raw declarations.
        """
        matches = [
            agent
            for agent in self._agents.values()
            if capability in agent.capabilities
            and (not only_operational or agent.state in OPERATIONAL_STATES)
        ]
        return sorted(matches, key=lambda a: a.agent_id)

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    async def initialize(self, agent_id: str) -> bool:
        agent = self.get(agent_id)
        return await self._initialize_agent(agent)

    async def initialize_all(
        self,
        critical_path: Sequence[str] | None = None,
    ) -> dict[str, bool]:
        """Initialize agents concurrently; critical-path agents go first, in order.

        Returns a mapping of ``agent_id -> success`` for every registered agent.
        """
        async with self._lock:
            results: dict[str, bool] = {}

            critical_ids = [aid for aid in (critical_path or []) if aid in self._agents]
            for agent_id in critical_ids:
                results[agent_id] = await self._initialize_agent(self._agents[agent_id])

            remaining = [a for a in self._agents.values() if a.agent_id not in results]
            outcomes = await asyncio.gather(
                *(self._initialize_agent(a) for a in remaining),
                return_exceptions=True,
            )
            for agent, outcome in zip(remaining, outcomes):
                if isinstance(outcome, BaseException):
                    logger.error("Initialization of '%s' failed: %s", agent.agent_id, outcome)
                    results[agent.agent_id] = False
                else:
                    results[agent.agent_id] = outcome

            self._persist()
            return results

    async def recover(self) -> dict[str, AgentState]:
        """Drive agents with a persisted stable state back to that state."""
        async with self._lock:
            for agent_id, target_state in list(self._recovery_targets.items()):
                agent = self._agents.get(agent_id)
                if agent is None:
                    self._recovery_targets.pop(agent_id, None)
                    continue
                try:
                    await self._recover_agent(agent, target_state)
                except Exception as exc:
                    logger.error("Recovery of '%s' failed: %s", agent_id, exc)
            self._persist()
            return {aid: a.state for aid, a in self._agents.items()}

    async def activate(self, agent_id: str) -> None:
        self.get(agent_id).activate()
        self._persist()

    async def pause(self, agent_id: str) -> None:
        self.get(agent_id).pause()
        self._persist()

    async def resume(self, agent_id: str) -> None:
        self.get(agent_id).resume()
        self._persist()

    async def shutdown(self, agent_id: str) -> None:
        agent = self.get(agent_id)
        await self._shutdown_agent(agent)
        self._persist()

    async def shutdown_all(self) -> dict[str, bool]:
        async with self._lock:
            operational = [a for a in self._agents.values() if a.state in OPERATIONAL_STATES]
            outcomes = await asyncio.gather(
                *(self._shutdown_agent(a) for a in operational),
                return_exceptions=True,
            )
            results = {
                agent.agent_id: not isinstance(outcome, BaseException)
                for agent, outcome in zip(operational, outcomes)
            }
            self._persist()
            return results

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    async def health_check(self, agent_id: str) -> HealthStatus:
        return await self.get(agent_id).health_check()

    async def health_check_all(self) -> dict[str, HealthStatus]:
        statuses = await asyncio.gather(*(agent.health_check() for agent in self._agents.values()))
        return dict(zip(self._agents, statuses))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _initialize_agent(self, agent: BaseArchitectureAgent) -> bool:
        if agent.state == AgentState.TERMINATED:
            logger.warning("Skipping initialization of terminated agent '%s'", agent.agent_id)
            return False
        if agent.state != AgentState.UNREGISTERED:
            return True
        try:
            await agent.initialize()
        except Exception as exc:
            logger.error("Initialization of '%s' failed: %s", agent.agent_id, exc)
            return False
        return True

    async def _shutdown_agent(self, agent: BaseArchitectureAgent) -> None:
        if agent.state in (*OPERATIONAL_STATES, AgentState.INITIALIZING):
            await agent.shutdown()

    async def _recover_agent(self, agent: BaseArchitectureAgent, target: AgentState) -> None:
        if agent.state == AgentState.UNREGISTERED:
            await agent.initialize()
        elif agent.state == target:
            return
        if agent.state == AgentState.READY and target in (AgentState.RUNNING, AgentState.PAUSED):
            agent.activate()
        if agent.state == AgentState.RUNNING and target == AgentState.PAUSED:
            agent.pause()

    def _persisted_state(self, agent_id: str) -> AgentState | None:
        if self._snapshot is None:
            return None
        agents = self._snapshot.get("agents")
        entry = agents.get(agent_id) if isinstance(agents, dict) else None
        if not isinstance(entry, dict):
            return None
        try:
            return AgentState(str(entry["state"]))
        except (KeyError, ValueError):
            return None

    def _persist(self) -> None:
        if self._persistence_path is None:
            return
        payload = {
            "version": _SNAPSHOT_VERSION,
            "agents": {
                aid: {
                    "class_name": type(agent).__name__,
                    "capabilities": list(agent.capabilities),
                    "state": agent.state.value,
                }
                for aid, agent in self._agents.items()
            },
        }
        try:
            path = self._persistence_path
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            logger.error(
                "Failed to persist registry snapshot to %s: %s", self._persistence_path, exc
            )

    def _load_snapshot(self) -> None:
        assert self._persistence_path is not None
        try:
            raw = json.loads(self._persistence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(
                "Failed to load registry snapshot from %s: %s", self._persistence_path, exc
            )
            self._snapshot = None
            return
        self._snapshot = raw if isinstance(raw, dict) else None
