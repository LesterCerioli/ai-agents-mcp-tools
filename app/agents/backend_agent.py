from app.skills.base import SkillCategory
from .base import BaseAgent


_BACKEND_EXPERT = (
    "You are a senior Python backend engineer specialising in FastAPI, SQLAlchemy 2.0 async, "
    "clean architecture, and domain-driven design. You write production-ready, type-annotated Python 3.12 code."
)


class BackendAgent(BaseAgent):
    
    name = "backend"
    description = (
        "Generates Python/FastAPI backend code: REST endpoints, async SQLAlchemy models, "
        "repository pattern, design patterns (Factory, Strategy, CQRS, Saga…), "
        "Docker setup, and pytest integration test suites."
    )
    category = SkillCategory.BACKEND
    system_prompt = _BACKEND_EXPERT

    SKILL_SHORTCUTS = {
        "endpoint": "backend.fastapi_endpoint",
        "model": "backend.sqlalchemy_model",
        "repo": "backend.repository_pattern",
        "pattern": "backend.design_patterns",
        "docker": "backend.docker_setup",
        "tests": "backend.pytest_suite",
    }

    async def quick(self, shortcut: str, **params) -> "AgentResult":  # type: ignore
        
        from .base import AgentResult
        skill_name = self.SKILL_SHORTCUTS.get(shortcut, shortcut)
        skill_result = await self.execute_skill(skill_name, **params)
        return AgentResult(
            success=skill_result.success,
            summary=skill_result.summary,
            skill_results=[skill_result],
            agent_name=self.name,
        )
