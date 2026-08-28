
from __future__ import annotations

from app.skills.base import BaseSkill, SkillCategory, SkillMetadata, SkillDomain, SkillComplexity, SkillParameter, SkillResult, CodeArtifact
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GenerateSpecSkill(BaseSkill):
    name = "planning.generate_spec"
    description = "Generate a comprehensive technical specification (SPEC.md) from requirements, user stories, and architecture decisions. Includes API contracts, data models, UI flows, infrastructure, testing strategy, and rollout plan."
    category = SkillCategory.PLANNING
    parameters = [
        SkillParameter(
            name="requirements_file",
            description="Path to requirements file (REQUIREMENTS.md)",
            type="string",
            required=False,
            default="",
        ),
        SkillParameter(
            name="user_stories_file",
            description="Path to user stories file (user-stories.md)",
            type="string",
            required=False,
            default="",
        ),
        SkillParameter(
            name="architecture_file",
            description="Path to architecture decisions (ARCHITECTURE.md, ADRs)",
            type="string",
            required=False,
            default="",
        ),
        SkillParameter(
            name="output_format",
            description="Output format",
            type="string",
            required=False,
            default="markdown",
            enum=["markdown", "html", "pdf_ready"],
        ),
        SkillParameter(
            name="include_api_spec",
            description="Include OpenAPI/AsyncAPI spec sections",
            type="boolean",
            required=False,
            default=True,
        ),
        SkillParameter(
            name="include_test_plan",
            description="Include test strategy and test cases",
            type="boolean",
            required=False,
            default=True,
        ),
    ]
    metadata = SkillMetadata(
        domain=SkillDomain.PLANNING,
        complexity=SkillComplexity.HIGH,
        inputs=["requirements_file", "user_stories_file", "architecture_file"],
        outputs=["technical_spec", "api_contracts", "test_plan", "rollout_plan"],
        prerequisites=["planning.analyze_requirements", "planning.generate_user_stories", "planning.identify_dependencies"],
        tags=["spec", "technical_specification", "api_design", "test_plan", "architecture", "documentation"],
        estimated_duration_seconds=120,
    )

    async def execute(self, requirements_file: str = "", user_stories_file: str = "", architecture_file: str = "", output_format: str = "markdown", include_api_spec: bool = True, include_test_plan: bool = True, **kwargs) -> SkillResult:
        
        sources = {}
        for name, path in [("requirements", requirements_file), ("user_stories", user_stories_file), ("architecture", architecture_file)]:
            if path:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        sources[name] = f.read()
                except Exception as e:
                    sources[name] = f"[ERROR: {e}]"

        if not sources:
            return SkillResult.failure("At least one source file required")

        if self.llm:
            prompt = self._build_prompt(sources, include_api_spec, include_test_plan)
            try:
                analysis = await self.llm.complete([
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt}
                ])
                spec = analysis.content
            except Exception as e:
                spec = self._fallback_spec(sources, str(e))
        else:
            spec = self._fallback_spec(sources, "No LLM available")

        ext = "md" if output_format == "markdown" else "html"
        output_file = f"SPEC.{ext}"
        return SkillResult(
            success=True,
            summary=f"Generated technical specification from {len(sources)} source(s)",
            artifacts=[
                CodeArtifact(
                    filename=output_file,
                    content=spec,
                    language="markdown",
                    description="Complete technical specification with API contracts, data models, test plan",
                )
            ],
        )

    def _system_prompt(self) -> str:
        return """You are a Senior Software Architect / Tech Lead. Generate a production-ready Technical Specification.

Structure the SPEC with these sections:

1. **Executive Summary** - What, why, for whom, timeline
2. **Functional Requirements** - Traceable to user stories (US-XXX)
3. **Non-Functional Requirements** - Performance, security, scalability, SLA
4. **System Architecture** - High-level diagram (Mermaid), components, boundaries
5. **API Contracts** - OpenAPI spec, endpoints, schemas, auth, error codes
6. **Data Models** - Entities, relationships, migrations, indexes
7. **UI/UX Flows** - Key user journeys, screen states, edge cases
8. **Infrastructure** - Deployment topology, environments, CI/CD, monitoring
9. **Security** - AuthZ/AuthN, encryption, secrets, compliance
10. **Test Strategy** - Unit, integration, contract, e2e, performance, chaos
11. **Rollout Plan** - Feature flags, canary, rollback, runbooks
12. **Open Questions / Decisions Needed** - Track with DEC-XXX IDs

Be specific, implementable, and traceable. Every requirement must map to a user story."""

    def _build_prompt(self, sources: dict[str, str], include_api_spec: bool, include_test_plan: bool) -> str:
        src_text = "\n\n".join(f"=== {name.upper()} ===\n{content}" for name, content in sources.items())
        return f"""Source Materials:
{src_text}

Options:
- Include API Spec: {include_api_spec}
- Include Test Plan: {include_test_plan}

Generate the complete SPEC.md following the structure above."""

    def _fallback_spec(self, sources: dict[str, str], error: str) -> str:
        sections = [
            f"# Technical Specification (Fallback)",
            f"*Note: {error}*",
            "",
            "## Source Materials",
        ]
        for name, content in sources.items():
            sections.append(f"### {name.title()}")
            sections.append(f"```\n{content[:1500]}\n```")
            sections.append("")
        sections.extend([
            "## Specification Structure (To Complete Manually)",
            "1. Executive Summary",
            "2. Functional Requirements (trace to US-XXX)",
            "3. Non-Functional Requirements",
            "4. System Architecture (Mermaid diagram)",
            "5. API Contracts (OpenAPI)",
            "6. Data Models (ERD)",
            "7. UI/UX Flows",
            "8. Infrastructure & Deployment",
            "9. Security & Compliance",
            "10. Test Strategy",
            "11. Rollout Plan",
            "12. Open Questions (DEC-XXX)",
        ])
        return "\n".join(sections)