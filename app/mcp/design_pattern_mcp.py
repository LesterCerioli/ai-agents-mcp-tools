import json
from typing import TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from app.architecture.context.pipeline_context import PipelineContext
    from app.agents.design_pattern_agent import DesignPatternRecommenderAgent
    from app.llm.base import BaseLLMProvider


def create_design_pattern_mcp(
    sessions: "dict[str, PipelineContext]",
    agent: "DesignPatternRecommenderAgent",
    llm: "BaseLLMProvider | None" = None,
) -> FastMCP:
    mcp = FastMCP("design-pattern-mcp")

    @mcp.resource("design-patterns://catalog")
    async def pattern_catalog() -> str:
        return json.dumps({
            "gof_creational": [
                "abstract_factory", "builder", "factory_method", "prototype", "singleton",
            ],
            "gof_structural": [
                "adapter", "bridge", "composite", "decorator",
                "facade", "flyweight", "proxy",
            ],
            "gof_behavioral": [
                "chain_of_responsibility", "command", "interpreter", "iterator",
                "mediator", "memento", "observer", "state",
                "strategy", "template_method", "visitor",
            ],
            "enterprise": [
                "repository", "unit_of_work", "cqrs", "event_sourcing",
                "saga", "outbox", "strangler_fig", "anti_corruption_layer",
            ],
        }, indent=2)

    @mcp.resource("design-patterns://sessions")
    async def sessions_with_reports() -> str:
        sids = [
            sid for sid, ctx in sessions.items()
            if ctx.metadata.get("pattern_recommendation_report") is not None
        ]
        return json.dumps(sids)

    @mcp.tool()
    async def recommend_design_patterns(session_id: str) -> str:
        """
        Trigger design pattern recommendation for an existing architecture session.

        Evaluates the full GoF catalog (23 patterns) and 8 enterprise patterns against
        the session's design artifact and SOLID compliance report. Produces 3–10 ranked,
        non-conflicting PatternRecommendation entries.

        Requires decide_architecture (and optionally analyze_solid_compliance) to have
        been called first on this session.

        Args:
            session_id: Session ID from parse_requirements / decide_architecture.

        Returns JSON with:
          session_id
          report_id
          architecture_style
          total_patterns_evaluated
          recommendations_count
          solid_violations_addressed
          conflicts_count
          analysis_summary
          recommendations         — top-ranked list (rank, pattern_name, category, problem_solved)
          next_action
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

        try:
            report = await agent.recommend(ctx, solid_report=solid_report)
        except Exception as exc:
            return json.dumps({"error": f"Pattern recommendation failed: {exc}"})

        ctx.metadata["pattern_recommendation_report"] = report
        sessions[session_id] = ctx

        next_action = (
            "review_conflicts"
            if report.conflicts
            else "implement_top_patterns"
        )

        return json.dumps({
            "session_id": session_id,
            "report_id": report.report_id,
            "architecture_style": report.architecture_style,
            "total_patterns_evaluated": report.total_patterns_evaluated,
            "recommendations_count": len(report.recommendations),
            "solid_violations_addressed": report.solid_violations_addressed,
            "conflicts_count": len(report.conflicts),
            "analysis_summary": report.analysis_summary,
            "recommendations": [
                {
                    "rank": r.rank,
                    "pattern_name": r.pattern_name,
                    "category": r.category.value,
                    "problem_solved": r.problem_solved,
                    "solid_principles_reinforced": r.solid_principles_reinforced,
                    "target_components": r.target_components,
                    "score": r.score,
                }
                for r in report.recommendations
            ],
            "conflicts": [
                {
                    "pattern_a": c.pattern_a,
                    "pattern_b": c.pattern_b,
                    "target_component": c.target_component,
                    "reason": c.reason,
                }
                for c in report.conflicts
            ],
            "next_action": next_action,
        }, indent=2)

    @mcp.tool()
    async def get_pattern_recommendation_report(session_id: str) -> str:
        """
        Retrieve the full PatternRecommendationReport for a session.

        Must call recommend_design_patterns first. Returns the complete report
        including all recommendations with implementation sketches and conflict details.

        Args:
            session_id: Session ID with an existing pattern recommendation report.

        Returns the full PatternRecommendationReport as JSON.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        report = ctx.metadata.get("pattern_recommendation_report")
        if report is None:
            return json.dumps({
                "error": (
                    "No pattern recommendation report found. "
                    "Call recommend_design_patterns first."
                ),
                "session_id": session_id,
            })

        return json.dumps({
            "session_id": session_id,
            "report_id": report.report_id,
            "architecture_style": report.architecture_style,
            "total_patterns_evaluated": report.total_patterns_evaluated,
            "solid_violations_addressed": report.solid_violations_addressed,
            "analysis_summary": report.analysis_summary,
            "recommendations": [
                {
                    "rank": r.rank,
                    "pattern_name": r.pattern_name,
                    "category": r.category.value,
                    "target_components": r.target_components,
                    "problem_solved": r.problem_solved,
                    "implementation_sketch": r.implementation_sketch,
                    "solid_principles_reinforced": r.solid_principles_reinforced,
                    "rationale": r.rationale,
                    "score": r.score,
                }
                for r in report.recommendations
            ],
            "conflicts": [
                {
                    "pattern_a": c.pattern_a,
                    "pattern_b": c.pattern_b,
                    "target_component": c.target_component,
                    "reason": c.reason,
                }
                for c in report.conflicts
            ],
        }, indent=2)

    @mcp.tool()
    async def get_pattern_details(session_id: str, pattern_name: str) -> str:
        """
        Retrieve details for a specific recommended pattern.

        Args:
            session_id: Session ID with an existing pattern recommendation report.
            pattern_name: Pattern name (e.g., repository, strategy, factory_method).

        Returns the full PatternRecommendation including implementation sketch.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        report = ctx.metadata.get("pattern_recommendation_report")
        if report is None:
            return json.dumps({
                "error": "No report found. Call recommend_design_patterns first."
            })

        rec = report.get_recommendation(pattern_name.lower())
        if rec is None:
            available = [r.pattern_name for r in report.recommendations]
            return json.dumps({
                "error": f"Pattern '{pattern_name}' not in recommendations.",
                "available_patterns": available,
            })

        return json.dumps({
            "rank": rec.rank,
            "pattern_name": rec.pattern_name,
            "category": rec.category.value,
            "target_components": rec.target_components,
            "problem_solved": rec.problem_solved,
            "implementation_sketch": rec.implementation_sketch,
            "solid_principles_reinforced": rec.solid_principles_reinforced,
            "rationale": rec.rationale,
            "score": rec.score,
        }, indent=2)

    return mcp


class DesignPatternMCPServer:
    def __init__(
        self,
        sessions: "dict[str, PipelineContext]",
        agent: "DesignPatternRecommenderAgent",
        llm: "BaseLLMProvider | None" = None,
    ) -> None:
        self._mcp = create_design_pattern_mcp(sessions, agent, llm=llm)

    def sse_app(self):
        return self._mcp.sse_app()
