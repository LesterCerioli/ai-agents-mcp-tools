import json
from typing import TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from app.architecture.context.pipeline_context import PipelineContext
    from app.agents.solid_agent import SOLIDPrinciplesEnforcerAgent
    from app.llm.base import BaseLLMProvider


def create_solid_mcp(
    sessions: "dict[str, PipelineContext]",
    solid_agent: "SOLIDPrinciplesEnforcerAgent",
    llm: "BaseLLMProvider | None" = None,
) -> FastMCP:
    mcp = FastMCP("solid-mcp")

    @mcp.resource("solid://principles")
    async def solid_principles() -> str:
        return json.dumps([
            {
                "id": "srp",
                "name": "Single Responsibility Principle",
                "description": "A component should have only one reason to change.",
                "skill": "solid.srp_analyze",
            },
            {
                "id": "ocp",
                "name": "Open/Closed Principle",
                "description": "Components should be open for extension but closed for modification.",
                "skill": "solid.ocp_analyze",
            },
            {
                "id": "lsp",
                "name": "Liskov Substitution Principle",
                "description": "Implementations must be substitutable for their abstractions.",
                "skill": "solid.lsp_analyze",
            },
            {
                "id": "isp",
                "name": "Interface Segregation Principle",
                "description": "Clients must not be forced to depend on interfaces they do not use.",
                "skill": "solid.isp_analyze",
            },
            {
                "id": "dip",
                "name": "Dependency Inversion Principle",
                "description": "High-level modules must depend on abstractions, not concretions.",
                "skill": "solid.dip_analyze",
            },
        ], indent=2)

    @mcp.resource("solid://sessions")
    async def solid_sessions() -> str:
        sessions_with_reports = [
            sid for sid, ctx in sessions.items()
            if ctx.metadata.get("solid_compliance_report") is not None
        ]
        return json.dumps(sessions_with_reports)

    @mcp.tool()
    async def analyze_solid_compliance(session_id: str) -> str:
        """
        Trigger SOLID Principles analysis for an existing architecture session.

        Evaluates all five SOLID principles (SRP, OCP, LSP, ISP, DIP) against the
        design artifact produced by the architecture pipeline. Stores the compliance
        report in the session for retrieval via get_solid_report.

        The agent automatically selects the appropriate skill per principle and
        produces a SOLIDComplianceReport with per-principle results, affected
        components, actionable recommendations, and cross-principle correlations.

        Requires decide_architecture (and optionally select_design_partner) to have
        been called first on this session.

        Args:
            session_id: Session ID from parse_requirements / decide_architecture.

        Returns JSON with:
          session_id
          overall_compliance     — compliant | warning | violation
          components_analyzed    — number of design elements evaluated
          architecture_pattern   — detected pattern (microservices, hexagonal, monolith, …)
          violations_count       — number of principles with VIOLATION level
          warnings_count         — number of principles with WARNING level
          cross_correlations     — number of cross-principle cascades detected
          analysis_summary       — human-readable overview
          principle_results      — list of per-principle results with details
          next_action            — suggested follow-up
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})
        if ctx.decision is None and ctx.system_design is None:
            return json.dumps({
                "error": "No architecture design found. Call decide_architecture or select_design_partner first."
            })

        try:
            report = await solid_agent.analyze(ctx)
        except Exception as exc:
            return json.dumps({"error": f"SOLID analysis failed: {exc}"})

        ctx.metadata["solid_compliance_report"] = report
        sessions[session_id] = ctx

        from app.architecture.schemas.solid import ComplianceLevel
        violations_count = sum(
            1 for r in report.principle_results
            if r.compliance_level == ComplianceLevel.VIOLATION
        )
        warnings_count = sum(
            1 for r in report.principle_results
            if r.compliance_level == ComplianceLevel.WARNING
        )

        next_action = (
            "review_principle_results"
            if violations_count > 0
            else "proceed_to_code_generation"
        )

        return json.dumps({
            "session_id": session_id,
            "report_id": report.report_id,
            "overall_compliance": report.overall_compliance.value,
            "components_analyzed": report.components_analyzed,
            "architecture_pattern": report.architecture_pattern,
            "violations_count": violations_count,
            "warnings_count": warnings_count,
            "cross_correlations": len(report.cross_principle_correlations),
            "analysis_summary": report.analysis_summary,
            "principle_results": [
                {
                    "principle": r.principle.value,
                    "compliance_level": r.compliance_level.value,
                    "summary": r.summary,
                    "affected_components_count": len(r.affected_components),
                    "recommendations_count": len(r.recommendations),
                }
                for r in report.principle_results
            ],
            "next_action": next_action,
        }, indent=2)

    @mcp.tool()
    async def get_solid_report(session_id: str) -> str:
        """
        Retrieve the full SOLID compliance report for a session.

        Must call analyze_solid_compliance first. Returns the complete report
        including per-principle results, affected components, recommendations,
        and cross-principle correlations.

        Args:
            session_id: Session ID with an existing SOLID compliance report.

        Returns the full SOLIDComplianceReport as JSON.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        report = ctx.metadata.get("solid_compliance_report")
        if report is None:
            return json.dumps({
                "error": "No SOLID report found. Call analyze_solid_compliance first.",
                "session_id": session_id,
            })

        return json.dumps({
            "session_id": session_id,
            "report_id": report.report_id,
            "overall_compliance": report.overall_compliance.value,
            "components_analyzed": report.components_analyzed,
            "architecture_pattern": report.architecture_pattern,
            "analysis_summary": report.analysis_summary,
            "principle_results": [
                {
                    "principle": r.principle.value,
                    "compliance_level": r.compliance_level.value,
                    "summary": r.summary,
                    "affected_components": [
                        {
                            "component_name": ac.component_name,
                            "violation_description": ac.violation_description,
                            "layer": ac.layer,
                            "component_type": ac.component_type,
                        }
                        for ac in r.affected_components
                    ],
                    "recommendations": r.recommendations,
                }
                for r in report.principle_results
            ],
            "cross_principle_correlations": [
                {
                    "primary_principle": c.primary_principle.value,
                    "cascaded_principles": [p.value for p in c.cascaded_principles],
                    "component_name": c.component_name,
                    "description": c.description,
                }
                for c in report.cross_principle_correlations
            ],
        }, indent=2)

    @mcp.tool()
    async def get_principle_result(session_id: str, principle: str) -> str:
        """
        Retrieve the detailed result for a specific SOLID principle.

        Args:
            session_id: Session ID with an existing SOLID compliance report.
            principle: One of: srp, ocp, lsp, isp, dip (case-insensitive).

        Returns the full PrincipleResult including affected components and recommendations.
        """
        from app.architecture.schemas.solid import SOLIDPrinciple

        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        report = ctx.metadata.get("solid_compliance_report")
        if report is None:
            return json.dumps({
                "error": "No SOLID report found. Call analyze_solid_compliance first."
            })

        try:
            p = SOLIDPrinciple(principle.lower())
        except ValueError:
            return json.dumps({
                "error": f"Unknown principle '{principle}'. Valid: srp, ocp, lsp, isp, dip"
            })

        result = report.get_result(p)
        if result is None:
            return json.dumps({"error": f"No result found for principle '{principle}'."})

        return json.dumps({
            "principle": result.principle.value,
            "compliance_level": result.compliance_level.value,
            "summary": result.summary,
            "affected_components": [
                {
                    "component_name": ac.component_name,
                    "violation_description": ac.violation_description,
                    "layer": ac.layer,
                    "component_type": ac.component_type,
                }
                for ac in result.affected_components
            ],
            "recommendations": result.recommendations,
        }, indent=2)

    return mcp


class SOLIDMCPServer:
    def __init__(
        self,
        sessions: "dict[str, PipelineContext]",
        solid_agent: "SOLIDPrinciplesEnforcerAgent",
        llm: "BaseLLMProvider | None" = None,
    ) -> None:
        self._mcp = create_solid_mcp(sessions, solid_agent, llm=llm)

    def sse_app(self):
        return self._mcp.sse_app()
