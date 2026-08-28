
from __future__ import annotations

from app.skills.base import BaseSkill, SkillCategory, SkillMetadata, SkillDomain, SkillComplexity, SkillParameter, SkillResult, CodeArtifact
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class IdentifyDependenciesSkill(BaseSkill):
    name = "planning.identify_dependencies"
    description = "Analyze tasks, user stories, or epics and identify dependencies: internal (story-to-story), external (APIs, teams, infrastructure), and sequential/parallel execution paths. Generates dependency graph and critical path."
    category = SkillCategory.PLANNING
    parameters = [
        SkillParameter(
            name="source_file",
            description="Path to file with tasks/stories (user-stories.md, backlog.txt, SPEC.md)",
            type="string",
            required=True,
        ),
        SkillParameter(
            name="include_external",
            description="Include external dependencies (APIs, third-party services, other teams, infrastructure)",
            type="boolean",
            required=False,
            default=True,
        ),
        SkillParameter(
            name="output_format",
            description="Output format for dependency graph",
            type="string",
            required=False,
            default="markdown",
            enum=["markdown", "mermaid", "json", "graphviz"],
        ),
    ]
    metadata = SkillMetadata(
        domain=SkillDomain.PLANNING,
        complexity=SkillComplexity.MEDIUM,
        inputs=["source_file"],
        outputs=["dependency_graph", "critical_path", "execution_order"],
        prerequisites=["planning.generate_user_stories", "planning.estimate_effort"],
        tags=["dependencies", "dependency_graph", "critical_path", "blocking", "sequencing"],
        estimated_duration_seconds=45,
    )

    async def execute(self, source_file: str, include_external: bool = True, output_format: str = "markdown", **kwargs) -> SkillResult:
        try:
            with open(source_file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            return SkillResult.failure(f"Failed to read {source_file}: {e}")

        if self.llm:
            prompt = self._build_prompt(content, include_external)
            try:
                analysis = await self.llm.complete([
                    {"role": "system", "content": self._system_prompt(output_format)},
                    {"role": "user", "content": prompt}
                ])
                deps = analysis.content
            except Exception as e:
                deps = self._fallback_deps(content, output_format, str(e))
        else:
            deps = self._fallback_deps(content, output_format, "No LLM available")

        ext = "mmd" if output_format == "mermaid" else "json" if output_format == "json" else "dot" if output_format == "graphviz" else "md"
        output_file = f"dependencies.{ext}"
        return SkillResult(
            success=True,
            summary=f"Identified dependencies from {source_file}",
            artifacts=[
                CodeArtifact(
                    filename=output_file,
                    content=deps,
                    language="mermaid" if output_format == "mermaid" else "json" if output_format == "json" else "dot" if output_format == "graphviz" else "markdown",
                    description="Dependency graph and critical path",
                )
            ],
        )

    def _system_prompt(self, output_format: str) -> str:
        fmt_guide = {
            "mermaid": "Output as Mermaid flowchart:\n```mermaid\ngraph TD\n  A[US-001] --> B[US-002]\n  C[External API] --> A\n```",
            "graphviz": "Output as Graphviz DOT:\n```dot\ndigraph G {\n  US001 -> US002;\n  ExternalAPI -> US001;\n}\n```",
            "json": "Output as JSON:\n```json\n{\"nodes\": [{\"id\": \"US-001\", \"type\": \"story\"}], \"edges\": [{\"from\": \"US-001\", \"to\": \"US-002\", \"type\": \"blocks\"}]}\n```",
            "markdown": "Output as Markdown with tables and Mermaid diagram embedded.",
        }
        return f"""You are a Technical Program Manager. Identify all dependencies between work items.

Types of dependencies:
- **Blocks** - A must finish before B starts
- **Relates** - A and B are related but can be parallel
- **Duplicates** - A and B are the same work
- **External** - Depends on external team, API, vendor, infrastructure, decision

Output format: {output_format}
{fmt_guide.get(output_format, fmt_guide["markdown"])}

Also provide:
1. **Critical Path** - Longest dependency chain
2. **Parallel Tracks** - Work that can run simultaneously
3. **External Dependencies** - What we're waiting on
4. **Recommended Execution Order** - Topological sort

Be explicit about WHY each dependency exists."""

    def _build_prompt(self, content: str, include_external: bool) -> str:
        return f"""Work Items:
```
{content}
```

Include External Dependencies: {include_external}

Identify all dependencies and output in the specified format."""

    def _fallback_deps(self, content: str, output_format: str, error: str) -> str:
        if output_format == "mermaid":
            return f"""# Dependency Graph (Fallback)
*Note: {error}*

```mermaid
graph TD
  A[US-001] --> B[US-002]
  C[External API] --> A
  D[US-003] --> E[US-004]
```

## Manual Analysis Required
Analyze source for dependencies."""
        elif output_format == "json":
            return f"""{{"error": "{error}", "note": "Manual analysis required"}}"""
        else:
            return f"""# Dependency Analysis (Fallback)
*Note: {error}*

## Source Content
```
{content[:2000]}
```

## Manual Dependency Analysis Required
Identify:
1. Internal dependencies (story blocks story)
2. External dependencies (APIs, teams, infra)
3. Critical path
4. Parallel tracks
"""