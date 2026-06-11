"""Multi-agent orchestrator for complex tasks."""
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from src.llm.bm25_index import SkillBM25Index
from .base import BaseAgent, AgentResult, AgentContext
from .nextjs_agent import NextJSAgent
from .design_agent import DesignAgent
from .frontend_agent import FrontendAgent
from .vercel_agent import VercelAgent
from .backend_agent import BackendAgent

if TYPE_CHECKING:
    from src.llm.base import BaseLLMProvider


@dataclass
class OrchestratorPlan:
    analysis: str
    tasks: list[dict[str, Any]] = field(default_factory=list)


class AgentOrchestrator:
    """
    Routes tasks to the appropriate specialized agent and coordinates multi-agent workflows.

    Example:
        orchestrator = AgentOrchestrator(llm=provider)
        result = await orchestrator.run("Create a SaaS dashboard with auth, dark mode, and data tables")
    """

    def __init__(self, llm: "BaseLLMProvider | None" = None):
        self.llm = llm
        self.agents: dict[str, BaseAgent] = {
            "nextjs": NextJSAgent(llm=llm),
            "design": DesignAgent(llm=llm),
            "frontend": FrontendAgent(llm=llm),
            "vercel": VercelAgent(llm=llm),
            "backend": BackendAgent(llm=llm),
        }
        self._bm25 = SkillBM25Index()
        self._bm25.build(
            {agent_name: agent.available_skills for agent_name, agent in self.agents.items()}
        )

    def get_agent(self, name: str) -> BaseAgent:
        if name not in self.agents:
            raise KeyError(f"Unknown agent: {name}. Available: {list(self.agents.keys())}")
        return self.agents[name]

    async def plan(self, task: str) -> OrchestratorPlan:
        """Build an execution plan via BM25 skill routing — no LLM call required."""
        matches = self._bm25.search(task, top_k=5)
        if not matches:
            return OrchestratorPlan(analysis="No matching skills found.", tasks=[])

        tasks = [
            {"agent": m.agent_name, "skill": m.skill_name, "params": {}}
            for m in matches
        ]
        analysis = f"BM25 matched {len(matches)} skill(s): {', '.join(m.skill_name for m in matches)}"
        return OrchestratorPlan(analysis=analysis, tasks=tasks)

    async def run(self, task: str) -> "OrchestratorRunResult":
        """Execute a complex task using multiple agents."""
        plan = await self.plan(task)
        results: list[AgentResult] = []
        errors: list[str] = []

        for task_spec in plan.tasks:
            agent_name = task_spec.get("agent", "")
            skill_name = task_spec.get("skill", "")
            params = task_spec.get("params", {})

            if agent_name not in self.agents:
                errors.append(f"Unknown agent: {agent_name}")
                continue

            try:
                agent = self.agents[agent_name]
                skill_result = await agent.execute_skill(skill_name, **params)
                results.append(AgentResult(
                    success=skill_result.success,
                    summary=skill_result.summary,
                    skill_results=[skill_result],
                    agent_name=agent.name,
                ))
            except Exception as e:
                errors.append(f"{agent_name}.{skill_name}: {e}")

        return OrchestratorRunResult(
            plan=plan,
            agent_results=results,
            errors=errors,
        )

    async def run_skill(self, agent_name: str, skill_name: str, **params: Any) -> AgentResult:
        """Directly run a specific skill on a specific agent."""
        agent = self.get_agent(agent_name)
        result = await agent.execute_skill(skill_name, **params)
        return AgentResult(
            success=result.success,
            summary=result.summary,
            skill_results=[result],
            agent_name=agent.name,
        )

    def list_all_skills(self) -> dict[str, list[dict[str, Any]]]:
        """List all available skills grouped by agent."""
        return {
            agent_name: agent.available_skills
            for agent_name, agent in self.agents.items()
        }


@dataclass
class OrchestratorRunResult:
    plan: OrchestratorPlan
    agent_results: list[AgentResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and all(r.success for r in self.agent_results)

    @property
    def all_artifacts(self):
        return [art for result in self.agent_results for art in result.all_artifacts]

    @property
    def all_dependencies(self) -> list[str]:
        deps: set[str] = set()
        for r in self.agent_results:
            deps.update(r.all_dependencies)
        return sorted(deps)

    def summary(self) -> str:
        lines = [f"Plan: {self.plan.analysis}", ""]
        for i, result in enumerate(self.agent_results, 1):
            status = "✓" if result.success else "✗"
            lines.append(f"{status} [{result.agent_name}] {result.summary}")
        if self.errors:
            lines.append("\nErrors:")
            lines.extend(f"  - {e}" for e in self.errors)
        if self.all_dependencies:
            lines.append(f"\nDependencies: {', '.join(self.all_dependencies)}")
        return "\n".join(lines)
