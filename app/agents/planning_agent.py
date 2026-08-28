from app.skills.base import SkillCategory
from .base import BaseAgent


_PLANNING_EXPERT = (
    "You are a senior Product Manager, Agile Coach and Technical Writer. "
    "You specialize in requirements analysis, backlog refinement, user story mapping, "
    "acceptance criteria (Gherkin/Given-When-Then), story point estimation, "
    "dependency mapping, and technical specification writing. "
    "You produce clear, testable, INVEST-compliant artifacts in Markdown/JSON."
)


class PlanningAgent(BaseAgent):
    name = "planning"
    description = (
        "Handles non-code planning work: requirements analysis, improving task descriptions, "
        "generating user stories with ACs, estimating effort, mapping dependencies, "
        "and generating technical specs. Works with docs, kanban, backlog files."
    )
    category = SkillCategory.PLANNING
    system_prompt = _PLANNING_EXPERT
