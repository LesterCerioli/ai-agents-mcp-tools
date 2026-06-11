from app.skills.base import SkillCategory
from .base import BaseAgent, AgentResult


_GO_EXPERT = (
    "You are a senior Go engineer specialising in clean architecture, domain-driven design, "
    "and idiomatic Go 1.24. You write production-ready, well-tested Go code using pgx/v5 for "
    "PostgreSQL, golang-jwt for authentication, and uber-go/zap for structured logging. "
    "You know Fiber v2, Gin, Gorilla Mux, Echo v4, and Chi v5 thoroughly."
)


class GoAgent(BaseAgent):
    
    name = "go"
    description = (
        "Generates Go 1.24 backend code: project scaffold, domain structs, repository pattern "
        "(pgx/v5), service layer, migrations (golang-migrate), Docker setup, and full CRUD "
        "HTTP handlers/routes/middleware for Fiber v2, Gin, Gorilla Mux, Echo v4, and Chi v5."
    )
    category = SkillCategory.GO
    system_prompt = _GO_EXPERT

    SKILL_SHORTCUTS = {
        "setup": "go.setup_project",
        "struct": "go.go_struct",
        "repo": "go.repository",
        "service": "go.service",
        "docker": "go.docker_setup",
        "tests": "go.test_suite",
        "migrate": "go.generate_migration",
        "config": "go.config",
        "logger": "go.logger",
        
        "fiber_app": "go.fiber_app",
        "fiber_handler": "go.fiber_handler",
        "fiber_routes": "go.fiber_routes",
        "fiber_middleware": "go.fiber_middleware",
        
        "gin_app": "go.gin_app",
        "gin_handler": "go.gin_handler",
        "gin_routes": "go.gin_routes",
        "gin_middleware": "go.gin_middleware",
        
        "gorilla_app": "go.gorilla_app",
        "gorilla_handler": "go.gorilla_handler",
        "gorilla_routes": "go.gorilla_routes",
        
        "echo_app": "go.echo_app",
        "echo_handler": "go.echo_handler",
        "echo_routes": "go.echo_routes",
        "echo_middleware": "go.echo_middleware",
        
        "chi_app": "go.chi_app",
        "chi_handler": "go.chi_handler",
        "chi_routes": "go.chi_routes",
    }

    async def quick(self, shortcut: str, **params) -> "AgentResult":
        
        skill_name = self.SKILL_SHORTCUTS.get(shortcut, shortcut)
        skill_result = await self.execute_skill(skill_name, **params)
        return AgentResult(
            success=skill_result.success,
            summary=skill_result.summary,
            skill_results=[skill_result],
            agent_name=self.name,
        )
