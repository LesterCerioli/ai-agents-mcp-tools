from collections import defaultdict

from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.requirements import ArchitectureRequirements, SpecificationStatus
from app.architecture.schemas.solution import (
    AntiPatternViolation,
    ArchitectureGap,
    ArchitecturePattern,
    ComponentType,
    IssueSeverity,
    RequirementCoverage,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
    ValidationReport,
)

_DISTRIBUTED_PATTERNS = {
    ArchitecturePattern.MICROSERVICES,
    ArchitecturePattern.EVENT_DRIVEN,
    ArchitecturePattern.CQRS,
}

_HIGH_SCALE_KEYWORDS = {"million", "1m", "2m", "5m", "10m", "100k", "500k", "1,000,000"}


def _is_high_scale_req(req: ArchitectureRequirements) -> bool:
    raw = (req.scalability.expected_users or "").lower()
    return any(kw in raw for kw in _HIGH_SCALE_KEYWORDS)


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    """Detect cycles in a directed graph via DFS."""
    graph: dict[str, list[str]] = defaultdict(list)
    for src, tgt in edges:
        graph[src].append(tgt)

    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for neighbour in graph[node]:
            if neighbour not in visited:
                if dfs(neighbour):
                    return True
            elif neighbour in in_stack:
                return True
        in_stack.discard(node)
        return False

    for node in list(graph):
        if node not in visited:
            if dfs(node):
                return True
    return False


class SolutionArchitectureValidationAgent(BaseArchitectureAgent):

    name = "solution_architecture_validation"
    description = (
        "Cross-checks the generated solution architecture (flow diagram + decision) against "
        "the original parsed business requirements. Acts as the quality gate of the Solution "
        "Architecture Layer before outputs are passed to System Architecture agents."
    )
    system_prompt = ""

    def validate(
        self,
        requirements: ArchitectureRequirements,
        diagram: SolutionFlowDiagram,
        decision: SolutionArchitectureDecision,
    ) -> ValidationReport:
        coverages = self._check_coverage(requirements, decision, diagram)
        gaps = self._derive_gaps(coverages, requirements, decision)
        violations = self._detect_anti_patterns(decision, diagram, requirements)

        blockers = [
            x for x in [*gaps, *violations] if x.severity == IssueSeverity.BLOCKER
        ]
        passed = len(blockers) == 0

        confidence = self._compute_confidence(coverages, violations, decision)

        corrections = list(
            dict.fromkeys(
                [g.recommended_correction for g in gaps]
                + [v.recommended_correction for v in violations]
            )
        )

        re_eval = len(blockers) > 0
        re_eval_context = (
            (
                f"Re-evaluation required due to {len(blockers)} blocker(s): "
                + "; ".join(
                    g.description
                    for g in [*gaps, *violations]
                    if g.severity == IssueSeverity.BLOCKER
                )
            )
            if re_eval
            else ""
        )

        return ValidationReport(
            decision_id=decision.decision_id,
            passed=passed,
            requirement_coverages=coverages,
            gaps=gaps,
            anti_pattern_violations=violations,
            confidence_score=confidence,
            recommended_corrections=corrections,
            re_evaluation_required=re_eval,
            re_evaluation_context=re_eval_context,
        )

    async def run(self, context: PipelineContext) -> PipelineContext:
        if context.requirements is None or context.decision is None or context.diagram is None:
            return context
        report = self.validate(context.requirements, context.diagram, context.decision)
        context.metadata["validation_report"] = report
        return context

    
    def _check_coverage(
        self,
        req: ArchitectureRequirements,
        decision: SolutionArchitectureDecision,
        diagram: SolutionFlowDiagram,
    ) -> list[RequirementCoverage]:
        all_nodes = (
            diagram.context_view.nodes
            + diagram.container_view.nodes
            + diagram.component_view.nodes
        )
        node_types = {n.type for n in all_nodes}
        primary = decision.primary_pattern

        coverages: list[RequirementCoverage] = []

        
        if req.scalability.status == SpecificationStatus.SPECIFIED:
            scalable_patterns = {
                ArchitecturePattern.MICROSERVICES,
                ArchitecturePattern.EVENT_DRIVEN,
                ArchitecturePattern.SERVERLESS,
                ArchitecturePattern.CQRS,
            }
            covered = primary is not None and primary.pattern in scalable_patterns
            has_cache = ComponentType.CACHE in node_types
            if not covered and not has_cache:
                coverages.append(RequirementCoverage(
                    dimension="scalability",
                    covered=False,
                    coverage_notes="Primary pattern does not directly address high-scale requirement and no cache layer is present.",
                    severity=IssueSeverity.WARNING,
                ))
            else:
                coverages.append(RequirementCoverage(
                    dimension="scalability",
                    covered=True,
                    coverage_notes="Pattern or cache layer addresses scalability requirement.",
                    severity=IssueSeverity.INFO,
                ))
        else:
            coverages.append(RequirementCoverage(
                dimension="scalability",
                covered=True,
                coverage_notes="Scalability not specified — no coverage required.",
                severity=IssueSeverity.INFO,
            ))

        
        if req.availability.status == SpecificationStatus.SPECIFIED:
            has_gateway = ComponentType.GATEWAY in node_types
            covered = has_gateway or (primary is not None and primary.pattern in {
                ArchitecturePattern.MICROSERVICES, ArchitecturePattern.EVENT_DRIVEN
            })
            coverages.append(RequirementCoverage(
                dimension="availability",
                covered=covered,
                coverage_notes=(
                    "Gateway component present or distributed pattern addresses availability."
                    if covered
                    else "No gateway or HA-oriented component detected."
                ),
                severity=IssueSeverity.INFO if covered else IssueSeverity.WARNING,
            ))
        else:
            coverages.append(RequirementCoverage(
                dimension="availability",
                covered=True,
                coverage_notes="Availability not specified — no coverage required.",
                severity=IssueSeverity.INFO,
            ))

        
        if req.compliance.status == SpecificationStatus.SPECIFIED and req.compliance.frameworks:
            has_gateway = ComponentType.GATEWAY in node_types
            covered = has_gateway
            coverages.append(RequirementCoverage(
                dimension="compliance",
                covered=covered,
                coverage_notes=(
                    "Security boundary (gateway) present to enforce compliance controls."
                    if covered
                    else "Compliance frameworks specified but no security boundary (gateway) detected."
                ),
                severity=IssueSeverity.INFO if covered else IssueSeverity.BLOCKER,
            ))
        else:
            coverages.append(RequirementCoverage(
                dimension="compliance",
                covered=True,
                coverage_notes="Compliance not specified — no coverage required.",
                severity=IssueSeverity.INFO,
            ))

        
        if req.integration.status == SpecificationStatus.SPECIFIED and req.integration.external_systems:
            diagram_external_labels = {
                n.label.lower()
                for n in all_nodes
                if n.type == ComponentType.EXTERNAL
            }
            uncovered = [
                s for s in req.integration.external_systems
                if s.lower() not in diagram_external_labels
            ]
            covered = len(uncovered) == 0
            coverages.append(RequirementCoverage(
                dimension="integration",
                covered=covered,
                coverage_notes=(
                    "All external integrations are represented in the diagram."
                    if covered
                    else f"Missing external integrations in diagram: {', '.join(uncovered)}."
                ),
                severity=IssueSeverity.INFO if covered else IssueSeverity.WARNING,
            ))
        else:
            coverages.append(RequirementCoverage(
                dimension="integration",
                covered=True,
                coverage_notes="Integration not specified — no coverage required.",
                severity=IssueSeverity.INFO,
            ))

        
        if req.domain_boundaries.status == SpecificationStatus.SPECIFIED:
            primary_domain = (req.domain_boundaries.primary_domain or "").lower()
            domain_matched = primary_domain and any(
                primary_domain in n.label.lower() or primary_domain in n.responsibility.lower()
                for n in all_nodes
            )
            covered = bool(domain_matched)
            coverages.append(RequirementCoverage(
                dimension="domain_boundaries",
                covered=covered,
                coverage_notes=(
                    "Primary domain is reflected in diagram components."
                    if covered
                    else f"Primary domain '{primary_domain}' not found in any diagram component."
                ),
                severity=IssueSeverity.INFO if covered else IssueSeverity.WARNING,
            ))
        else:
            coverages.append(RequirementCoverage(
                dimension="domain_boundaries",
                covered=True,
                coverage_notes="Domain boundaries not specified — no coverage required.",
                severity=IssueSeverity.INFO,
            ))

        return coverages

    

    def _derive_gaps(
        self,
        coverages: list[RequirementCoverage],
        req: ArchitectureRequirements,
        decision: SolutionArchitectureDecision,
    ) -> list[ArchitectureGap]:
        gaps: list[ArchitectureGap] = []
        for cov in coverages:
            if not cov.covered:
                gaps.append(ArchitectureGap(
                    description=cov.coverage_notes,
                    severity=cov.severity,
                    dimension=cov.dimension,
                    recommended_correction=self._correction_for_dimension(cov.dimension, req, decision),
                ))
        return gaps

    def _correction_for_dimension(
        self,
        dimension: str,
        req: ArchitectureRequirements,
        decision: SolutionArchitectureDecision,
    ) -> str:
        corrections = {
            "scalability": (
                "Add a cache layer (Redis/Memcached) or switch to a scalable pattern "
                "(microservices, event-driven, serverless) to address scalability requirements."
            ),
            "availability": (
                "Introduce an API Gateway or load balancer component to ensure high-availability "
                "traffic routing and failover."
            ),
            "compliance": (
                f"Add a security boundary (API Gateway with auth/rate-limiting) to enforce "
                f"compliance controls for: {', '.join(req.compliance.frameworks)}."
            ),
            "integration": (
                "Ensure all required external systems are represented as EXTERNAL nodes in the "
                "diagram and connected to the appropriate application layer components."
            ),
            "domain_boundaries": (
                f"Add a domain service component that explicitly names the "
                f"'{req.domain_boundaries.primary_domain}' domain to reflect bounded-context boundaries."
            ),
        }
        return corrections.get(dimension, "Review and address the identified coverage gap.")

    
    def _detect_anti_patterns(
        self,
        decision: SolutionArchitectureDecision,
        diagram: SolutionFlowDiagram,
        req: ArchitectureRequirements,
    ) -> list[AntiPatternViolation]:
        violations: list[AntiPatternViolation] = []
        primary = decision.primary_pattern

        
        all_edges = [(e.source_id, e.target_id) for e in diagram.component_view.edges]
        if _has_cycle(all_edges):
            violations.append(AntiPatternViolation(
                pattern_name="circular_dependency",
                description="Circular dependency detected in the component view diagram.",
                severity=IssueSeverity.BLOCKER,
                recommended_correction=(
                    "Break the cycle by introducing an abstraction layer (e.g. shared event bus, "
                    "mediator pattern) or inverting a dependency via an interface."
                ),
            ))

        
        all_nodes = (
            diagram.context_view.nodes
            + diagram.container_view.nodes
            + diagram.component_view.nodes
        )
        node_types = {n.type for n in all_nodes}
        is_distributed = primary is not None and primary.pattern in _DISTRIBUTED_PATTERNS
        has_compliance = (
            req.compliance.status == SpecificationStatus.SPECIFIED
            and bool(req.compliance.frameworks)
        )
        if (is_distributed or has_compliance) and ComponentType.GATEWAY not in node_types:
            violations.append(AntiPatternViolation(
                pattern_name="missing_security_boundary",
                description=(
                    "No API Gateway or security boundary component found in a "
                    f"{'compliance-sensitive' if has_compliance else 'distributed'} architecture."
                ),
                severity=IssueSeverity.BLOCKER,
                recommended_correction=(
                    "Add an API Gateway (Kong, AWS API Gateway, Nginx) as the single entry point "
                    "to enforce authentication, rate-limiting, and routing policies."
                ),
            ))

        
        if is_distributed:
            service_nodes = [n for n in all_nodes if n.type == ComponentType.SERVICE]
            unique_services = {n.id for n in service_nodes}
            if len(unique_services) == 1:
                violations.append(AntiPatternViolation(
                    pattern_name="monolithic_bottleneck",
                    description=(
                        f"Only one service component found despite a "
                        f"'{primary.pattern.value}' pattern selection, creating a monolithic bottleneck."
                    ),
                    severity=IssueSeverity.BLOCKER,
                    recommended_correction=(
                        "Decompose the single service into multiple bounded-context services, "
                        "each owning its own data store and deployed independently."
                    ),
                ))

        
        if _is_high_scale_req(req) and ComponentType.CACHE not in node_types:
            violations.append(AntiPatternViolation(
                pattern_name="missing_cache_for_high_scale",
                description=(
                    f"High-scale requirement detected ({req.scalability.expected_users}) "
                    "but no cache layer is present in the architecture."
                ),
                severity=IssueSeverity.WARNING,
                recommended_correction=(
                    "Add a distributed cache layer (Redis, Memcached, or AWS ElastiCache) "
                    "in front of the primary database to reduce read latency at scale."
                ),
            ))

        
        if primary is not None and primary.pattern == ArchitecturePattern.CQRS:
            db_nodes = [n for n in all_nodes if n.type == ComponentType.DATABASE]
            unique_dbs = {n.id for n in db_nodes}
            if len(unique_dbs) < 2:
                violations.append(AntiPatternViolation(
                    pattern_name="cqrs_without_database_segregation",
                    description=(
                        "CQRS pattern selected but fewer than 2 database components detected. "
                        "CQRS requires separate read and write data stores."
                    ),
                    severity=IssueSeverity.BLOCKER,
                    recommended_correction=(
                        "Add separate read (query) and write (command) databases. "
                        "For example: PostgreSQL for commands, Elasticsearch or read-replica for queries."
                    ),
                ))

        
        if req.availability.status == SpecificationStatus.SPECIFIED:
            gateway_nodes = [n for n in all_nodes if n.type == ComponentType.GATEWAY]
            unique_gateways = {n.id for n in gateway_nodes}
            uptime = req.availability.target_uptime or ""
            is_high_availability = "99.9" in uptime or "99.99" in uptime or "100" in uptime
            if is_high_availability and len(unique_gateways) == 1:
                violations.append(AntiPatternViolation(
                    pattern_name="single_point_of_failure",
                    description=(
                        f"High availability target '{uptime}' specified but only a single gateway "
                        "component exists, creating a single point of failure."
                    ),
                    severity=IssueSeverity.WARNING,
                    recommended_correction=(
                        "Deploy the gateway in an active-active or active-passive configuration "
                        "with a load balancer in front (e.g. AWS ALB, GCP Cloud Load Balancing)."
                    ),
                ))

        return violations

    
    def _compute_confidence(
        self,
        coverages: list[RequirementCoverage],
        violations: list[AntiPatternViolation],
        decision: SolutionArchitectureDecision,
    ) -> float:
        covered_count = sum(1 for c in coverages if c.covered)
        coverage_ratio = covered_count / max(len(coverages), 1)

        blocker_penalty = sum(
            0.25 for v in violations if v.severity == IssueSeverity.BLOCKER
        )
        warning_penalty = sum(
            0.08 for v in violations if v.severity == IssueSeverity.WARNING
        )

        base = decision.decision_confidence * coverage_ratio
        score = max(0.0, base - blocker_penalty - warning_penalty)
        return round(min(score, 1.0), 4)
