
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import FRONTEND_EXPERT


@SkillRegistry.register
class GenerateComponentTestsSkill(BaseSkill):
    name = "frontend.generate_component_tests"
    description = (
        "Generate Vitest + Testing Library tests for a React component "
        "covering rendering, interactions, accessibility, and edge cases."
    )
    category = SkillCategory.FRONTEND
    tags = ["testing", "vitest", "testing-library", "unit-tests"]
    parameters = [
        SkillParameter("component_name", "Component to test"),
        SkillParameter("component_code", "The component source code"),
        SkillParameter(
            "test_cases",
            "Comma-separated test scenarios: render, interactions, accessibility, error-states, async, snapshots",
            required=False, default="render,interactions,accessibility",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        component_name: str,
        component_code: str,
        test_cases: str = "render,interactions,accessibility",
        **_: Any,
    ) -> SkillResult:
        test_list = [t.strip() for t in test_cases.split(",") if t.strip()]

        prompt = f"""Generate Vitest + Testing Library tests for `{component_name}`.

Component source:
```tsx
{component_code}
```

Test scenarios: {', '.join(test_list)}

Requirements:
- Use @testing-library/react: render, screen, fireEvent, userEvent, waitFor
- Use @testing-library/jest-dom matchers (toBeInTheDocument, toHaveClass, etc.)
- Use vi.fn() for mocked callbacks/handlers
- {"Test all rendered text and elements" if "render" in test_list else ""}
- {"Test user interactions (click, type, focus)" if "interactions" in test_list else ""}
- {"Test ARIA roles, labels, and keyboard nav" if "accessibility" in test_list else ""}
- {"Test loading and error states" if "error-states" in test_list else ""}
- Descriptive test names: describe + it/test
- Group related tests in describe blocks
- Mock external dependencies

Generate a complete {component_name}.test.tsx file."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=FRONTEND_EXPERT)
        else:
            code = (
                f"import {{ render, screen, fireEvent }} from '@testing-library/react'\n"
                f"import {{ describe, it, expect, vi }} from 'vitest'\n"
                f"import {{ {component_name} }} from './{component_name}'\n\n"
                f"describe('{component_name}', () => {{\n"
                f"  it('renders without crashing', () => {{\n"
                f"    render(<{component_name} />)\n"
                f"    expect(document.body).toBeTruthy()\n"
                f"  }})\n\n"
                f"  it('is accessible', () => {{\n"
                f"    const {{ container }} = render(<{component_name} />)\n"
                f"    expect(container).not.toHaveAttribute('aria-hidden', 'true')\n"
                f"  }})\n\n"
                f"  // Add more test cases here\n"
                f"}})\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated tests for `{component_name}`",
            artifacts=[CodeArtifact(filename=f"__tests__/{component_name}.test.tsx", content=code, language="tsx")],
            dev_dependencies=["vitest", "@testing-library/react", "@testing-library/jest-dom", "@testing-library/user-event"],
        )


@SkillRegistry.register
class GenerateE2ETestsSkill(BaseSkill):
    name = "frontend.generate_e2e_tests"
    description = (
        "Generate Playwright end-to-end tests for a feature flow "
        "with page objects, selectors, and CI configuration."
    )
    category = SkillCategory.FRONTEND
    tags = ["testing", "playwright", "e2e", "integration"]
    parameters = [
        SkillParameter("feature", "Feature to test (e.g. user authentication, checkout flow, product CRUD)"),
        SkillParameter("steps", "Comma-separated test steps (e.g. go to login|fill email|submit|verify redirect)"),
        SkillParameter("base_url", "Base URL to test against", required=False, default="http://localhost:3000"),
    ]

    async def execute(  # type: ignore[override]
        self,
        feature: str,
        steps: str,
        base_url: str = "http://localhost:3000",
        **_: Any,
    ) -> SkillResult:
        step_list = [s.strip() for s in steps.split("|") if s.strip()]

        test_code = (
            f"import {{ test, expect }} from '@playwright/test'\n\n"
            f"test.describe('{feature}', () => {{\n"
            f"  test.beforeEach(async ({{ page }}) => {{\n"
            f"    await page.goto('{base_url}')\n"
            f"  }})\n\n"
            f"  test('complete {feature} flow', async ({{ page }}) => {{\n"
        )

        for step in step_list:
            if step.startswith("go to"):
                path = step.replace("go to", "").strip()
                test_code += f"    await page.goto('{base_url}/{path.lstrip('/')}')\n"
            elif step.startswith("fill"):
                field = step.replace("fill", "").strip()
                test_code += f"    await page.fill('[placeholder=\"{field}\"]', 'test-{field}')\n"
            elif step.startswith("click"):
                el = step.replace("click", "").strip()
                test_code += f"    await page.click('button:has-text(\"{el}\")')\n"
            elif step.startswith("verify"):
                what = step.replace("verify", "").strip()
                test_code += f"    await expect(page.getByText('{what}')).toBeVisible()\n"
            elif step.startswith("submit"):
                test_code += "    await page.keyboard.press('Enter')\n    await page.waitForNavigation()\n"
            else:
                test_code += f"    // TODO: {step}\n"

        test_code += "  })\n})\n"

        playwright_config = (
            "import { defineConfig, devices } from '@playwright/test'\n\n"
            "export default defineConfig({\n"
            "  testDir: './e2e',\n"
            "  fullyParallel: true,\n"
            "  forbidOnly: !!process.env.CI,\n"
            "  retries: process.env.CI ? 2 : 0,\n"
            "  reporter: process.env.CI ? 'github' : 'html',\n"
            "  use: {\n"
            f"    baseURL: '{base_url}',\n"
            "    trace: 'on-first-retry',\n"
            "  },\n"
            "  projects: [\n"
            "    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },\n"
            "    { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },\n"
            "  ],\n"
            "  webServer: {\n"
            "    command: 'npm run dev',\n"
            f"    url: '{base_url}',\n"
            "    reuseExistingServer: !process.env.CI,\n"
            "  },\n"
            "})\n"
        )

        safe_name = feature.lower().replace(" ", "-")
        return SkillResult(
            success=True,
            summary=f"Generated E2E tests for `{feature}` with {len(step_list)} steps",
            artifacts=[
                CodeArtifact(filename=f"e2e/{safe_name}.spec.ts", content=test_code, language="typescript"),
                CodeArtifact(filename="playwright.config.ts", content=playwright_config, language="typescript"),
            ],
            dev_dependencies=["@playwright/test"],
            instructions=["npx playwright install", "npx playwright test"],
        )
