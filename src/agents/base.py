"""Base agent implementation."""
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from src.skills.base import BaseSkill, SkillCategory, SkillResult
from src.skills.registry import SkillRegistry

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
    """Result from an agent task execution."""
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
    """Base class for all specialized agents."""

    name: str
    description: str
    category: SkillCategory
    system_prompt: str = ""

    def __init__(self, llm: "BaseLLMProvider | None" = None):
        self.llm = llm
        self._skills: dict[str, BaseSkill] = {}
        self._load_skills()

    def _load_skills(self) -> None:
        """Load all skills for this agent's category."""
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
        """Execute a task — override in subclasses for complex orchestration."""
        if self.llm:
            return await self._run_with_llm(context)
        return AgentResult(
            success=False,
            summary="No LLM configured. Provide HUGGINGFACE_TOKEN and retry.",
            agent_name=self.name,
        )

    async def _run_with_llm(self, context: AgentContext) -> AgentResult:
        """Use LLM to analyze task and select/execute appropriate skills."""
        skills_summary = "\n".join(
            f"- {s['name']}: {s['description']}"
            for s in self.available_skills
        )

        analysis_prompt = (
            f"Task: {context.task}\n\n"
            f"Available skills:\n{skills_summary}\n\n"
            "Select the best skill and its parameters. "
            "Respond with JSON: {\"skill\": \"skill.name\", \"params\": {...}, \"reasoning\": \"...\"}"
        )

        response = await self.llm.chat(analysis_prompt, system_prompt=self.system_prompt)

        import json
        try:
            selection = json.loads(response)
            skill_name = selection.get("skill", "")
            params = selection.get("params", {})
            skill_result = await self.execute_skill(skill_name, **params)
            return AgentResult(
                success=skill_result.success,
                summary=f"Executed {skill_name}: {skill_result.summary}",
                skill_results=[skill_result],
                agent_name=self.name,
            )
        except (json.JSONDecodeError, KeyError) as e:
            return AgentResult(
                success=False,
                summary="Failed to parse skill selection",
                agent_name=self.name,
                error=str(e),
            )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} skills={len(self._skills)}>"
