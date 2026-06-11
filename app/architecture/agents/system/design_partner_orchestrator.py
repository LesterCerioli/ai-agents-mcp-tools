from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.agents.system.hexagonal_design_partner import HexagonalDesignPartnerAgent
from app.architecture.agents.system.microservices_design_partner import MicroservicesDesignPartnerAgent
from app.architecture.agents.system.monolith_design_partner import MonolithDesignPartnerAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.solution import ArchitecturePattern

_MICROSERVICES_PATTERNS = {
    ArchitecturePattern.MICROSERVICES,
    ArchitecturePattern.EVENT_DRIVEN,
    ArchitecturePattern.CQRS,
}
_HEXAGONAL_PATTERNS = {ArchitecturePattern.HEXAGONAL}
_MONOLITH_PATTERNS = {
    ArchitecturePattern.MONOLITH,
    ArchitecturePattern.LAYERED,
    ArchitecturePattern.SERVERLESS,
}


class DesignPartnerOrchestrator(BaseArchitectureAgent):

    name = "design_partner_orchestrator"
    description = (
        "Selects and activates the correct system architecture design partner based on the "
        "primary pattern from the solution architecture decision. "
        "Distributed patterns (microservices, event-driven, CQRS) → MicroservicesDesignPartner. "
        "Domain-centric (hexagonal) → HexagonalDesignPartner. "
        "Low-complexity (monolith, layered, serverless) → MonolithDesignPartner."
    )
    system_prompt = ""

    def __init__(self, llm=None, service_mesh_threshold: int = 5):
        super().__init__(llm)
        self._microservices = MicroservicesDesignPartnerAgent(llm, service_mesh_threshold)
        self._hexagonal = HexagonalDesignPartnerAgent(llm)
        self._monolith = MonolithDesignPartnerAgent(llm)

    def _select_partner(self, pattern: ArchitecturePattern) -> BaseArchitectureAgent:
        if pattern in _MICROSERVICES_PATTERNS:
            return self._microservices
        if pattern in _HEXAGONAL_PATTERNS:
            return self._hexagonal
        return self._monolith

    async def run(self, context: PipelineContext) -> PipelineContext:
        if context.decision is None or context.requirements is None:
            return context
        primary = context.decision.primary_pattern
        if primary is None:
            return context
        partner = self._select_partner(primary.pattern)
        return await partner.run(context)
