"""Design specialized agent."""
from src.skills.base import SkillCategory
from src.llm.prompts import DESIGN_EXPERT
from .base import BaseAgent


class DesignAgent(BaseAgent):
    """Agent specialized in UI/UX design, Tailwind CSS, and design systems."""

    name = "Design Agent"
    description = (
        "Specializes in UI/UX design: Tailwind CSS, shadcn/ui, color systems, "
        "typography, layouts, accessibility, animations, and design systems."
    )
    category = SkillCategory.DESIGN
    system_prompt = DESIGN_EXPERT

    SKILL_SHORTCUTS = {
        "tailwind": "design.generate_tailwind_config",
        "tokens": "design.generate_design_tokens_css",
        "layout": "design.generate_responsive_layout",
        "shadcn": "design.setup_shadcn",
        "table": "design.generate_data_table",
        "dashboard": "design.generate_dashboard",
        "animate": "design.implement_animations",
        "skeleton": "design.generate_loading_ui",
        "a11y": "design.audit_accessibility",
        "skip": "design.generate_skip_links",
        "palette": "design.generate_color_palette",
        "darkmode": "design.implement_dark_mode",
        "typescale": "design.generate_type_scale",
        "fonts": "design.setup_next_fonts",
        "system": "design.generate_design_system",
        "sidebar": "design.generate_sidebar_layout",
        "variants": "design.generate_component_variants",
    }
