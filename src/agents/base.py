
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)
from src.skills.base import BaseSkill, SkillCategory, SkillResult
from src.skills.registry import SkillRegistry
from src.llm.bm25_index import SkillBM25Index

if TYPE_CHECKING:
    from src.llm.base import BaseLLMProvider


@dataclass
class AgentContext:
    """Context passed to agents during task execution."""
    task: str
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    
    success: bool
    summary: str
    skill_results: list[SkillResult] = field(default_factory=list)
    agent_name: str = ""
    error: str | None = None

    @property
    def all_artifacts(self):
        return [art for result in self.skill_results for art in result.artifacts]

    @property
    def all_dependencies(self):
        deps = set()
        for r in self.skill_results:
            deps.update(r.dependencies)
        return sorted(deps)

    @property
    def all_dev_dependencies(self):
        deps = set()
        for r in self.skill_results:
            deps.update(r.dev_dependencies)
        return sorted(deps)


class BaseAgent:
    
    name: str
    description: str
    category: SkillCategory
    system_prompt: str = ""

    def __init__(self, llm: "BaseLLMProvider | None" = None):
        self.llm = llm
        self._skills: dict[str, BaseSkill] = {}
        self._load_skills()
        self._bm25 = SkillBM25Index()
        self._bm25.build({self.name: [s.schema() for s in self._skills.values()]})

    def _load_skills(self) -> None:
        
        skills = SkillRegistry.instantiate_all(self.category, self.llm)
        self._skills = {skill.name: skill for skill in skills}

    @property
    def available_skills(self) -> list[dict[str, Any]]:
        return [skill.schema() for skill in self._skills.values()]

    def get_skill(self, name: str) -> BaseSkill:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not available in {self.name}. Available: {list(self._skills.keys())}")
        return self._skills[name]

    async def execute_skill(self, skill_name: str, **params: Any) -> SkillResult:
        skill = self.get_skill(skill_name)
        return await skill.execute(**params)

    async def run(self, context: AgentContext) -> AgentResult:
        
        matches = self._bm25.search(context.task, top_k=1)
        if not matches:
            return AgentResult(
                success=False,
                summary="No matching skill found for the given task.",
                agent_name=self.name,
            )

        skill_name = matches[0].skill_name
        params: dict[str, Any] = {}

        if self.llm:
            extracted = await self._extract_params(skill_name, context.task)
            if extracted is None:
                logger.warning(
                    "Failed to decode LLM params JSON for skill %s; aborting skill execution",
                    skill_name,
                )
                return AgentResult(
                    success=False,
                    summary=f"Could not extract parameters for skill '{skill_name}': LLM returned invalid JSON.",
                    agent_name=self.name,
                )
            params = extracted

        skill_result = await self.execute_skill(skill_name, **params)
        return AgentResult(
            success=skill_result.success,
            summary=f"Executed {skill_name}: {skill_result.summary}",
            skill_results=[skill_result],
            agent_name=self.name,
        )

    async def _extract_params(self, skill_name: str, task: str) -> Optional[dict[str, Any]]:
        
        skill = self.get_skill(skill_name)
        required = [p for p in skill.schema()["parameters"] if p.get("required", True)]
        if not required:
            return {}

        param_lines = "\n".join(f"- {p['name']}: {p['description']}" for p in required)
        prompt = (
            f"Task: {task}\n\n"
            f"Extract the following parameters for skill '{skill_name}':\n"
            f"{param_lines}\n\n"
            "Return only JSON: {\"param_name\": \"value\"}"
        )

        response = await self.llm.chat(prompt, system_prompt=self.system_prompt)  # type: ignore[union-attr]
        try:
            return json.loads(response)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} skills={len(self._skills)}>"
