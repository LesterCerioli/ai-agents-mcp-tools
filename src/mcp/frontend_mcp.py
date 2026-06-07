"""
Frontend MCP Server — exposes frontend/NextJS code generation via Model Context Protocol.

Uses FastMCP high-level API. Mount via: app.mount("/mcp/frontend", server.sse_app())

Tools:
  - generate_ui_components
  - setup_routing
  - setup_deployment
  - apply_design_system

Resources:
  - frontend://skills
"""
import json
from typing import TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentOrchestrator


def create_frontend_mcp(orchestrator: "AgentOrchestrator") -> FastMCP:
    """Create and return the Frontend MCP server."""
    mcp = FastMCP("frontend-mcp")

    @mcp.resource("frontend://skills")
    async def frontend_skills() -> str:
        skills: dict = {}
        for name in ("nextjs", "frontend", "design", "vercel"):
            agent = orchestrator.agents.get(name)
            if agent:
                skills[name] = agent.available_skills
        return json.dumps(skills, indent=2)

    @mcp.tool()
    async def generate_ui_components(
        skill: str,
        route: str = "/",
        name: str = "Component",
        description: str = "",
    ) -> str:
        """
        Generate NextJS pages, layouts, components, or forms.

        Args:
            skill: Skill to use. Options: page, layout, component, form, loading, error.
            route: URL route for pages (e.g. /dashboard, /products/[id]).
            name: Component or layout name.
            description: What the component does.
        """
        agent = orchestrator.agents.get("nextjs")
        if agent is None:
            return json.dumps({"error": "NextJS agent not available"})

        skill_map = {
            "page": "nextjs.generate_page",
            "layout": "nextjs.generate_layout",
            "component": "nextjs.generate_component",
            "form": "nextjs.generate_form_component",
            "loading": "nextjs.generate_loading",
            "error": "nextjs.generate_error_page",
        }
        skill_name = skill_map.get(skill, skill)
        params = {"route": route, "name": name}
        if description:
            params["description"] = description

        result = await agent.execute_skill(skill_name, **params)
        return json.dumps({
            "success": result.success,
            "summary": result.summary,
            "artifacts": [
                {"filename": a.filename, "language": a.language, "content": a.content}
                for a in result.artifacts
            ],
        }, indent=2)

    @mcp.tool()
    async def setup_routing(
        routes: str,
        with_middleware: bool = False,
    ) -> str:
        """
        Generate NextJS route structure and optionally auth middleware.

        Args:
            routes: Comma-separated routes to generate (e.g. /dashboard, /products/[id]).
            with_middleware: Whether to generate authentication middleware.
        """
        agent = orchestrator.agents.get("nextjs")
        if agent is None:
            return json.dumps({"error": "NextJS agent not available"})

        result = await agent.execute_skill("nextjs.generate_route_structure", routes=routes)
        artifacts = [
            {"filename": a.filename, "language": a.language, "content": a.content}
            for a in result.artifacts
        ]

        if with_middleware:
            try:
                mw = await agent.execute_skill(
                    "nextjs.generate_middleware", description="Authentication middleware"
                )
                if mw.success:
                    artifacts.extend(
                        {"filename": a.filename, "language": a.language, "content": a.content}
                        for a in mw.artifacts
                    )
            except Exception:
                pass

        return json.dumps({
            "success": result.success,
            "summary": result.summary,
            "artifacts": artifacts,
        }, indent=2)

    @mcp.tool()
    async def setup_deployment(
        project_name: str,
        framework: str = "nextjs",
    ) -> str:
        """
        Generate Vercel deployment configuration.

        Args:
            project_name: Vercel project name.
            framework: Framework type. Options: nextjs, vite, remix.
        """
        agent = orchestrator.agents.get("vercel")
        if agent is None:
            return json.dumps({"error": "Vercel agent not available"})

        try:
            result = await agent.execute_skill(
                "vercel.generate_vercel_config",
                project_name=project_name,
                framework=framework,
            )
            return json.dumps({
                "success": result.success,
                "summary": result.summary,
                "artifacts": [
                    {"filename": a.filename, "language": a.language, "content": a.content}
                    for a in result.artifacts
                ],
            }, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @mcp.tool()
    async def apply_design_system(
        project_type: str,
        include_shadcn: bool = True,
    ) -> str:
        """
        Generate Tailwind configuration and design tokens.

        Args:
            project_type: Domain/project type for tailored tokens (e.g. fintech, ecommerce).
            include_shadcn: Whether to include shadcn/ui component setup.
        """
        agent = orchestrator.agents.get("design")
        if agent is None:
            return json.dumps({"error": "Design agent not available"})

        results: list[dict] = []

        try:
            tw = await agent.execute_skill(
                "design.generate_tailwind_config", project_type=project_type
            )
            results.append({
                "skill": "tailwind",
                "success": tw.success,
                "artifacts": [
                    {"filename": a.filename, "language": a.language, "content": a.content}
                    for a in tw.artifacts
                ],
            })
        except Exception as e:
            results.append({"skill": "tailwind", "success": False, "error": str(e)})

        if include_shadcn:
            try:
                sh = await agent.execute_skill("design.setup_shadcn", project_type=project_type)
                results.append({
                    "skill": "shadcn",
                    "success": sh.success,
                    "artifacts": [
                        {"filename": a.filename, "language": a.language, "content": a.content}
                        for a in sh.artifacts
                    ],
                })
            except Exception as e:
                results.append({"skill": "shadcn", "success": False, "error": str(e)})

        return json.dumps(results, indent=2)

    return mcp


class FrontendMCPServer:
    """Wrapper that holds the FastMCP instance and exposes the ASGI app."""

    def __init__(self, orchestrator: "AgentOrchestrator") -> None:
        self._mcp = create_frontend_mcp(orchestrator)

    def sse_app(self):
        return self._mcp.sse_app()
