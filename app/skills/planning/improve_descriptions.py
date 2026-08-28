
from __future__ import annotations

from app.skills.base import BaseSkill, SkillCategory, SkillMetadata, SkillDomain, SkillComplexity, SkillParameter, SkillResult, CodeArtifact
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class ImproveDescriptionsSkill(BaseSkill):
    name = "planning.improve_descriptions"
    description = "Rewrite task/card descriptions with clarity, structure, and proper acceptance criteria (Given/When/Then). Supports User Story format, Gherkin, or custom templates."
    category = SkillCategory.PLANNING
    parameters = [
        SkillParameter(
            name="source_file",
            description="Path to file containing tasks/cards to improve (kanban.txt, backlog.md, etc.)",
            type="string",
            required=True,
        ),
        SkillParameter(
            name="style",
            description="Output style for improved descriptions",
            type="string",
            required=False,
            default="user_story_with_ac",
            enum=["user_story_with_ac", "gherkin", "smart_goals", "jira_ticket", "markdown_checklist"],
        ),
        SkillParameter(
            name="include_estimates",
            description="Add story point estimates (1,2,3,5,8,13)",
            type="boolean",
            required=False,
            default=True,
        ),
        SkillParameter(
            name="project_context",
            description="Additional context (domain, tech stack, team conventions)",
            type="string",
            required=False,
            default="",
        ),
    ]
    metadata = SkillMetadata(
        domain=SkillDomain.PLANNING,
        complexity=SkillComplexity.MEDIUM,
        inputs=["source_file", "project_context"],
        outputs=["improved_descriptions", "acceptance_criteria"],
        prerequisites=["planning.analyze_requirements"],
        tags=["descriptions", "acceptance_criteria", "user_stories", "refinement", "kanban"],
        estimated_duration_seconds=60,
    )

    async def execute(self, source_file: str, style: str = "user_story_with_ac", include_estimates: bool = True, project_context: str = "", **kwargs) -> SkillResult:
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return SkillResult.failure(f"Failed to read {source_file}: {e}")

        if self.llm:
            prompt = self._build_prompt(content, style, include_estimates, project_context)
            try:
                analysis = await self.llm.complete([
                    {"role": "system", "content": self._system_prompt(style)},
                    {"role": "user", "content": prompt}
                ])
                improved = analysis.content
            except Exception as e:
                improved = self._fallback_improve(content, style, str(e))
        else:
            improved = self._fallback_improve(content, style, "No LLM available")

        output_file = source_file.replace(".txt", "-improved.txt").replace(".md", "-improved.md")
        return SkillResult(
            success=True,
            summary=f"Improved descriptions in {source_file} using {style} style",
            artifacts=[
                CodeArtifact(
                    filename=output_file,
                    content=improved,
                    language="markdown",
                    description=f"Improved task descriptions with acceptance criteria ({style})",
                )
            ],
        )

    def _system_prompt(self, style: str) -> str:
        base = """You are an Agile Coach / Senior PM. Rewrite task descriptions for clarity, testability, and completeness.

Rules:
- Every task MUST have clear Acceptance Criteria (Given/When/Then format)
- Use the specified output style
- Be specific, measurable, and testable
- Remove ambiguity and vague language
- Add story point estimates if requested (1,2,3,5,8,13)
- Preserve original intent while improving quality"""
        
        style_guides = {
            "user_story_with_ac": "Format: **User Story**: As a [role], I want [action], so that [benefit]\n**Acceptance Criteria**:\n- Given [context]\n- When [action]\n- Then [outcome]",
            "gherkin": "Format: Feature: [title]\nScenario: [description]\nGiven [context]\nWhen [action]\nThen [outcome]",
            "smart_goals": "Format: **Specific** - What exactly?\n**Measurable** - How to measure?\n**Achievable** - Realistic?\n**Relevant** - Why important?\n**Time-bound** - When done?",
            "jira_ticket": "Format: **Summary**: [one line]\n**Description**: [detailed]\n**Acceptance Criteria**: [numbered list]\n**Story Points**: [estimate]",
            "markdown_checklist": "Format: ## [Task Title]\n- [ ] **Description**: ...\n- [ ] **AC1**: Given/When/Then\n- [ ] **AC2**: ...\n**Estimate**: X pts",
        }
        return base + "\n\nStyle Guide:\n" + style_guides.get(style, style_guides["user_story_with_ac"])

    def _build_prompt(self, content: str, style: str, include_estimates: bool, project_context: str) -> str:
        return f"""Project Context: {project_context or "Not provided"}
Style: {style}
Include Estimates: {include_estimates}

Source Content:
```
{content}
```

Rewrite each task/card following the style guide. Return the complete improved document."""

    def _fallback_improve(self, content: str, style: str, error: str) -> str:
        return f"""# Improved Descriptions (Fallback Mode)
*Note: {error}*

## Original Content
```
{content}
```

## Manual Improvement Required
Apply {style} style manually:
- Add clear Acceptance Criteria (Given/When/Then)
- Use specific, measurable language
- Remove ambiguity
- Add story point estimates
- Structure as {style}
"""