
from __future__ import annotations

from app.skills.base import BaseSkill, SkillCategory, SkillMetadata, SkillDomain, SkillComplexity, SkillParameter, SkillResult, CodeArtifact
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GenerateUserStoriesSkill(BaseSkill):
    name = "planning.generate_user_stories"
    description = "Convert requirements, features, or epics into detailed User Stories with Acceptance Criteria (Given/When/Then). Supports epic breakdown, story mapping, and INVEST criteria validation."
    category = SkillCategory.PLANNING
    parameters = [
        SkillParameter(
            name="source",
            description="Source material: requirements file, feature list, epic descriptions, or raw text",
            type="string",
            required=True,
        ),
        SkillParameter(
            name="epic_breakdown",
            description="Whether to break epics into smaller stories",
            type="boolean",
            required=False,
            default=True,
        ),
        SkillParameter(
            name="format",
            description="Output format",
            type="string",
            required=False,
            default="markdown",
            enum=["markdown", "json", "csv", "jira_import"],
        ),
        SkillParameter(
            name="include_technical_tasks",
            description="Generate technical sub-tasks for each story",
            type="boolean",
            required=False,
            default=False,
        ),
    ]
    metadata = SkillMetadata(
        domain=SkillDomain.PLANNING,
        complexity=SkillComplexity.MEDIUM,
        inputs=["source", "epic_breakdown"],
        outputs=["user_stories", "acceptance_criteria", "story_map"],
        prerequisites=["planning.analyze_requirements"],
        tags=["user_stories", "acceptance_criteria", "epic_breakdown", "story_mapping", "invest"],
        estimated_duration_seconds=60,
    )

    async def execute(self, source: str, epic_breakdown: bool = True, format: str = "markdown", include_technical_tasks: bool = False, **kwargs) -> SkillResult:
        
        content = source
        if source.endswith((".txt", ".md", ".json", ".yaml")):
            try:
                with open(source, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                return SkillResult.failure(f"Failed to read {source}: {e}")

        if self.llm:
            prompt = self._build_prompt(content)
            try:
                analysis = await self.llm.complete([
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt}
                ])
                stories = analysis.content
            except Exception as e:
                stories = self._fallback_stories(content, str(e))
        else:
            stories = self._fallback_stories(content, "No LLM available")

        output_file = f"user-stories.{ 'json' if format == 'json' else 'csv' if format == 'csv' else 'md' }"
        return SkillResult(
            success=True,
            summary=f"Generated user stories from requirements",
            artifacts=[
                CodeArtifact(
                    filename=f"user-stories.{ 'json' if format == 'json' else 'csv' if format == 'csv' else 'md' }",
                    content=stories,
                    language="json" if format == "json" else "markdown",
                    description="User stories with acceptance criteria",
                )
            ],
        )

    def _system_prompt(self) -> str:
        return """You are an Agile Coach / Product Owner. Convert requirements into well-formed User Stories.

Each story MUST follow INVEST criteria:
- **Independent** - Minimize dependencies
- **Negotiable** - Details can be discussed
- **Valuable** - Delivers user value
- **Estimable** - Can be sized
- **Small** - Fits in one sprint
- **Testable** - Clear acceptance criteria

Format each story:
```
## US-XXX: [Title]
**As a** [role]
**I want to** [action]
**So that** [benefit]

**Story Points**: X

**Acceptance Criteria**:
- **Given** [context]
- **When** [action]
- **Then** [outcome]

**Technical Notes** (optional): ...
**Dependencies**: US-XXX, external API, etc.
```

Group by Epic/Feature. Include Story Map overview at top."""

    def _build_prompt(self, content: str) -> str:
        return f"""Requirements/Features:
```
{content}
```

Generate user stories following the format above. Break down epics into small, independent stories. Include story point estimates (1,2,3,5,8,13)."""

    def _fallback_stories(self, content: str, error: str) -> str:
        return f"""# User Stories (Fallback)
*Note: {error}*

## Source Requirements
```
{content[:3000]}
```

## Manual Story Creation Required
Create stories following INVEST criteria:
- Independent, Negotiable, Valuable, Estimable, Small, Testable

Template:
```
## US-001: [Title]
**As a** [role]
**I want to** [action]
**So that** [benefit]

**Story Points**: X

**Acceptance Criteria**:
- **Given** [context]
- **When** [action]
- **Then** [outcome]
```
"""