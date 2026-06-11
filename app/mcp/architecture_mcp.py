"""
Architecture MCP Server — exposes the architecture pipeline as individual, controllable tools.

Flow between agents:
  parse_requirements                    → BusinessObjectiveParserAgent
  clarify_requirements (0-N times)      → BusinessObjectiveParserAgent.clarify()
  decide_architecture                   → DecisionEngine + SolutionFlowDiagram + ValidationAgent
  select_design_partner                 → DesignPartnerOrchestrator
       ├─ HexagonalDesignPartnerAgent   (pattern == hexagonal)
       ├─ MicroservicesDesignPartner    (microservices | event_driven | cqrs)
       └─ MonolithDesignPartner         (monolith | layered | serverless)
  → caller then invokes /mcp/backend and /mcp/frontend with the recommended tool calls

Tools:
  - parse_requirements
  - clarify_requirements
  - decide_architecture
  - select_design_partner
  - get_session_state

Resources:
  - architecture://sessions
  - architecture://patterns
"""
import json
from typing import TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from app.architecture.context.pipeline_context import PipelineContext
    from app.llm.base import BaseLLMProvider


def create_architecture_mcp(
    sessions: "dict[str, PipelineContext]",
    llm: "BaseLLMProvider | None" = None,
) -> FastMCP:
    mcp = FastMCP("architecture-mcp")

    # ── Resources ─────────────────────────────────────────────────────────────

    @mcp.resource("architecture://sessions")
    async def active_sessions() -> str:
        return json.dumps(list(sessions.keys()))

    @mcp.resource("architecture://patterns")
    async def supported_patterns() -> str:
        return json.dumps([
            {
                "pattern": "hexagonal",
                "description": "Ports & Adapters — domain isolation, infrastructure independence",
                "design_partner": "HexagonalDesignPartnerAgent",
            },
            {
                "pattern": "microservices",
                "description": "Distributed bounded contexts with independent deployments",
                "design_partner": "MicroservicesDesignPartnerAgent",
            },
            {
                "pattern": "event_driven",
                "description": "Async event bus with producer/consumer services",
                "design_partner": "MicroservicesDesignPartnerAgent",
            },
            {
                "pattern": "cqrs",
                "description": "Command/Query Responsibility Segregation with separate read/write stores",
                "design_partner": "MicroservicesDesignPartnerAgent",
            },
            {
                "pattern": "monolith",
                "description": "Single deployable unit — layered, modular, or vertical slices",
                "design_partner": "MonolithDesignPartnerAgent",
            },
            {
                "pattern": "layered",
                "description": "Classic n-tier layered architecture",
                "design_partner": "MonolithDesignPartnerAgent",
            },
            {
                "pattern": "serverless",
                "description": "Function-as-a-service with managed infrastructure",
                "design_partner": "MonolithDesignPartnerAgent",
            },
        ], indent=2)

    # ── Stage 1 ───────────────────────────────────────────────────────────────

    @mcp.tool()
    async def parse_requirements(
        objective: str,
        session_id: str | None = None,
    ) -> str:
        """
        Stage 1 — Parse a business objective into structured architecture requirements.

        Always call this first. Creates a new session (or resumes one) and returns a
        session_id that must be passed to all subsequent architecture tools.

        Args:
            objective: Natural-language description of what to build.
            session_id: Optional existing session ID to resume from.

        Returns JSON with:
          session_id           — use in all subsequent calls
          domain               — inferred primary domain
          is_complete          — whether requirements are fully specified
          clarification_questions — questions to answer when is_complete is False
          overall_confidence   — 0.0–1.0
          next_action          — "clarify_requirements" | "decide_architecture"
        """
        from app.architecture.agents.business_objective_parser import BusinessObjectiveParserAgent
        from app.architecture.context.pipeline_context import PipelineContext

        agent = BusinessObjectiveParserAgent(llm=llm)

        if session_id and session_id in sessions:
            ctx = sessions[session_id]
        else:
            ctx = PipelineContext()
            sessions[ctx.session_id] = ctx

        requirements = await agent.parse(objective, ctx)

        next_action = (
            "clarify_requirements"
            if not requirements.is_complete and requirements.clarification_questions
            else "decide_architecture"
        )

        return json.dumps({
            "session_id": ctx.session_id,
            "domain": requirements.domain_boundaries.primary_domain or "",
            "is_complete": requirements.is_complete,
            "clarification_questions": requirements.clarification_questions,
            "overall_confidence": requirements.overall_confidence,
            "next_action": next_action,
        }, indent=2)

    # ── Stage 1b ──────────────────────────────────────────────────────────────

    @mcp.tool()
    async def clarify_requirements(
        session_id: str,
        answer: str,
    ) -> str:
        """
        Stage 1b — Provide an answer to a clarification question to refine requirements.

        Call this when parse_requirements returns is_complete=False.
        May be called multiple times until is_complete=True.

        Args:
            session_id: Session ID from parse_requirements.
            answer: Answer to the first pending clarification question.

        Returns JSON with:
          session_id
          is_complete
          remaining_questions
          overall_confidence
          next_action          — "clarify_requirements" | "decide_architecture"
        """
        from app.architecture.agents.business_objective_parser import BusinessObjectiveParserAgent

        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({
                "error": f"Session '{session_id}' not found. Call parse_requirements first."
            })

        agent = BusinessObjectiveParserAgent(llm=llm)

        try:
            requirements = await agent.clarify(answer, ctx)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})

        next_action = (
            "clarify_requirements"
            if not requirements.is_complete and requirements.clarification_questions
            else "decide_architecture"
        )

        return json.dumps({
            "session_id": session_id,
            "is_complete": requirements.is_complete,
            "remaining_questions": requirements.clarification_questions,
            "overall_confidence": requirements.overall_confidence,
            "next_action": next_action,
        }, indent=2)

    # ── Stage 2–4 ─────────────────────────────────────────────────────────────

    @mcp.tool()
    async def decide_architecture(
        session_id: str,
    ) -> str:
        """
        Stages 2–4 — Run the architecture decision engine, generate the solution flow
        diagram, and validate the decision against the requirements.

        Requires parse_requirements (or clarify_requirements until is_complete=True)
        to have been called first.

        Args:
            session_id: Session ID from parse_requirements.

        Returns JSON with:
          decision_id          — reference ID for the architecture decision
          primary_pattern      — selected architecture pattern
          primary_pattern_confidence
          alternative_patterns — other considered patterns with confidence scores
          components           — key system components with type, layer, technology hints
          validation_passed    — whether the decision passed the validation quality gate
          validation_gaps      — list of gaps found (each with description and severity)
          design_confidence    — 0.0–1.0
          next_action          — "select_design_partner"
        """
        from app.architecture.agents.decision_engine import SolutionArchitectureDecisionEngine
        from app.architecture.agents.solution_flow_diagram import SolutionFlowDiagramAgent
        from app.architecture.agents.validation_agent import SolutionArchitectureValidationAgent

        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})
        if ctx.requirements is None:
            return json.dumps({
                "error": "Requirements not parsed yet. Call parse_requirements first."
            })

        ctx = await SolutionArchitectureDecisionEngine(llm=llm).run(ctx)
        ctx = await SolutionFlowDiagramAgent(llm=llm).run(ctx)
        ctx = await SolutionArchitectureValidationAgent(llm=llm).run(ctx)
        sessions[session_id] = ctx

        decision = ctx.decision
        if decision is None:
            return json.dumps({"error": "Architecture decision could not be generated."})

        primary = decision.primary_pattern
        report = ctx.metadata.get("validation_report")

        components_out = [
            {
                "name": c.name,
                "type": c.type.value,
                "layer": c.layer.value,
                "responsibility": c.responsibility,
                "technology_hints": c.technology_hints,
            }
            for c in decision.components
        ]

        gaps_out = []
        if report and report.gaps:
            gaps_out = [
                {"description": g.description, "severity": g.severity.value}
                for g in report.gaps
            ]

        return json.dumps({
            "session_id": session_id,
            "decision_id": decision.decision_id,
            "primary_pattern": primary.pattern.value if primary else None,
            "primary_pattern_confidence": primary.confidence if primary else 0.0,
            "alternative_patterns": [
                {"pattern": p.pattern.value, "confidence": p.confidence}
                for p in decision.alternative_patterns
            ],
            "components": components_out,
            "validation_passed": report.passed if report else True,
            "validation_gaps": gaps_out,
            "design_confidence": decision.decision_confidence,
            "next_action": "select_design_partner",
        }, indent=2)

    # ── Stage 5 ───────────────────────────────────────────────────────────────

    @mcp.tool()
    async def select_design_partner(
        session_id: str,
    ) -> str:
        """
        Stage 5 — Activate the correct Design Partner Agent based on the architecture
        decision produced by decide_architecture.

        Partner selection rules:
          hexagonal                      → HexagonalDesignPartnerAgent
          microservices | event_driven | cqrs → MicroservicesDesignPartnerAgent
          monolith | layered | serverless → MonolithDesignPartnerAgent

        Args:
            session_id: Session ID from decide_architecture.

        Returns JSON with:
          active_partner                  — which design partner was activated
          design_summary                  — rationale from the selected design
          recommended_backend_invocations — ordered list of /mcp/backend tool calls
                                            the caller should make next, with params
          recommended_frontend_agent      — "nextjs" (only frontend agent available)
          recommended_frontend_invocations— suggested /mcp/frontend tool calls
          next_actions                    — human-readable ordered call list
        """
        from app.architecture.agents.system.design_partner_orchestrator import DesignPartnerOrchestrator

        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})
        if ctx.decision is None:
            return json.dumps({
                "error": "Architecture decision missing. Call decide_architecture first."
            })
        if ctx.diagram is None:
            return json.dumps({
                "error": "Solution diagram missing. Call decide_architecture first."
            })

        ctx = await DesignPartnerOrchestrator(llm=llm).run(ctx)
        sessions[session_id] = ctx

        system_design = ctx.system_design
        if system_design is None:
            return json.dumps({"error": "System design could not be generated."})

        active_partner = system_design.active_partner
        design_summary = ""
        backend_invocations: list[dict] = []

        if system_design.hexagonal_architecture_design:
            hd = system_design.hexagonal_architecture_design
            design_summary = hd.rationale
            for svc in hd.application_core.domain_services:
                resource = (
                    svc.name.lower()
                    .replace("domainservice", "")
                    .replace(" ", "_")
                    .strip("_")
                )
                backend_invocations.append({
                    "mcp_server": "/mcp/backend",
                    "tool": "generate_backend_code",
                    "params": {"resource": resource, "skills": ["endpoint", "repo"]},
                    "reason": f"FastAPI endpoint + repository adapter for domain service {svc.name}",
                })

        elif system_design.microservices_design:
            md = system_design.microservices_design
            design_summary = md.rationale
            for bc in md.bounded_contexts:
                resource = bc.subdomain.lower().replace(" ", "_").replace("-", "_")
                backend_invocations.append({
                    "mcp_server": "/mcp/backend",
                    "tool": "generate_backend_code",
                    "params": {"resource": resource, "skills": ["endpoint", "model", "repo"]},
                    "reason": f"Full backend stack for bounded context {bc.name}",
                })
            domain_name = (
                ctx.decision.domain
                if ctx.decision
                else "app"
            )
            backend_invocations.append({
                "mcp_server": "/mcp/backend",
                "tool": "generate_docker_setup",
                "params": {"app_name": domain_name, "services": "postgres,redis"},
                "reason": "Docker Compose for microservices infrastructure",
            })

        elif system_design.monolith_design:
            mnd = system_design.monolith_design
            design_summary = mnd.rationale
            for module in mnd.modules:
                resource = module.name.lower().replace(" ", "_").replace("-", "_")
                backend_invocations.append({
                    "mcp_server": "/mcp/backend",
                    "tool": "generate_backend_code",
                    "params": {"resource": resource, "skills": ["endpoint", "model"]},
                    "reason": f"Backend for monolith module {module.name}",
                })
            domain_name = ctx.decision.domain if ctx.decision else "app"
            backend_invocations.append({
                "mcp_server": "/mcp/backend",
                "tool": "generate_docker_setup",
                "params": {"app_name": domain_name, "services": "postgres"},
                "reason": "Docker Compose for monolith deployment",
            })

        domain = (
            ctx.requirements.domain_boundaries.primary_domain
            if ctx.requirements and ctx.requirements.domain_boundaries
            else "app"
        ) or "app"

        frontend_invocations = [
            {
                "mcp_server": "/mcp/frontend",
                "tool": "generate_ui_components",
                "params": {
                    "skill": "page",
                    "route": f"/{domain}/dashboard",
                    "description": f"Main dashboard for the {domain} system",
                },
                "reason": f"Generate Next.js dashboard page for the {domain} domain",
            },
            {
                "mcp_server": "/mcp/frontend",
                "tool": "generate_ui_components",
                "params": {
                    "skill": "layout",
                    "name": f"{domain.capitalize()}Layout",
                    "description": f"Root layout for {domain}",
                },
                "reason": "Generate Next.js root layout",
            },
            {
                "mcp_server": "/mcp/frontend",
                "tool": "setup_deployment",
                "params": {"project_name": domain, "framework": "nextjs"},
                "reason": "Generate Vercel deployment configuration",
            },
        ]

        next_actions = (
            [f"/mcp/backend → {inv['tool']}({inv['params']}) — {inv['reason']}"
             for inv in backend_invocations]
            + [f"/mcp/frontend → {inv['tool']}({inv['params']}) — {inv['reason']}"
               for inv in frontend_invocations]
        )

        return json.dumps({
            "session_id": session_id,
            "active_partner": active_partner,
            "design_summary": design_summary,
            "recommended_backend_invocations": backend_invocations,
            "recommended_frontend_agent": "nextjs",
            "recommended_frontend_invocations": frontend_invocations,
            "next_actions": next_actions,
        }, indent=2)

    # ── State inspector ───────────────────────────────────────────────────────

    @mcp.tool()
    async def get_session_state(session_id: str) -> str:
        """
        Inspect the current state of an architecture session — which stages are complete
        and what tool to call next.

        Args:
            session_id: Session ID to inspect.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        stages_completed: list[str] = []
        if ctx.requirements:
            stages_completed.append("parse_requirements")
            if ctx.requirements.is_complete:
                stages_completed.append("requirements_complete")
        if ctx.decision:
            stages_completed.append("decide_architecture")
        if ctx.diagram:
            stages_completed.append("solution_diagram_generated")
        if ctx.metadata.get("validation_report"):
            stages_completed.append("validation_complete")
        if ctx.system_design:
            stages_completed.append("select_design_partner")
        if ctx.workflow_output:
            stages_completed.append("workflow_complete")

        if ctx.system_design:
            next_step = "invoke /mcp/backend and /mcp/frontend tools"
        elif ctx.decision:
            next_step = "select_design_partner"
        elif ctx.requirements and ctx.requirements.is_complete:
            next_step = "decide_architecture"
        elif ctx.requirements and not ctx.requirements.is_complete:
            next_step = "clarify_requirements"
        else:
            next_step = "parse_requirements"

        report = ctx.metadata.get("validation_report")

        return json.dumps({
            "session_id": session_id,
            "stages_completed": stages_completed,
            "next_step": next_step,
            "has_requirements": ctx.requirements is not None,
            "requirements_complete": (
                ctx.requirements.is_complete if ctx.requirements else False
            ),
            "pending_clarification_questions": (
                ctx.requirements.clarification_questions
                if ctx.requirements and not ctx.requirements.is_complete
                else []
            ),
            "has_decision": ctx.decision is not None,
            "primary_pattern": (
                ctx.decision.primary_pattern.pattern.value
                if ctx.decision and ctx.decision.primary_pattern
                else None
            ),
            "has_diagram": ctx.diagram is not None,
            "validation_passed": report.passed if report else None,
            "has_system_design": ctx.system_design is not None,
            "active_design_partner": (
                ctx.system_design.active_partner if ctx.system_design else None
            ),
            "turn_count": ctx.turn_count(),
        }, indent=2)

    return mcp


class ArchitectureMCPServer:
    """Wrapper that holds the FastMCP instance and exposes the ASGI app."""

    def __init__(
        self,
        sessions: "dict[str, PipelineContext]",
        llm: "BaseLLMProvider | None" = None,
    ) -> None:
        self._mcp = create_architecture_mcp(sessions, llm=llm)

    def sse_app(self):
        return self._mcp.sse_app()
