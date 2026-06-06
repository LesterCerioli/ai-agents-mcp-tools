"""Next.js specialized agent."""
from src.skills.base import SkillCategory
from src.llm.prompts import NEXTJS_EXPERT
from .base import BaseAgent


class NextJSAgent(BaseAgent):
    """Agent specialized in Next.js 15 App Router development."""

    name = "NextJS Agent"
    description = (
        "Specializes in Next.js 15 App Router development: components, pages, layouts, "
        "server actions, API routes, authentication, data fetching, optimization, and SEO."
    )
    category = SkillCategory.NEXTJS
    system_prompt = NEXTJS_EXPERT

    SKILL_SHORTCUTS = {
        "component": "nextjs.generate_component",
        "setup-sc": "nextjs.setup_styled_components",
        "decompose": "nextjs.decompose_into_components",
        "page": "nextjs.generate_page",
        "layout": "nextjs.generate_layout",
        "loading": "nextjs.generate_loading",
        "error": "nextjs.generate_error_page",
        "form": "nextjs.generate_form_component",
        "action": "nextjs.generate_server_action",
        "crud": "nextjs.generate_crud_actions",
        "optimistic": "nextjs.implement_optimistic_update",
        "fetch": "nextjs.generate_server_fetch",
        "stream": "nextjs.generate_streaming_page",
        "isr": "nextjs.implement_isr",
        "routes": "nextjs.generate_route_structure",
        "middleware": "nextjs.generate_middleware",
        "api": "nextjs.generate_api_route",
        "auth": "nextjs.setup_nextauth",
        "protect": "nextjs.generate_protected_route",
        "images": "nextjs.optimize_images",
        "fonts": "nextjs.optimize_fonts",
        "split": "nextjs.implement_code_splitting",
        "metadata": "nextjs.generate_metadata",
        "og": "nextjs.generate_og_image",
        "sitemap": "nextjs.generate_sitemap",
    }

    async def quick(self, shortcut: str, **params) -> "AgentResult":  # type: ignore
        """Execute a skill by shortcut name."""
        from .base import AgentContext
        skill_name = self.SKILL_SHORTCUTS.get(shortcut, shortcut)
        skill_result = await self.execute_skill(skill_name, **params)
        from .base import AgentResult
        return AgentResult(
            success=skill_result.success,
            summary=skill_result.summary,
            skill_results=[skill_result],
            agent_name=self.name,
        )
