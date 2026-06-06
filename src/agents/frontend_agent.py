"""Frontend specialized agent."""
from src.skills.base import SkillCategory
from src.llm.prompts import FRONTEND_EXPERT
from .base import BaseAgent


class FrontendAgent(BaseAgent):
    """Agent specialized in React frontend patterns and ecosystem."""

    name = "Frontend Agent"
    description = (
        "Specializes in React frontend: state management (Zustand, Jotai), "
        "forms (React Hook Form + Zod), data fetching (TanStack Query), "
        "testing (Vitest, Playwright), i18n, and performance."
    )
    category = SkillCategory.FRONTEND
    system_prompt = FRONTEND_EXPERT

    SKILL_SHORTCUTS = {
        "store": "frontend.implement_zustand_store",
        "atoms": "frontend.implement_jotai_atoms",
        "ui-store": "frontend.implement_ui_store",
        "schema": "frontend.generate_zod_schema",
        "multistep": "frontend.generate_multi_step_form",
        "query": "frontend.implement_tanstack_query",
        "virtual": "frontend.implement_virtualization",
        "memo": "frontend.implement_memoization",
        "test": "frontend.generate_component_tests",
        "e2e": "frontend.generate_e2e_tests",
        "i18n": "frontend.setup_i18n",
        "sentry": "frontend.setup_sentry",
        "toast": "frontend.implement_toast_system",
    }
