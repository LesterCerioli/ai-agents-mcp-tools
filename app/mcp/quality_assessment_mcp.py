import json
from typing import TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from app.architecture.context.pipeline_context import PipelineContext
    from app.agents.quality_assessment_agent import ArchitectureQualityAssessmentAgent
    from app.llm.base import BaseLLMProvider


def create_quality_assessment_mcp(
    sessions: "dict[str, PipelineContext]",
    agent: "ArchitectureQualityAssessmentAgent",
    llm: "BaseLLMProvider | None" = None,
) -> FastMCP:
    mcp = FastMCP("quality-assessment-mcp")

    @mcp.resource("quality-assessment://attributes")
    async def quality_attributes() -> str:
        return json.dumps([
            {
                "id": "maintainability",
                "name": "Maintainability",
                "description": "Ease of changing the system; driven by SRP and OCP compliance.",
                "weight": 0.25,
                "solid_focus": ["SRP", "OCP"],
            },
            {
                "id": "extensibility",
                "name": "Extensibility",
                "description": "Ability to add behaviour without modifying existing code.",
                "weight": 0.20,
                "solid_focus": ["OCP", "DIP"],
            },
            {
                "id": "testability",
                "name": "Testability",
                "description": "Ease of writing isolated, dependency-injected tests.",
                "weight": 0.20,
                "solid_focus": ["ISP", "DIP"],
            },
            {
                "id": "scalability",
                "name": "Scalability",
                "description": "Ability to handle increased workload; driven by architectural patterns.",
                "weight": 0.20,
                "solid_focus": [],
            },
            {
                "id": "security_boundary_clarity",
                "name": "Security Boundary Clarity",
                "description": "Clarity of security enforcement points across architectural layers.",
                "weight": 0.15,
                "solid_focus": ["SRP"],
            },
        ], indent=2)

    @mcp.resource("quality-assessment://sessions")
    async def sessions_with_reports() -> str:
        sids = [
            sid for sid, ctx in sessions.items()
            if ctx.metadata.get("quality_assessment_report") is not None
        ]
        return json.dumps(sids)

    @mcp.tool()
    async def assess_architecture_quality(session_id: str) -> str:
        """
        Trigger a holistic architecture quality assessment for an existing session.

        Combines SOLID compliance findings, design pattern recommendations, and the
        system architecture design to produce a quality report across five attributes:
        Maintainability, Extensibility, Testability, Scalability, and Security Boundary Clarity.

        Each attribute is scored 0–100. The weighted overall health score determines
        a grade: Excellent (≥80), Good (≥60), Needs Improvement (≥40), Critical (<40).

        For best results, call analyze_solid_compliance and recommend_design_patterns
        on this session before triggering quality assessment.

        Args:
            session_id: Session ID from parse_requirements / decide_architecture.

        Returns JSON with:
          session_id, report_id, overall_health_score, health_grade,
          attribute_scores (5 attributes), layer_quality_breakdown (4 layers),
          improvement_actions (top 5), analysis_summary, next_action.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})
        if ctx.decision is None and ctx.system_design is None:
            return json.dumps({
                "error": (
                    "No architecture design found. "
                    "Call decide_architecture or select_design_partner first."
                )
            })

        solid_report = ctx.metadata.get("solid_compliance_report")
        pattern_report = ctx.metadata.get("pattern_recommendation_report")

        try:
            report = await agent.assess(ctx, solid_report=solid_report, pattern_report=pattern_report)
        except Exception as exc:
            return json.dumps({"error": f"Quality assessment failed: {exc}"})

        ctx.metadata["quality_assessment_report"] = report
        sessions[session_id] = ctx

        next_action = (
            "review_improvement_actions"
            if report.overall_health_score < 80
            else "proceed_to_code_generation"
        )

        return json.dumps({
            "session_id": session_id,
            "report_id": report.report_id,
            "overall_health_score": report.overall_health_score,
            "health_grade": report.health_grade,
            "architecture_pattern": report.architecture_pattern,
            "attribute_scores": [
                {
                    "attribute": s.attribute.value,
                    "score": s.score,
                    "justification": s.justification,
                }
                for s in report.attribute_scores
            ],
            "layer_quality_breakdown": [
                {
                    "layer": lq.layer,
                    "score": lq.score,
                    "issues_count": len(lq.issues),
                    "strengths_count": len(lq.strengths),
                }
                for lq in report.layer_quality_breakdown
            ],
            "improvement_actions": [
                {
                    "rank": a.rank,
                    "title": a.title,
                    "affected_attribute": a.affected_attribute.value,
                    "effort": a.effort.value,
                    "impact": a.impact.value,
                    "priority_score": a.priority_score,
                }
                for a in report.improvement_actions
            ],
            "analysis_summary": report.analysis_summary,
            "next_action": next_action,
        }, indent=2)

    @mcp.tool()
    async def get_quality_report(session_id: str) -> str:
        """
        Retrieve the full architecture quality report for a session.

        Must call assess_architecture_quality first. Returns the complete report
        including per-attribute justifications, full layer breakdowns with issues
        and strengths, and detailed improvement action descriptions.

        Args:
            session_id: Session ID with an existing quality assessment report.

        Returns the full ArchitectureQualityReport as JSON.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        report = ctx.metadata.get("quality_assessment_report")
        if report is None:
            return json.dumps({
                "error": (
                    "No quality report found. "
                    "Call assess_architecture_quality first."
                ),
                "session_id": session_id,
            })

        return json.dumps({
            "session_id": session_id,
            "report_id": report.report_id,
            "architecture_pattern": report.architecture_pattern,
            "overall_health_score": report.overall_health_score,
            "health_grade": report.health_grade,
            "analysis_summary": report.analysis_summary,
            "attribute_scores": [
                {
                    "attribute": s.attribute.value,
                    "score": s.score,
                    "justification": s.justification,
                }
                for s in report.attribute_scores
            ],
            "layer_quality_breakdown": [
                {
                    "layer": lq.layer,
                    "score": lq.score,
                    "issues": lq.issues,
                    "strengths": lq.strengths,
                }
                for lq in report.layer_quality_breakdown
            ],
            "improvement_actions": [
                {
                    "rank": a.rank,
                    "title": a.title,
                    "description": a.description,
                    "affected_attribute": a.affected_attribute.value,
                    "effort": a.effort.value,
                    "impact": a.impact.value,
                    "priority_score": a.priority_score,
                }
                for a in report.improvement_actions
            ],
        }, indent=2)

    @mcp.tool()
    async def get_layer_quality_breakdown(session_id: str, layer: str) -> str:
        """
        Retrieve the quality breakdown for a specific architectural layer.

        Args:
            session_id: Session ID with an existing quality assessment report.
            layer: One of: presentation, application, domain, infrastructure (case-insensitive).

        Returns the LayerQualityScore with issues and strengths.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        report = ctx.metadata.get("quality_assessment_report")
        if report is None:
            return json.dumps({
                "error": "No quality report found. Call assess_architecture_quality first."
            })

        layer_lower = layer.lower()
        valid_layers = ["presentation", "application", "domain", "infrastructure"]
        if layer_lower not in valid_layers:
            return json.dumps({
                "error": f"Unknown layer '{layer}'. Valid: {valid_layers}"
            })

        lq = next(
            (lq for lq in report.layer_quality_breakdown if lq.layer == layer_lower), None
        )
        if lq is None:
            return json.dumps({"error": f"No data found for layer '{layer}'."})

        return json.dumps({
            "layer": lq.layer,
            "score": lq.score,
            "issues": lq.issues,
            "strengths": lq.strengths,
        }, indent=2)

    @mcp.tool()
    async def get_improvement_actions(session_id: str) -> str:
        """
        Retrieve the top-5 ranked improvement actions for a session.

        Actions are ranked by priority score (impact / effort ratio). Each action
        includes an effort estimate (low/medium/high), impact estimate, and full description.

        Args:
            session_id: Session ID with an existing quality assessment report.

        Returns the ranked improvement action list as JSON.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        report = ctx.metadata.get("quality_assessment_report")
        if report is None:
            return json.dumps({
                "error": "No quality report found. Call assess_architecture_quality first."
            })

        return json.dumps({
            "session_id": session_id,
            "overall_health_score": report.overall_health_score,
            "health_grade": report.health_grade,
            "improvement_actions": [
                {
                    "rank": a.rank,
                    "title": a.title,
                    "description": a.description,
                    "affected_attribute": a.affected_attribute.value,
                    "effort": a.effort.value,
                    "impact": a.impact.value,
                    "priority_score": a.priority_score,
                }
                for a in report.improvement_actions
            ],
        }, indent=2)

    return mcp


class QualityAssessmentMCPServer:
    def __init__(
        self,
        sessions: "dict[str, PipelineContext]",
        agent: "ArchitectureQualityAssessmentAgent",
        llm: "BaseLLMProvider | None" = None,
    ) -> None:
        self._mcp = create_quality_assessment_mcp(sessions, agent, llm=llm)

    def sse_app(self):
        return self._mcp.sse_app()
