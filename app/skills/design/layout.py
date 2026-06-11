"""Layout pattern skills."""
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import DESIGN_EXPERT


@SkillRegistry.register
class GenerateDesignSystemSkill(BaseSkill):
    name = "design.generate_design_system"
    description = (
        "Generate a complete design system with tokens, component variants, "
        "and usage documentation — the foundation for a consistent UI."
    )
    category = SkillCategory.DESIGN
    tags = ["design-system", "tokens", "components", "documentation"]
    parameters = [
        SkillParameter("brand_name", "Brand/product name"),
        SkillParameter("primary_color", "Primary brand color hex"),
        SkillParameter(
            "personality",
            "Brand personality", required=False, default="modern",
            enum=["modern", "playful", "corporate", "minimal", "bold"],
        ),
        SkillParameter("components", "Components to include (comma-separated)", required=False, default="button,card,input,badge,avatar"),
    ]

    async def execute(  # type: ignore[override]
        self,
        brand_name: str,
        primary_color: str,
        personality: str = "modern",
        components: str = "button,card,input,badge,avatar",
        **_: Any,
    ) -> SkillResult:
        comp_list = [c.strip() for c in components.split(",") if c.strip()]

        prompt = f"""Design a complete design system for `{brand_name}`.

Brand color: {primary_color}
Personality: {personality}
Components: {', '.join(comp_list)}

Generate:
1. Design token definitions (colors, spacing, typography, shadows, radii)
2. Component style variants for: {', '.join(comp_list)}
3. CSS custom properties in globals.css
4. Tailwind config extension

For each component, define variants:
- button: primary, secondary, outline, ghost, destructive (+ sm/md/lg sizes)
- card: default, elevated, outlined, ghost
- input: default, error, success states
- badge: default, outline, destructive, success, warning

Make it feel {personality}: {"clean edges, subtle shadows" if personality == "modern" else "rounded, colorful" if personality == "playful" else "sharp, professional" if personality == "corporate" else "minimal strokes" if personality == "minimal" else "high contrast, strong type"}"""

        if self.llm:
            code = await self.llm.chat(prompt, system_prompt=DESIGN_EXPERT)
        else:
            code = (
                f"/* {brand_name} Design System */\n\n"
                ":root {\n"
                f"  /* Brand: {primary_color} */\n"
                f"  --color-brand: {primary_color};\n"
                "  \n"
                "  /* Spacing scale (4px base) */\n"
                "  --space-1: 4px; --space-2: 8px; --space-3: 12px;\n"
                "  --space-4: 16px; --space-6: 24px; --space-8: 32px;\n"
                "  \n"
                "  /* Border radius */\n"
                "  --radius-sm: 4px; --radius-md: 8px;\n"
                "  --radius-lg: 12px; --radius-full: 9999px;\n"
                "  \n"
                "  /* Shadows */\n"
                "  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);\n"
                "  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);\n"
                "  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated {personality} design system for {brand_name}",
            artifacts=[CodeArtifact(filename="design/system.css", content=code, language="css")],
            next_steps=[
                "Import design/system.css in app/globals.css",
                "Create component variants using cva() from class-variance-authority",
                "Document with Storybook: npx storybook@latest init",
            ],
            dependencies=["class-variance-authority", "clsx", "tailwind-merge"],
        )


@SkillRegistry.register
class GenerateSidebarLayoutSkill(BaseSkill):
    name = "design.generate_sidebar_layout"
    description = "Generate a responsive sidebar + main content layout with collapsible sidebar, breadcrumbs, and topbar."
    category = SkillCategory.DESIGN
    tags = ["layout", "sidebar", "responsive", "navigation", "shadcn"]
    parameters = [
        SkillParameter("app_name", "Application name"),
        SkillParameter("sidebar_width", "Sidebar width in pixels", required=False, default="256"),
        SkillParameter(
            "features",
            "Comma-separated features: collapsible, breadcrumbs, user-menu, search, notifications",
            required=False, default="collapsible,breadcrumbs,user-menu",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_name: str,
        sidebar_width: str = "256",
        features: str = "collapsible,breadcrumbs,user-menu",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        code = (
            '"use client"\n\n'
            'import { useState } from "react"\n'
            'import { PanelLeftClose, PanelLeftOpen } from "lucide-react"\n'
            'import { Button } from "@/components/ui/button"\n\n'
            f"const SIDEBAR_WIDTH = {sidebar_width}\n\n"
            "export function SidebarLayout({ children, sidebar }: {\n"
            "  children: React.ReactNode\n"
            "  sidebar: React.ReactNode\n"
            "}) {\n"
            "  const [collapsed, setCollapsed] = useState(false)\n\n"
            "  return (\n"
            "    <div className=\"flex h-screen overflow-hidden\">\n"
            "      {/* Sidebar */}\n"
            "      <aside\n"
            "        className=\"flex-shrink-0 border-r bg-card transition-all duration-300 ease-in-out overflow-hidden\"\n"
            f"        style={{{{ width: collapsed ? 0 : SIDEBAR_WIDTH }}}}\n"
            "      >\n"
            "        <div className=\"h-full overflow-y-auto overflow-x-hidden\">\n"
            "          {sidebar}\n"
            "        </div>\n"
            "      </aside>\n\n"
            "      {/* Main area */}\n"
            "      <div className=\"flex flex-1 flex-col overflow-hidden\">\n"
            "        <header className=\"flex h-14 items-center gap-2 border-b bg-background px-4\">\n"
            "          <Button\n"
            "            variant=\"ghost\"\n"
            "            size=\"icon\"\n"
            "            onClick={() => setCollapsed(!collapsed)}\n"
            "            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}\n"
            "          >\n"
            "            {collapsed ? <PanelLeftOpen className=\"h-4 w-4\" /> : <PanelLeftClose className=\"h-4 w-4\" />}\n"
            "          </Button>\n"
            f"          <span className=\"font-semibold\">{app_name}</span>\n"
            "        </header>\n"
            "        <main className=\"flex-1 overflow-y-auto p-6\">\n"
            "          {children}\n"
            "        </main>\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated sidebar layout for {app_name}",
            artifacts=[CodeArtifact(filename="components/layouts/SidebarLayout.tsx", content=code, language="tsx")],
        )
