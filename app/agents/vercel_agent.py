
from app.skills.base import SkillCategory
from app.llm.prompts import VERCEL_EXPERT
from .base import BaseAgent


class VercelAgent(BaseAgent):
    
    name = "Vercel Agent"
    description = (
        "Specializes in Vercel platform: deployment config, environment variables, "
        "Edge Config, feature flags, analytics, and production readiness."
    )
    category = SkillCategory.VERCEL
    system_prompt = VERCEL_EXPERT

    SKILL_SHORTCUTS = {
        "config": "vercel.generate_config",
        "checklist": "vercel.deployment_checklist",
        "env": "vercel.generate_env_validation",
        "flags": "vercel.implement_feature_flags",
        "analytics": "vercel.setup_analytics",
    }
