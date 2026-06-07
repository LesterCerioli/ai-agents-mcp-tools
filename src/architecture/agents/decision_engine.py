"""Solution Architecture Decision Engine — rule-based with optional LLM fallback."""
import re
from typing import TYPE_CHECKING

from src.architecture.agents.base import BaseArchitectureAgent
from src.architecture.context.pipeline_context import PipelineContext
from src.architecture.schemas.requirements import ArchitectureRequirements, SpecificationStatus
from src.architecture.schemas.solution import (
    ArchitecturalDriver,
    ArchitecturePattern,
    ComponentType,
    ArchitectureLayer,
    DecisionComponent,
    RiskFactor,
    SolutionArchitectureDecision,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Static trade-off matrices per pattern
# ---------------------------------------------------------------------------

_TRADE_OFF_MATRICES: dict[ArchitecturePattern, TradeOffMatrix] = {
    ArchitecturePattern.MICROSERVICES: TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.LOW,
        operational_complexity=TradeOffRating.HIGH,
        time_to_market=TradeOffRating.LOW,
        cost=TradeOffRating.HIGH,
    ),
    ArchitecturePattern.MONOLITH: TradeOffMatrix(
        scalability=TradeOffRating.MEDIUM,
        consistency=TradeOffRating.HIGH,
        operational_complexity=TradeOffRating.LOW,
        time_to_market=TradeOffRating.HIGH,
        cost=TradeOffRating.LOW,
    ),
    ArchitecturePattern.SERVERLESS: TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.MEDIUM,
        operational_complexity=TradeOffRating.MEDIUM,
        time_to_market=TradeOffRating.HIGH,
        cost=TradeOffRating.MEDIUM,
    ),
    ArchitecturePattern.EVENT_DRIVEN: TradeOffMatrix(
        scalability=TradeOffRating.VERY_HIGH,
        consistency=TradeOffRating.LOW,
        operational_complexity=TradeOffRating.HIGH,
        time_to_market=TradeOffRating.LOW,
        cost=TradeOffRating.MEDIUM,
    ),
    ArchitecturePattern.LAYERED: TradeOffMatrix(
        scalability=TradeOffRating.MEDIUM,
        consistency=TradeOffRating.HIGH,
        operational_complexity=TradeOffRating.LOW,
        time_to_market=TradeOffRating.HIGH,
        cost=TradeOffRating.LOW,
    ),
    ArchitecturePattern.CQRS: TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.LOW,
        operational_complexity=TradeOffRating.VERY_HIGH,
        time_to_market=TradeOffRating.LOW,
        cost=TradeOffRating.MEDIUM,
    ),
    ArchitecturePattern.HEXAGONAL: TradeOffMatrix(
        scalability=TradeOffRating.MEDIUM,
        consistency=TradeOffRating.HIGH,
        operational_complexity=TradeOffRating.MEDIUM,
        time_to_market=TradeOffRating.MEDIUM,
        cost=TradeOffRating.MEDIUM,
    ),
}

_STRICT_COMPLIANCE_FRAMEWORKS = {"hipaa", "pci-dss", "pci_dss", "pci", "sox", "fedramp"}

_EVENT_SYSTEM_KEYWORDS = {"kafka", "rabbitmq", "sqs", "pubsub", "nats", "kinesis", "eventbridge"}


def _is_high_scale(req: ArchitectureRequirements) -> bool:
    raw = (req.scalability.expected_users or "").lower()
    for pattern, threshold in [
        (r"(\d+)m", 1),
        (r"(\d+)k", 100),
        (r"(\d+),?000,?000", 1),
        (r"(\d+),?000", 100),
    ]:
        m = re.search(pattern, raw)
        if m and int(m.group(1)) >= threshold:
            return True
    return False


def _has_strict_compliance(req: ArchitectureRequirements) -> bool:
    return any(
        f.lower() in _STRICT_COMPLIANCE_FRAMEWORKS
        for f in req.compliance.frameworks
    )


def _has_high_availability(req: ArchitectureRequirements) -> bool:
    uptime = req.availability.target_uptime or ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", uptime)
    return bool(m and float(m.group(1)) >= 99.9)


def _has_event_integration(req: ArchitectureRequirements) -> bool:
    systems = " ".join(req.integration.external_systems).lower()
    patterns = " ".join(req.integration.integration_patterns).lower()
    return any(kw in systems or kw in patterns for kw in _EVENT_SYSTEM_KEYWORDS)


def _is_small_team(req: ArchitectureRequirements) -> bool:
    raw = (req.team_size.engineering_team_size or "").lower()
    return any(kw in raw for kw in ["small", "1-5", "2-5", "startup", "solo", "1-3", "2-3"])


def _is_startup_budget(req: ArchitectureRequirements) -> bool:
    tier = (req.budget.tier or "").lower()
    return any(kw in tier for kw in ["startup", "free", "low", "bootstrap", "seed"])


def _many_integrations(req: ArchitectureRequirements) -> bool:
    return len(req.integration.external_systems) >= 4


def _make_pattern(
    pattern: ArchitecturePattern,
    rationale: str,
    confidence: float,
    trade_offs: list[str],
    is_primary: bool = False,
) -> SolutionPattern:
    return SolutionPattern(
        pattern=pattern,
        rationale=rationale,
        confidence=confidence,
        trade_offs=trade_offs,
        trade_off_matrix=_TRADE_OFF_MATRICES[pattern],
        is_primary=is_primary,
    )


def _default_components(domain: str) -> list[DecisionComponent]:
    return [
        DecisionComponent(
            name="API Gateway",
            type=ComponentType.GATEWAY,
            layer=ArchitectureLayer.APPLICATION,
            responsibility="Entry point for all client requests; handles routing, auth, and rate limiting.",
            technology_hints=["Kong", "AWS API Gateway", "Nginx"],
            protocols=["HTTP/REST", "gRPC"],
        ),
        DecisionComponent(
            name=f"{domain.title()} Service",
            type=ComponentType.SERVICE,
            layer=ArchitectureLayer.DOMAIN,
            responsibility=f"Core business logic for the {domain} domain.",
            technology_hints=["FastAPI", "Node.js", "Spring Boot"],
            protocols=["HTTP/REST"],
        ),
        DecisionComponent(
            name="Primary Database",
            type=ComponentType.DATABASE,
            layer=ArchitectureLayer.INFRASTRUCTURE,
            responsibility="Persistent storage for domain entities.",
            technology_hints=["PostgreSQL", "MySQL"],
            protocols=["TCP"],
        ),
    ]


# ---------------------------------------------------------------------------
# Decision Engine
# ---------------------------------------------------------------------------

class SolutionArchitectureDecisionEngine(BaseArchitectureAgent):
    """
    Evaluates ArchitectureRequirements and produces a SolutionArchitectureDecision.

    Rule-based logic handles clear-cut cases deterministically. When requirements
    are ambiguous (overall_confidence < 0.5 and no LLM available), the engine
    defaults to a conservative LAYERED strategy with appropriate rationale.
    When an LLM is configured, ambiguous cases are escalated to it.
    """

    name = "solution_architecture_decision_engine"
    description = (
        "Evaluates structured architecture requirements and selects the optimal "
        "solution architecture strategy with trade-off analysis and risk assessment."
    )
    system_prompt = (
        "You are a senior solutions architect. Given architecture requirements, "
        "select the best strategy family from: event_driven, microservices, monolith, "
        "serverless, layered, cqrs, hexagonal. Return JSON with keys: "
        "primary_pattern, alternative_patterns (list of 2), rationale, risk_factors (list)."
    )

    async def decide(self, requirements: ArchitectureRequirements) -> SolutionArchitectureDecision:
        decision = self._rule_based_decide(requirements)
        if decision is not None:
            return decision
        if self.llm:
            return await self._llm_decide(requirements)
        return self._conservative_fallback(requirements)

    async def run(self, context: PipelineContext) -> PipelineContext:
        if context.requirements is None:
            return context
        context.decision = await self.decide(context.requirements)
        return context

    # ------------------------------------------------------------------
    # Rule engine
    # ------------------------------------------------------------------

    def _rule_based_decide(
        self, req: ArchitectureRequirements
    ) -> SolutionArchitectureDecision | None:
        high_scale = _is_high_scale(req)
        strict_compliance = _has_strict_compliance(req)
        high_availability = _has_high_availability(req)
        event_integration = _has_event_integration(req)
        small_team = _is_small_team(req)
        startup = _is_startup_budget(req)
        many_integrations = _many_integrations(req)
        real_time = req.integration.real_time is True

        domain = req.domain_boundaries.primary_domain or "application"
        drivers: list[ArchitecturalDriver] = []
        risks: list[RiskFactor] = []

        # Rule 1: high-scale + real-time or event integration → EVENT_DRIVEN
        if (high_scale or real_time) and event_integration:
            drivers.append(ArchitecturalDriver(driver="High throughput with event-driven integrations", weight=0.95, source_dimension="scalability+integration"))
            risks.append(RiskFactor(risk="Eventual consistency may cause stale reads", severity="medium", mitigation="Implement read-model projections and idempotent consumers"))
            risks.append(RiskFactor(risk="Operational complexity of message brokers", severity="medium", mitigation="Use managed services (AWS SQS/SNS, GCP Pub/Sub)"))
            return self._build_decision(
                domain=domain,
                primary=_make_pattern(ArchitecturePattern.EVENT_DRIVEN, "High-scale real-time workload with existing event integrations mandates event-driven architecture.", 0.92, ["Eventual consistency", "Higher operational overhead"], True),
                alternatives=[
                    _make_pattern(ArchitecturePattern.CQRS, "CQRS complements event-driven by separating read and write models.", 0.78, ["Complexity", "Dual models to maintain"]),
                    _make_pattern(ArchitecturePattern.MICROSERVICES, "Microservices provide independent scaling if events are not central.", 0.65, ["Network overhead", "Service coordination"]),
                ],
                drivers=drivers, risks=risks, req=req, is_rule_based=True,
            )

        # Rule 2: strict compliance + small team → MONOLITH (auditable, simple)
        if strict_compliance and small_team:
            drivers.append(ArchitecturalDriver(driver="Strict regulatory compliance with limited engineering capacity", weight=0.9, source_dimension="compliance+team_size"))
            risks.append(RiskFactor(risk="Monolith may become a bottleneck at scale", severity="low", mitigation="Design with modular boundaries for future extraction"))
            risks.append(RiskFactor(risk="Compliance audit trail must be centralized", severity="high", mitigation="Implement structured logging and immutable audit log table"))
            return self._build_decision(
                domain=domain,
                primary=_make_pattern(ArchitecturePattern.MONOLITH, "Strict compliance (HIPAA/PCI) with a small team favors a monolith: single audit surface, simpler data governance.", 0.88, ["Limited horizontal scalability", "Deployment risk at scale"], True),
                alternatives=[
                    _make_pattern(ArchitecturePattern.LAYERED, "Layered architecture enforces separation of concerns while staying simple.", 0.75, ["Tight layer coupling over time"]),
                    _make_pattern(ArchitecturePattern.HEXAGONAL, "Hexagonal isolates domain logic from compliance adapters.", 0.60, ["Higher initial complexity"]),
                ],
                drivers=drivers, risks=risks, req=req, is_rule_based=True,
            )

        # Rule 3: startup + small team → MONOLITH or SERVERLESS
        if startup and small_team:
            drivers.append(ArchitecturalDriver(driver="Speed-to-market and cost efficiency for early-stage product", weight=0.85, source_dimension="budget+team_size"))
            risks.append(RiskFactor(risk="Technical debt accumulation in monolith", severity="low", mitigation="Enforce module boundaries from day one"))
            primary = ArchitecturePattern.SERVERLESS if not high_scale else ArchitecturePattern.MONOLITH
            primary_rationale = (
                "Serverless eliminates infrastructure management, reducing operational burden for a small startup team."
                if primary == ArchitecturePattern.SERVERLESS
                else "Monolith enables fast iteration with a small team on a constrained budget."
            )
            return self._build_decision(
                domain=domain,
                primary=_make_pattern(primary, primary_rationale, 0.85, ["Vendor lock-in (serverless)", "Scale ceiling (monolith)"], True),
                alternatives=[
                    _make_pattern(ArchitecturePattern.MONOLITH, "Monolith offers predictable costs and full control.", 0.70, ["Scale ceiling"]),
                    _make_pattern(ArchitecturePattern.LAYERED, "Layered adds structure with minimal overhead.", 0.55, ["May feel over-engineered for MVP"]),
                ],
                drivers=drivers, risks=risks, req=req, is_rule_based=True,
            )

        # Rule 4: enterprise + high availability + many integrations → MICROSERVICES
        if high_availability and many_integrations and not startup:
            drivers.append(ArchitecturalDriver(driver="High availability SLA with multiple external system integrations", weight=0.9, source_dimension="availability+integration"))
            risks.append(RiskFactor(risk="Distributed tracing and observability overhead", severity="medium", mitigation="Adopt OpenTelemetry and a centralized observability platform"))
            risks.append(RiskFactor(risk="Network partition tolerance complexity", severity="high", mitigation="Implement circuit breakers and bulkhead patterns"))
            return self._build_decision(
                domain=domain,
                primary=_make_pattern(ArchitecturePattern.MICROSERVICES, "High availability requirements with multiple integrations demand independently deployable services for targeted scaling and resilience.", 0.90, ["Operational complexity", "Eventual consistency", "High infrastructure cost"], True),
                alternatives=[
                    _make_pattern(ArchitecturePattern.EVENT_DRIVEN, "Event-driven decouples integrations and improves resilience.", 0.72, ["Message broker operational burden"]),
                    _make_pattern(ArchitecturePattern.HEXAGONAL, "Hexagonal architecture cleanly separates integration adapters.", 0.60, ["Does not address scalability directly"]),
                ],
                drivers=drivers, risks=risks, req=req, is_rule_based=True,
            )

        # Rule 5: high scale only (no events, no compliance) → MICROSERVICES
        if high_scale and not strict_compliance and not startup:
            drivers.append(ArchitecturalDriver(driver="Large user base requiring independent service scaling", weight=0.88, source_dimension="scalability"))
            risks.append(RiskFactor(risk="Inter-service communication latency", severity="medium", mitigation="Use async messaging for non-critical paths; gRPC for low-latency sync calls"))
            return self._build_decision(
                domain=domain,
                primary=_make_pattern(ArchitecturePattern.MICROSERVICES, "High user scale requires horizontal scaling of individual services independently.", 0.85, ["Operational complexity", "Distributed system challenges"], True),
                alternatives=[
                    _make_pattern(ArchitecturePattern.EVENT_DRIVEN, "Event-driven handles peak load spikes gracefully.", 0.70, ["Eventual consistency"]),
                    _make_pattern(ArchitecturePattern.SERVERLESS, "Serverless auto-scales without capacity planning.", 0.58, ["Cold starts", "Vendor lock-in"]),
                ],
                drivers=drivers, risks=risks, req=req, is_rule_based=True,
            )

        # Rule 6: moderate requirements, no strong signals → LAYERED
        if not high_scale and not strict_compliance and not many_integrations:
            drivers.append(ArchitecturalDriver(driver="Balanced requirements without dominant constraints", weight=0.75, source_dimension="overall"))
            risks.append(RiskFactor(risk="Layer coupling may hinder future refactoring", severity="low", mitigation="Enforce dependency rules with linting (e.g. ArchUnit)"))
            return self._build_decision(
                domain=domain,
                primary=_make_pattern(ArchitecturePattern.LAYERED, "Moderate, balanced requirements fit a layered architecture: simple, well-understood, and easy to maintain.", 0.80, ["Horizontal scaling limits", "Risk of anemic domain model"], True),
                alternatives=[
                    _make_pattern(ArchitecturePattern.HEXAGONAL, "Hexagonal improves testability and adapter isolation.", 0.68, ["Steeper initial learning curve"]),
                    _make_pattern(ArchitecturePattern.MONOLITH, "Monolith minimizes complexity for smaller teams.", 0.55, ["Deployment coupling"]),
                ],
                drivers=drivers, risks=risks, req=req, is_rule_based=True,
            )

        return None

    def _conservative_fallback(self, req: ArchitectureRequirements) -> SolutionArchitectureDecision:
        domain = req.domain_boundaries.primary_domain or "application"
        return self._build_decision(
            domain=domain,
            primary=_make_pattern(ArchitecturePattern.LAYERED, "Requirements are ambiguous. Layered architecture is chosen as the safest conservative baseline — it can be refactored as constraints become clearer.", 0.60, ["May not scale to enterprise load"], True),
            alternatives=[
                _make_pattern(ArchitecturePattern.HEXAGONAL, "Hexagonal provides better testability and future adapter flexibility.", 0.50, ["Higher initial complexity"]),
                _make_pattern(ArchitecturePattern.MONOLITH, "Monolith maximizes simplicity while requirements are still being defined.", 0.45, ["Scale ceiling"]),
            ],
            drivers=[ArchitecturalDriver(driver="Ambiguous requirements — conservative choice", weight=0.5, source_dimension="overall")],
            risks=[RiskFactor(risk="Architecture may not match final requirements", severity="medium", mitigation="Re-run decision engine after clarification rounds")],
            req=req,
            is_rule_based=False,
        )

    async def _llm_decide(self, req: ArchitectureRequirements) -> SolutionArchitectureDecision:
        import json
        domain = req.domain_boundaries.primary_domain or "application"
        prompt = (
            f"Architecture requirements:\n{req.model_dump_json(indent=2)}\n\n"
            "Select the best architecture strategy. Return JSON with: "
            "primary_pattern (string), alternative_patterns (list of 2 strings), "
            "rationale (string), risk_factors (list of {risk, severity, mitigation})."
        )
        try:
            response = await self.llm.chat(prompt, system_prompt=self.system_prompt)  # type: ignore[union-attr]
            data = json.loads(response)
            primary_name = data.get("primary_pattern", "layered")
            alt_names: list[str] = data.get("alternative_patterns", ["hexagonal", "monolith"])
            rationale: str = data.get("rationale", "")
            raw_risks: list[dict] = data.get("risk_factors", [])

            def _parse_pattern(name: str) -> ArchitecturePattern:
                try:
                    return ArchitecturePattern(name.lower())
                except ValueError:
                    return ArchitecturePattern.LAYERED

            primary_pat = _parse_pattern(primary_name)
            risks = [
                RiskFactor(risk=r.get("risk", ""), severity=r.get("severity", "medium"), mitigation=r.get("mitigation", ""))
                for r in raw_risks
            ]
            return self._build_decision(
                domain=domain,
                primary=_make_pattern(primary_pat, rationale, 0.75, [], True),
                alternatives=[_make_pattern(_parse_pattern(n), f"Alternative considered by LLM.", 0.60, []) for n in alt_names[:2]],
                drivers=[ArchitecturalDriver(driver="LLM-evaluated multi-constraint requirements", weight=0.75, source_dimension="overall")],
                risks=risks,
                req=req,
                is_rule_based=False,
            )
        except Exception:
            return self._conservative_fallback(req)

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------

    def _build_decision(
        self,
        domain: str,
        primary: SolutionPattern,
        alternatives: list[SolutionPattern],
        drivers: list[ArchitecturalDriver],
        risks: list[RiskFactor],
        req: ArchitectureRequirements,
        is_rule_based: bool = True,
    ) -> SolutionArchitectureDecision:
        patterns = [primary, *alternatives]
        rationale = (
            f"Primary strategy: {primary.pattern.value}. {primary.rationale} "
            f"Alternatives considered: {', '.join(p.pattern.value for p in alternatives)}."
        )
        return SolutionArchitectureDecision(
            domain=domain,
            patterns=patterns,
            components=_default_components(domain),
            external_integrations=req.integration.external_systems,
            rationale=rationale,
            architectural_drivers=drivers,
            risk_factors=risks,
            decision_confidence=primary.confidence * req.overall_confidence if req.overall_confidence > 0 else primary.confidence,
            is_rule_based=is_rule_based,
        )
