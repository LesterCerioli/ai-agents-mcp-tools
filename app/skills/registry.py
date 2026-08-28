from typing import Any, TYPE_CHECKING
from .base import BaseSkill, SkillCategory, SkillMetadata, SkillDomain, SkillComplexity

if TYPE_CHECKING:
    from app.llm.base import BaseLLMProvider


class SkillRegistry:
    
    _skill_classes: dict[str, type[BaseSkill]] = {}

    @classmethod
    def register(cls, skill_class: type[BaseSkill]) -> type[BaseSkill]:
        """Decorator to register a skill class."""
        cls._skill_classes[skill_class.name] = skill_class
        return skill_class

    @classmethod
    def get(cls, name: str, llm: "BaseLLMProvider | None" = None) -> BaseSkill:
        if name not in cls._skill_classes:
            raise KeyError(f"Skill '{name}' not found. Available: {list(cls._skill_classes.keys())}")
        return cls._skill_classes[name](llm=llm)

    @classmethod
    def list_all(cls) -> list[dict[str, Any]]:
        return [sc(llm=None).schema() for sc in cls._skill_classes.values()]

    @classmethod
    def list_by_category(cls, category: SkillCategory) -> list[dict[str, Any]]:
        return [
            sc(llm=None).schema()
            for sc in cls._skill_classes.values()
            if sc.category == category
        ]

    @classmethod
    def list_by_tag(cls, tag: str) -> list[dict[str, Any]]:
        return [
            sc(llm=None).schema()
            for sc in cls._skill_classes.values()
            if tag in sc.tags
        ]

    @classmethod
    def list_by_domain(cls, domain: SkillDomain) -> list[dict[str, Any]]:
        return [
            sc(llm=None).schema()
            for sc in cls._skill_classes.values()
            if sc(llm=None).metadata.domain == domain
        ]

    @classmethod
    def list_for_planner(cls) -> list[dict[str, Any]]:
        """Returns all skills with full metadata for the Grok planner."""
        return [sc(llm=None).schema() for sc in cls._skill_classes.values()]

    @classmethod
    def instantiate_all(cls, category: SkillCategory, llm: "BaseLLMProvider | None" = None) -> list[BaseSkill]:
        return [
            sc(llm=llm)
            for sc in cls._skill_classes.values()
            if sc.category == category
        ]

    @classmethod
    def names(cls) -> list[str]:
        return list(cls._skill_classes.keys())
