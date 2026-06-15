from app.skills.base import SkillCategory
from .base import BaseAgent, AgentResult

_DIAGNOSTIC_EXPERT = (
    "You are a senior polyglot engineer specialized in diagnosing and fixing build, compile, "
    "and runtime errors across Go, Next.js/TypeScript, and Python. "
    "You identify root causes precisely, return only minimal targeted fixes, and never alter "
    "working logic. You know Go 1.24, Next.js 15, TypeScript 5, Python 3.12, FastAPI, and "
    "common build toolchains (go build, tsc, next build, uvicorn)."
)


class DiagnosticAgent(BaseAgent):

    name = "diagnostic"
    description = (
        "Diagnoses and fixes build/compile/runtime errors in Go, Next.js/TypeScript, and Python projects. "
        "Receives error output and affected source files, then returns corrected files ready to apply. "
        "Uses LLM analysis when available; falls back to a structured diagnostic report."
    )
    category = SkillCategory.DIAGNOSTIC
    system_prompt = _DIAGNOSTIC_EXPERT

    SKILL_SHORTCUTS = {
        "go":     "diagnostic.go_diagnose",
        "nextjs": "diagnostic.nextjs_diagnose",
        "python": "diagnostic.python_diagnose",
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
