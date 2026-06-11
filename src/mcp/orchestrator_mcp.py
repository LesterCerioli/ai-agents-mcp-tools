"""
Orchestrator MCP Server — top-level coordinator for the full workflow pipeline.

Uses FastMCP high-level API. Mount via: app.mount("/mcp/orchestrate", server.sse_app())

Tools:
  - run_full_workflow
  - run_architecture_pipeline
  - get_workflow_status
  - list_agents

Resources:
  - orchestrator://sessions
  - orchestrator://agents
"""
import json
from typing import Any, TYPE_CHECKING

from mcp.server import FastMCP

from src.architecture.schemas.workflow import WorkflowScope

if TYPE_CHECKING:
    from src.architecture.workflow_coordinator import WorkflowCoordinator
    from src.agents.orchestrator import AgentOrchestrator
    from src.architecture.context.pipeline_context import PipelineContext


def create_orchestrator_mcp(
    workflow_coordinator: "WorkflowCoordinator",
    orchestrator: "AgentOrchestrator",
    sessions: dict[str, "PipelineContext"],
) -> FastMCP:
    """Create and return the Orchestrator MCP server."""
    mcp = FastMCP("orchestrator-mcp")

    @mcp.resource("orchestrator://sessions")
    async def active_sessions() -> str:
        return json.dumps(list(sessions.keys()))

    @mcp.resource("orchestrator://agents")
    async def available_agents() -> str:
        return json.dumps(orchestrator.list_all_skills(), indent=2)

    @mcp.tool()
    async def run_full_workflow(
        objective: str,
        scope: str = "fullstack",
        session_id: str | None = None,
    ) -> str:
        """
        Execute the complete pipeline from a business objective to generated code artifacts.

        Stages: parse requirements → decide architecture → diagram → validate →
                system design → backend code + frontend code + integration contracts.

        Args:
            objective: Natural-language description of what to build.
            scope: Which artifacts to generate. Options: backend, frontend, fullstack.
            session_id: Optional existing session ID to resume from (skips requirements parsing).
        """
        try:
            workflow_scope = WorkflowScope(scope)
        except ValueError:
            return json.dumps({"error": f"Invalid scope '{scope}'. Valid: backend, frontend, fullstack"})

        existing_ctx = sessions.get(session_id) if session_id else None

        output = await workflow_coordinator.run(
            objective=objective,
            scope=workflow_scope,
            session_id=session_id,
            existing_context=existing_ctx,
        )

        return json.dumps({
            "workflow_id": output.workflow_id,
            "session_id": output.session_id,
            "scope": output.scope.value,
            "architecture_pattern": output.architecture_pattern,
            "system_design_summary": output.system_design_summary,
            "summary": output.summary,
            "confidence": output.confidence,
            "backend_artifacts_count": len(output.backend_artifacts),
            "frontend_artifacts_count": len(output.frontend_artifacts),
            "has_integration_contracts": output.integration_contracts is not None,
            "backend_artifacts": [
                {"filename": a.filename, "language": a.language, "content": a.content}
                for a in output.backend_artifacts
            ],
            "frontend_artifacts": [
                {"filename": a.filename, "language": a.language, "content": a.content}
                for a in output.frontend_artifacts
            ],
            "integration_contracts": {
                "openapi_stub": output.integration_contracts.openapi_stub,
                "typescript_types": output.integration_contracts.typescript_types,
                "pydantic_schemas": output.integration_contracts.pydantic_schemas,
            } if output.integration_contracts else None,
        }, indent=2)

    @mcp.tool()
    async def run_architecture_pipeline(
        session_id: str,
        scope: str = "fullstack",
    ) -> str:
        """
        Run the architecture pipeline for an existing session and generate code.

        Use this when requirements have already been parsed via /architecture/parse
        and you want to continue to system design and code generation.

        Args:
            session_id: Session ID from a prior /architecture/parse call.
            scope: Which artifacts to generate. Options: backend, frontend, fullstack.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": f"Session '{session_id}' not found."})

        try:
            workflow_scope = WorkflowScope(scope)
        except ValueError:
            return json.dumps({"error": f"Invalid scope '{scope}'."})

        output = await workflow_coordinator.run(
            objective="",
            scope=workflow_scope,
            session_id=session_id,
            existing_context=ctx,
        )

        return json.dumps({
            "session_id": session_id,
            "workflow_id": output.workflow_id,
            "architecture_pattern": output.architecture_pattern,
            "system_design_summary": output.system_design_summary,
            "confidence": output.confidence,
            "backend_artifacts_count": len(output.backend_artifacts),
            "frontend_artifacts_count": len(output.frontend_artifacts),
        }, indent=2)

    @mcp.tool()
    async def get_workflow_status(session_id: str) -> str:
        """
        Return the current state of a workflow session.

        Args:
            session_id: The session ID to inspect.
        """
        ctx = sessions.get(session_id)
        if ctx is None:
            return json.dumps({"error": "Session not found"})

        status: dict[str, Any] = {
            "session_id": session_id,
            "has_requirements": ctx.requirements is not None,
            "has_decision": ctx.decision is not None,
            "has_diagram": ctx.diagram is not None,
            "has_system_design": ctx.system_design is not None,
            "has_workflow_output": ctx.workflow_output is not None,
            "execution_scope": ctx.execution_scope.value if ctx.execution_scope else None,
            "turn_count": ctx.turn_count(),
        }
        if ctx.requirements:
            status["overall_confidence"] = ctx.requirements.overall_confidence
            status["is_requirements_complete"] = ctx.requirements.is_complete
        if ctx.decision and ctx.decision.primary_pattern:
            status["primary_pattern"] = ctx.decision.primary_pattern.pattern.value

        return json.dumps(status, indent=2)

    @mcp.tool()
    async def list_agents() -> str:
        """List all available agents and their skill counts."""
        agents = {
            name: {
                "description": agent.description,
                "skill_count": len(agent.available_skills),
            }
            for name, agent in orchestrator.agents.items()
        }
        return json.dumps(agents, indent=2)

    return mcp


class OrchestratorMCPServer:
    """Wrapper that holds the FastMCP instance and exposes the ASGI app."""

    def __init__(
        self,
        workflow_coordinator: "WorkflowCoordinator",
        orchestrator: "AgentOrchestrator",
        sessions: dict[str, "PipelineContext"],
    ) -> None:
        self._mcp = create_orchestrator_mcp(workflow_coordinator, orchestrator, sessions)

    def sse_app(self):
        return self._mcp.sse_app()
