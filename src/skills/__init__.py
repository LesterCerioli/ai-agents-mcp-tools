from .base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from .registry import SkillRegistry

# Import all skill modules to trigger registration
from .nextjs import components, routing, data_fetching, server_actions, auth, optimization, metadata
from .design import tailwind, shadcn, color_system, typography, layout, accessibility, animations, design_system
from .frontend import state_management, forms, data_fetching as fe_data_fetching, performance, testing, i18n, error_handling
from .vercel import deployment, environment, edge_config, analytics

__all__ = [
    "BaseSkill",
    "SkillCategory",
    "SkillParameter",
    "SkillResult",
    "CodeArtifact",
    "SkillRegistry",
]
