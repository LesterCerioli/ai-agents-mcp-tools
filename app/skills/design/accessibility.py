
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import DESIGN_EXPERT


@SkillRegistry.register
class AuditAccessibilitySkill(BaseSkill):
    name = "design.audit_accessibility"
    description = (
        "Analyze a component for accessibility issues and generate a corrected version "
        "following WCAG 2.2 AA standards with ARIA, keyboard nav, and focus management."
    )
    category = SkillCategory.DESIGN
    tags = ["accessibility", "a11y", "wcag", "aria", "keyboard"]
    parameters = [
        SkillParameter("component_code", "The component code to audit (paste the TSX/JSX code)"),
        SkillParameter(
            "issues_to_fix",
            "Specific issues to address (comma-separated): aria-labels, focus-management, keyboard-nav, color-contrast, semantic-html, skip-links",
            required=False, default="aria-labels,keyboard-nav,semantic-html",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        component_code: str,
        issues_to_fix: str = "aria-labels,keyboard-nav,semantic-html",
        **_: Any,
    ) -> SkillResult:
        issues = [i.strip() for i in issues_to_fix.split(",") if i.strip()]

        prompt = f"""Audit this React component for WCAG 2.2 AA accessibility issues and fix them.

Component code:
```tsx
{component_code}
```

Issues to specifically address: {', '.join(issues)}

For each issue found:
1. Identify the problem
2. Explain why it fails WCAG
3. Show the fix

Then generate the fully corrected component with:
- Proper semantic HTML (nav, main, article, section, aside, header, footer)
- ARIA labels for icon-only buttons and interactive elements
- aria-expanded, aria-controls for toggles/accordions
- role="alert" or aria-live for dynamic content
- Keyboard navigation (tab order, escape key, enter/space activation)
- Focus visible styles (focus-visible:ring-2)
- Screen reader only text with sr-only class
- Proper heading hierarchy (h1 → h2 → h3)

Return the fixed component and a list of changes made."""

        if self.llm:
            result = await self.llm.chat(prompt, system_prompt=DESIGN_EXPERT)
            code = result
        else:
            code = "// Accessibility audit requires LLM. Provide HUGGINGFACE_TOKEN in .env"

        return SkillResult(
            success=True,
            summary=f"Accessibility audit addressing: {', '.join(issues)}",
            artifacts=[CodeArtifact(filename="component-a11y-fixed.tsx", content=code, language="tsx")],
            next_steps=[
                "Run: npx axe-core to validate",
                "Test with screen reader (NVDA, VoiceOver)",
                "Run Lighthouse accessibility audit",
                "Check color contrast with https://webaim.org/resources/contrastchecker/",
            ],
        )


@SkillRegistry.register
class GenerateSkipLinksSkill(BaseSkill):
    name = "design.generate_skip_links"
    description = "Generate accessible skip navigation links for keyboard users."
    category = SkillCategory.DESIGN
    tags = ["accessibility", "skip-links", "keyboard", "navigation"]
    parameters = [
        SkillParameter("targets", "Comma-separated section IDs to skip to (e.g. main-content,navigation,footer)", required=False, default="main-content,navigation"),
    ]

    async def execute(  # type: ignore[override]
        self,
        targets: str = "main-content,navigation",
        **_: Any,
    ) -> SkillResult:
        target_list = [t.strip() for t in targets.split(",") if t.strip()]

        links = "\n".join(
            f"      <a\n"
            f"        href=\"#{t}\"\n"
            f"        className=\"sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 z-50 rounded-md bg-background px-4 py-2 text-sm font-medium ring-2 ring-ring\"\n"
            f"      >\n"
            f"        Skip to {t.replace('-', ' ')}\n"
            f"      </a>"
            for t in target_list
        )

        code = (
            "export function SkipLinks() {\n"
            "  return (\n"
            "    <nav aria-label=\"Skip navigation\" className=\"fixed top-0 left-0\">\n"
            f"{links}\n"
            "    </nav>\n"
            "  )\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated skip links for: {', '.join(target_list)}",
            artifacts=[CodeArtifact(filename="components/SkipLinks.tsx", content=code, language="tsx")],
            instructions=[
                "Add <SkipLinks /> as the first child of <body>",
                f"Add id=\"{target_list[0]}\" to your main content element",
            ],
        )
