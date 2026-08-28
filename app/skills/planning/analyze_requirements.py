
from __future__ import annotations

from app.skills.base import BaseSkill, SkillCategory, SkillMetadata, SkillDomain, SkillComplexity, SkillParameter, SkillResult, CodeArtifact
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class AnalyzeRequirementsSkill(BaseSkill):
    name = "planning.analyze_requirements"
    description = "Analyze project documentation (kanban, backlog, README, specs) and extract structured requirements: functional, non-functional, constraints, risks, assumptions."
    category = SkillCategory.PLANNING
    parameters = [
        SkillParameter(
            name="source_files",
            description="List of file paths to analyze (e.g. kanban.txt, backlog.md, README.md, SPEC.md)",
            type="array",
            required=True,
        ),
        SkillParameter(
            name="project_context",
            description="Additional context about the project (stack, team, domain)",
            type="string",
            required=False,
            default="",
        ),
        SkillParameter(
            name="output_format",
            description="Output format for requirements",
            type="string",
            required=False,
            default="markdown",
            enum=["markdown", "json", "yaml"],
        ),
    ]
    metadata = SkillMetadata(
        domain=SkillDomain.PLANNING,
        complexity=SkillComplexity.MEDIUM,
        inputs=["source_files", "project_context"],
        outputs=["structured_requirements", "requirements_markdown"],
        prerequisites=[],
        tags=["requirements", "analysis", "kanban", "backlog", "planning"],
        estimated_duration_seconds=45,
    )

    async def execute(self, source_files: list[str], project_context: str = "", output_format: str = "markdown", **kwargs) -> SkillResult:
        
        file_contents = {}
        for path in source_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    file_contents[path] = f.read()
            except Exception as e:
                file_contents[path] = f"[ERROR reading file: {e}]"

        
        if self.llm:
            prompt = self._build_analysis_prompt(file_contents, project_context)
            try:
                analysis = await self.llm.complete([
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt}
                ])
                content = analysis.content
            except Exception as e:
                content = self._fallback_analysis(file_contents, project_context, str(e))
        else:
            content = self._fallback_analysis(file_contents, project_context, "No LLM available")
        
        if output_format == "json":
            import json
            try:
                parsed = json.loads(content) if content.strip().startswith("{") else {"raw": content}
                content = json.dumps(parsed, indent=2, ensure_ascii=False)
            except:
                pass

        return SkillResult(
            success=True,
            summary=f"Analyzed {len(source_files)} file(s) and extracted structured requirements",
            artifacts=[
                CodeArtifact(
                    filename="REQUIREMENTS.md" if output_format == "markdown" else "requirements.json",
                    content=content,
                    language="markdown" if output_format == "markdown" else "json",
                    description="Structured requirements extracted from source documents",
                )
            ],
        )

    def _system_prompt(self) -> str:
        return """You are a Senior Product Manager / Business Analyst. Analyze project documentation and extract structured requirements.

Return a comprehensive requirements document with these sections:
1. **Project Overview** - What is being built, for whom, why
2. **Functional Requirements** - Features, user stories, use cases (numbered FR-001, FR-002...)
3. **Non-Functional Requirements** - Performance, security, scalability, usability (NFR-001...)
4. **Constraints** - Technical, business, regulatory, budget
5. **Assumptions** - What we assume to be true
6. **Risks** - Known risks with likelihood/impact
7. **Dependencies** - External systems, teams, decisions needed
8. **Acceptance Criteria** - How we know each requirement is done

Be specific, actionable, and traceable. Use the source documents as evidence."""

    def _build_analysis_prompt(self, file_contents: dict[str, str], project_context: str) -> str:
        files_text = "\n\n".join(f"=== {path} ===\n{content}" for path, content in file_contents.items())
        return f"""Project Context: {project_context or "Not provided"}

Source Documents:
{files_text}

Analyze the above and produce the structured requirements document."""

    def _fallback_analysis(self, file_contents: dict[str, str], project_context: str, error: str) -> str:
        lines = [
            "# Requirements Analysis (Fallback Mode)",
            f"*Note: {error}*",
            "",
            "## Source Files Analyzed",
        ]
        for path, content in file_contents.items():
            lines.append(f"- `{path}` ({len(content)} chars)")
        lines.extend([
            "",
            "## Extracted Content (Raw)",
            "```",
            "\n\n---\n\n".join(f"{path}:\n{content[:2000]}" for path, content in file_contents.items()),
            "```",
            "",
            "## Manual Analysis Required",
            "Please review the raw content above and manually structure into:",
            "1. Functional Requirements (FR-XXX)",
            "2. Non-Functional Requirements (NFR-XXX)",
            "3. Constraints & Assumptions",
            "4. Risks & Dependencies",
            "5. Acceptance Criteria",
        ])
        return "\n".join(lines)