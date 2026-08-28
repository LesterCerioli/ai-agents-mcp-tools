
from __future__ import annotations

from app.skills.base import BaseSkill, SkillCategory, SkillMetadata, SkillDomain, SkillComplexity, SkillParameter, SkillResult, CodeArtifact
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class EstimateEffortSkill(BaseSkill):
    name = "planning.estimate_effort"
    description = "Estimate effort for tasks, user stories, or features using story points (Fibonacci), t-shirt sizes, or ideal hours. Uses complexity factors: uncertainty, volume, technical difficulty, dependencies."
    category = SkillCategory.PLANNING
    parameters = [
        SkillParameter(
            name="source_file",
            description="Path to file with tasks/stories to estimate (user-stories.md, backlog.txt, etc.)",
            type="string",
            required=True,
        ),
        SkillParameter(
            name="method",
            description="Estimation method",
            type="string",
            required=False,
            default="story_points",
            enum=["story_points", "tshirt", "ideal_hours", "relative"],
        ),
        SkillParameter(
            name="baseline_story",
            description="Reference story for relative estimation (e.g. 'US-001: Login = 3 pts')",
            type="string",
            required=False,
            default="",
        ),
        SkillParameter(
            name="team_velocity",
            description="Team velocity (points/sprint) for sprint planning",
            type="integer",
            required=False,
            default=0,
        ),
    ]
    metadata = SkillMetadata(
        domain=SkillDomain.PLANNING,
        complexity=SkillComplexity.LOW,
        inputs=["source_file", "baseline_story"],
        outputs=["estimates", "sprint_plan"],
        prerequisites=["planning.generate_user_stories"],
        tags=["estimation", "story_points", "planning_poker", "sprint_planning", "velocity"],
        estimated_duration_seconds=30,
    )

    async def execute(self, source_file: str, method: str = "story_points", baseline_story: str = "", team_velocity: int = 0, **kwargs) -> SkillResult:
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return SkillResult.failure(f"Failed to read {source_file}: {e}")

        if self.llm:
            prompt = self._build_prompt(content, method, baseline_story, team_velocity)
            try:
                analysis = await self.llm.complete([
                    {"role": "system", "content": self._system_prompt(method)},
                    {"role": "user", "content": prompt}
                ])
                estimates = analysis.content
            except Exception as e:
                estimates = self._fallback_estimates(content, method, str(e))
        else:
            estimates = self._fallback_estimates(content, method, "No LLM available")

        output_file = source_file.replace(".md", "-estimates.md").replace(".txt", "-estimates.txt")
        return SkillResult(
            success=True,
            summary=f"Estimated effort for items in {source_file} using {method}",
            artifacts=[
                CodeArtifact(
                    filename=output_file,
                    content=estimates,
                    language="markdown",
                    description=f"Effort estimates ({method})",
                )
            ],
        )

    def _system_prompt(self, method: str) -> str:
        guides = {
            "story_points": "Use Fibonacci: 1, 2, 3, 5, 8, 13, 21. 1=trivial, 3=small, 5=medium, 8=large, 13=very large, 21=break down.",
            "tshirt": "Use XS, S, M, L, XL. XS=1-2 pts, S=3, M=5, L=8, XL=13+.",
            "ideal_hours": "Estimate ideal hours (no interruptions). 1, 2, 4, 8, 16, 24, 40.",
            "relative": "Compare each item to baseline. '2x baseline', '0.5x baseline', etc.",
        }
        return f"""You are an Agile Estimator. Estimate effort using {method}.

{guides.get(method, guides["story_points"])}

Consider these factors:
- **Complexity**: Technical difficulty, algorithm complexity
- **Uncertainty**: Unknowns, research needed, vague requirements
- **Volume**: Amount of code, tests, documentation
- **Dependencies**: Blocked by other teams, external APIs, decisions
- **Risk**: Likelihood of rework, integration issues

Output format: Table with columns [ID, Title, Estimate, Confidence (1-5), Notes]
If team_velocity > 0, also suggest sprint allocation."""

    def _build_prompt(self, content: str, method: str, baseline_story: str, team_velocity: int) -> str:
        return f"""Items to Estimate:
```
{content}
```

Method: {method}
Baseline Reference: {baseline_story or "None provided"}
Team Velocity: {team_velocity or "Not provided"} pts/sprint

Estimate each item. Output as markdown table."""

    def _fallback_estimates(self, content: str, method: str, error: str) -> str:
        return f"""# Effort Estimates (Fallback)
*Note: {error}*

## Method: {method}

## Items to Estimate
```
{content[:2000]}
```

## Manual Estimation Required
Use {method} scale:
- Fibonacci: 1, 2, 3, 5, 8, 13, 21
- T-Shirt: XS, S, M, L, XL
- Hours: 1, 2, 4, 8, 16, 24, 40

| ID | Title | Estimate | Confidence | Notes |
|----|-------|----------|------------|-------|
| US-001 | ... | ... | ... | ... |
"""