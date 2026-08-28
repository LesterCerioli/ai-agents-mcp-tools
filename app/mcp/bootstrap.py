"""Bootstrap helpers that assemble the default architecture agent registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.architecture.agents import (
    BusinessObjectiveParserAgent,
    DesignPartnerOrchestrator,
    HexagonalDesignPartnerAgent,
    MicroservicesDesignPartnerAgent,
    MonolithArchitectureDesignPartnerAgent,
    MonolithDesignPartnerAgent,
    SolutionArchitectureDecisionEngine,
    SolutionArchitectureValidationAgent,
    SolutionFlowDiagramAgent,
)
from app.architecture.agents.base import BaseArchitectureAgent
from app.mcp.registry import AgentRegistry

if TYPE_CHECKING:
    from app.llm.base import BaseLLMProvider


def default_architecture_agents(
    llm: BaseLLMProvider | None = None,
) -> list[BaseArchitectureAgent]:
    """Instantiate every architecture agent from Tasks 1-3."""
    return [
        BusinessObjectiveParserAgent(llm),
        SolutionArchitectureDecisionEngine(llm),
        SolutionFlowDiagramAgent(llm),
        SolutionArchitectureValidationAgent(llm),
        MicroservicesDesignPartnerAgent(llm),
        HexagonalDesignPartnerAgent(llm),
        MonolithDesignPartnerAgent(llm),
        MonolithArchitectureDesignPartnerAgent(llm),
        DesignPartnerOrchestrator(llm),
    ]


def create_architecture_registry(
    llm: BaseLLMProvider | None = None,
    persistence_path: str | None = None,
) -> AgentRegistry:
    """Create a registry with all default architecture agents registered."""
    registry = AgentRegistry(persistence_path=persistence_path)
    for agent in default_architecture_agents(llm):
        registry.register(agent)
    return registry
