"""
Backend MCP Server — exposes backend code generation capabilities via Model Context Protocol.

Uses FastMCP high-level API. Mount via: app.mount("/mcp/backend", server.sse_app())

Tools:
  - generate_backend_code
  - apply_design_pattern
  - generate_docker_setup

Resources:
  - backend://skills
"""
import json
from typing import Any, TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from app.agents.backend_agent import BackendAgent


def create_backend_mcp(backend_agent: "BackendAgent") -> FastMCP:
    """Create and return the Backend MCP server."""
    mcp = FastMCP("backend-mcp")

    @mcp.resource("backend://skills")
    async def backend_skills() -> str:
        return json.dumps(backend_agent.available_skills, indent=2)

    @mcp.tool()
    async def generate_backend_code(
        resource: str,
        skills: list[str] | None = None,
    ) -> str:
        """
        Generate FastAPI endpoint, SQLAlchemy model, and/or repository pattern for a resource.

        Args:
            resource: Resource name in singular form (e.g. user, product, order)
            skills: Which code skills to run. Options: endpoint, model, repo, tests.
                    Defaults to all three (endpoint, model, repo).
        """
        if skills is None:
            skills = ["endpoint", "model", "repo"]

        skill_map = {
            "endpoint": "backend.fastapi_endpoint",
            "model": "backend.sqlalchemy_model",
            "repo": "backend.repository_pattern",
            "tests": "backend.pytest_suite",
        }
        results: list[dict] = []
        for shortcut in skills:
            skill_name = skill_map.get(shortcut, shortcut)
            try:
                result = await backend_agent.execute_skill(skill_name, resource=resource)
                results.append({
                    "skill": skill_name,
                    "success": result.success,
                    "summary": result.summary,
                    "artifacts": [
                        {"filename": a.filename, "language": a.language, "content": a.content}
                        for a in result.artifacts
                    ],
                })
            except Exception as e:
                results.append({"skill": skill_name, "success": False, "error": str(e)})

        return json.dumps(results, indent=2)

    @mcp.tool()
    async def apply_design_pattern(
        pattern: str,
        context: str = "",
    ) -> str:
        """
        Generate a backend design pattern implementation.

        Args:
            pattern: Pattern to generate. One of: factory, strategy, observer, command,
                     cqrs, unit_of_work, event_bus, saga.
            context: Domain context to personalise the pattern (e.g. Order, Payment, User).
        """
        result = await backend_agent.execute_skill(
            "backend.design_patterns",
            pattern=pattern,
            context=context,
        )
        return json.dumps({
            "success": result.success,
            "summary": result.summary,
            "artifacts": [
                {"filename": a.filename, "language": a.language, "content": a.content}
                for a in result.artifacts
            ],
            "error": result.error,
        }, indent=2)

    @mcp.tool()
    async def generate_docker_setup(
        app_name: str,
        services: str = "postgres",
    ) -> str:
        """
        Generate Dockerfile and docker-compose.yml for the backend application.

        Args:
            app_name: Application name used in image tags.
            services: Comma-separated services to include: postgres, redis, celery, prometheus.
        """
        result = await backend_agent.execute_skill(
            "backend.docker_setup",
            app_name=app_name,
            services=services,
        )
        return json.dumps({
            "success": result.success,
            "summary": result.summary,
            "artifacts": [
                {"filename": a.filename, "language": a.language, "content": a.content}
                for a in result.artifacts
            ],
            "instructions": result.instructions,
        }, indent=2)

    return mcp


class BackendMCPServer:
    """Wrapper that holds the FastMCP instance and exposes the ASGI app."""

    def __init__(self, backend_agent: "BackendAgent") -> None:
        self._mcp = create_backend_mcp(backend_agent)

    def sse_app(self):
        return self._mcp.sse_app()
