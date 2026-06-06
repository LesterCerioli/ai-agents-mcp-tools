"""Tailwind CSS design skills."""
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import DESIGN_EXPERT


@SkillRegistry.register
class GenerateTailwindConfigSkill(BaseSkill):
    name = "design.generate_tailwind_config"
    description = (
        "Generate a complete Tailwind CSS v4 configuration with custom design tokens, "
        "color palette, typography, spacing scale, and plugin setup."
    )
    category = SkillCategory.DESIGN
    tags = ["tailwind", "config", "design-tokens", "theme"]
    parameters = [
        SkillParameter("brand_colors", "Brand colors as name:hex pairs (e.g. primary:#7c3aed,secondary:#0ea5e9)"),
        SkillParameter(
            "plugins",
            "Comma-separated Tailwind plugins: typography, forms, aspect-ratio, container-queries",
            required=False, default="typography",
        ),
        SkillParameter("dark_mode", "Dark mode strategy", required=False, default="class", enum=["class", "media"]),
        SkillParameter("fonts", "Custom font CSS variable names (e.g. --font-sans:Inter,--font-heading:Playfair)", required=False, default=""),
    ]

    async def execute(  # type: ignore[override]
        self,
        brand_colors: str,
        plugins: str = "typography",
        dark_mode: str = "class",
        fonts: str = "",
        **_: Any,
    ) -> SkillResult:
        color_pairs = {}
        for pair in brand_colors.split(","):
            if ":" in pair:
                name, value = pair.split(":", 1)
                color_pairs[name.strip()] = value.strip()

        plugin_list = [p.strip() for p in plugins.split(",") if p.strip()]
        font_pairs = {}
        for pair in fonts.split(","):
            if ":" in pair:
                var, name = pair.split(":", 1)
                font_pairs[var.strip().lstrip("--")] = name.strip()

        config = (
            "import type { Config } from 'tailwindcss'\n"
            + "".join(f"import {p.replace('-', '')}Plugin from '@tailwindcss/{p}'\n" for p in plugin_list)
            + "\n"
            "const config: Config = {\n"
            f"  darkMode: '{dark_mode}',\n"
            "  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],\n"
            "  theme: {\n"
            "    extend: {\n"
            "      colors: {\n"
        )

        for name, hex_val in color_pairs.items():
            config += (
                f"        {name}: {{\n"
                f"          DEFAULT: '{hex_val}',\n"
                f"          foreground: 'hsl(var(--{name}-foreground))',\n"
                f"        }},\n"
            )

        config += (
            "        background: 'hsl(var(--background))',\n"
            "        foreground: 'hsl(var(--foreground))',\n"
            "        border: 'hsl(var(--border))',\n"
            "        input: 'hsl(var(--input))',\n"
            "        ring: 'hsl(var(--ring))',\n"
            "        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },\n"
            "        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },\n"
            "        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },\n"
            "      },\n"
        )

        if font_pairs:
            config += "      fontFamily: {\n"
            for var, name in font_pairs.items():
                config += f"        '{var}': ['var(--font-{var})', '{name}', 'sans-serif'],\n"
            config += "      },\n"

        config += (
            "      borderRadius: {\n"
            "        lg: 'var(--radius)',\n"
            "        md: 'calc(var(--radius) - 2px)',\n"
            "        sm: 'calc(var(--radius) - 4px)',\n"
            "      },\n"
            "    },\n"
            "  },\n"
        )

        if plugin_list:
            config += f"  plugins: [{', '.join(p.replace('-', '') + 'Plugin' for p in plugin_list)}],\n"

        config += "}\n\nexport default config\n"

        deps = [f"@tailwindcss/{p}" for p in plugin_list]

        return SkillResult(
            success=True,
            summary=f"Generated Tailwind config with {len(color_pairs)} brand colors",
            artifacts=[CodeArtifact(filename="tailwind.config.ts", content=config, language="typescript")],
            dev_dependencies=["tailwindcss", "postcss", "autoprefixer"] + deps,
        )


@SkillRegistry.register
class GenerateDesignTokensCSSSkill(BaseSkill):
    name = "design.generate_design_tokens_css"
    description = (
        "Generate CSS custom properties (design tokens) for light and dark themes "
        "compatible with shadcn/ui, Tailwind, and any component library."
    )
    category = SkillCategory.DESIGN
    tags = ["design-tokens", "css-variables", "dark-mode", "theming", "shadcn"]
    parameters = [
        SkillParameter("primary_hsl", "Primary color in HSL (e.g. 262 83% 58%)"),
        SkillParameter(
            "style", "Design style", required=False, default="modern",
            enum=["modern", "minimal", "bold", "soft", "corporate"],
        ),
        SkillParameter("border_radius", "Base border radius (e.g. 0.5rem, 0.75rem, 1rem)", required=False, default="0.5rem"),
    ]

    async def execute(  # type: ignore[override]
        self,
        primary_hsl: str,
        style: str = "modern",
        border_radius: str = "0.5rem",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate CSS custom properties for a {style} design system.

Primary color (HSL): {primary_hsl}
Border radius: {border_radius}

Generate a globals.css with:
- :root {{ }} for light theme
- .dark {{ }} for dark theme
- All shadcn/ui required variables: --background, --foreground, --card, --popover, --primary, --primary-foreground, --secondary, --muted, --accent, --destructive, --border, --input, --ring
- --radius variable
- Smooth color transitions
- Derive complementary colors from the primary HSL

Format as valid CSS with @layer base."""

        if self.llm:
            code = await self.llm.chat(prompt, system_prompt=DESIGN_EXPERT)
        else:
            code = (
                "@layer base {\n"
                "  :root {\n"
                "    --background: 0 0% 100%;\n"
                "    --foreground: 240 10% 3.9%;\n"
                "    --card: 0 0% 100%;\n"
                "    --card-foreground: 240 10% 3.9%;\n"
                "    --popover: 0 0% 100%;\n"
                "    --popover-foreground: 240 10% 3.9%;\n"
                f"    --primary: {primary_hsl};\n"
                "    --primary-foreground: 0 0% 98%;\n"
                "    --secondary: 240 4.8% 95.9%;\n"
                "    --secondary-foreground: 240 5.9% 10%;\n"
                "    --muted: 240 4.8% 95.9%;\n"
                "    --muted-foreground: 240 3.8% 46.1%;\n"
                "    --accent: 240 4.8% 95.9%;\n"
                "    --accent-foreground: 240 5.9% 10%;\n"
                "    --destructive: 0 84.2% 60.2%;\n"
                "    --destructive-foreground: 0 0% 98%;\n"
                "    --border: 240 5.9% 90%;\n"
                "    --input: 240 5.9% 90%;\n"
                "    --ring: 240 10% 3.9%;\n"
                f"    --radius: {border_radius};\n"
                "  }\n\n"
                "  .dark {\n"
                "    --background: 240 10% 3.9%;\n"
                "    --foreground: 0 0% 98%;\n"
                "    --card: 240 10% 3.9%;\n"
                "    --card-foreground: 0 0% 98%;\n"
                "    --popover: 240 10% 3.9%;\n"
                "    --popover-foreground: 0 0% 98%;\n"
                f"    --primary: {primary_hsl};\n"
                "    --primary-foreground: 0 0% 98%;\n"
                "    --secondary: 240 3.7% 15.9%;\n"
                "    --secondary-foreground: 0 0% 98%;\n"
                "    --muted: 240 3.7% 15.9%;\n"
                "    --muted-foreground: 240 5% 64.9%;\n"
                "    --accent: 240 3.7% 15.9%;\n"
                "    --accent-foreground: 0 0% 98%;\n"
                "    --destructive: 0 62.8% 30.6%;\n"
                "    --destructive-foreground: 0 0% 98%;\n"
                "    --border: 240 3.7% 15.9%;\n"
                "    --input: 240 3.7% 15.9%;\n"
                "    --ring: 240 4.9% 83.9%;\n"
                "  }\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated {style} design tokens CSS",
            artifacts=[CodeArtifact(filename="app/globals.css", content=code, language="css")],
        )


@SkillRegistry.register
class GenerateResponsiveLayoutSkill(BaseSkill):
    name = "design.generate_responsive_layout"
    description = (
        "Generate responsive Tailwind CSS layout components for common patterns "
        "like hero sections, feature grids, pricing tables, and dashboards."
    )
    category = SkillCategory.DESIGN
    tags = ["layout", "responsive", "tailwind", "sections", "ui"]
    parameters = [
        SkillParameter(
            "pattern", "Layout pattern", enum=[
                "hero", "feature-grid", "pricing-table", "dashboard-shell",
                "blog-layout", "product-grid", "testimonials", "cta-section",
                "stats-row", "team-grid",
            ],
        ),
        SkillParameter("content", "Content description (what goes in each section)", required=False, default=""),
        SkillParameter("columns", "Number of columns in grid patterns (2, 3, 4)", required=False, default="3"),
    ]

    async def execute(  # type: ignore[override]
        self,
        pattern: str,
        content: str = "",
        columns: str = "3",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate a responsive {pattern} layout component using Tailwind CSS.

{"Content: " + content if content else ""}
Columns: {columns}

Requirements:
- Mobile-first responsive design
- Tailwind CSS utility classes
- TypeScript with proper props interface
- shadcn/ui components where appropriate
- Accessible semantic HTML
- Support dark mode via Tailwind dark: variant
- Smooth hover states and transitions
- {"Container with max-width and auto margins" if pattern != "dashboard-shell" else "Full-height sidebar + main content layout"}

Generate a complete, beautiful component ready to copy-paste."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=DESIGN_EXPERT)
        else:
            col_cls = {"2": "sm:grid-cols-2", "3": "sm:grid-cols-2 lg:grid-cols-3", "4": "sm:grid-cols-2 lg:grid-cols-4"}.get(columns, "sm:grid-cols-3")

            patterns = {
                "hero": (
                    "export function HeroSection() {\n"
                    "  return (\n"
                    "    <section className=\"relative isolate overflow-hidden bg-background px-6 py-24 sm:py-32 lg:px-8\">\n"
                    "      <div className=\"mx-auto max-w-2xl text-center\">\n"
                    "        <h1 className=\"text-4xl font-bold tracking-tight sm:text-6xl\">Your Headline Here</h1>\n"
                    "        <p className=\"mt-6 text-lg leading-8 text-muted-foreground\">Supporting description text that explains value proposition.</p>\n"
                    "        <div className=\"mt-10 flex items-center justify-center gap-x-6\">\n"
                    "          <a href=\"#\" className=\"rounded-md bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90\">Get started</a>\n"
                    "          <a href=\"#\" className=\"text-sm font-semibold\">Learn more <span aria-hidden>→</span></a>\n"
                    "        </div>\n"
                    "      </div>\n"
                    "    </section>\n"
                    "  )\n"
                    "}\n"
                ),
                "feature-grid": (
                    f"const features = Array.from({{ length: 6 }}, (_, i) => ({{\n"
                    f"  title: `Feature ${{i + 1}}`,\n"
                    f"  description: 'Feature description goes here explaining the benefit.',\n"
                    f"  icon: '✦',\n"
                    f"}})\n\n"
                    f"export function FeatureGrid() {{\n"
                    f"  return (\n"
                    f"    <section className=\"py-24 px-6\">\n"
                    f"      <div className=\"mx-auto max-w-7xl\">\n"
                    f"        <h2 className=\"text-3xl font-bold text-center mb-12\">Features</h2>\n"
                    f"        <dl className=\"grid grid-cols-1 gap-8 {col_cls}\">\n"
                    f"          {{features.map(f => (\n"
                    f"            <div key={{f.title}} className=\"rounded-2xl border bg-card p-6 shadow-sm hover:shadow-md transition-shadow\">\n"
                    f"              <dt className=\"flex items-center gap-3 text-lg font-semibold\">\n"
                    f"                <span className=\"text-2xl\" aria-hidden>{{f.icon}}</span>\n"
                    f"                {{f.title}}\n"
                    f"              </dt>\n"
                    f"              <dd className=\"mt-2 text-muted-foreground\">{{f.description}}</dd>\n"
                    f"            </div>\n"
                    f"          ))}}\n"
                    f"        </dl>\n"
                    f"      </div>\n"
                    f"    </section>\n"
                    f"  )\n"
                    f"}}\n"
                ),
            }
            code = patterns.get(pattern, patterns["hero"])

        return SkillResult(
            success=True,
            summary=f"Generated responsive `{pattern}` layout",
            artifacts=[CodeArtifact(
                filename=f"components/sections/{pattern.replace('-', '_').title().replace('_', '')}.tsx",
                content=code, language="tsx",
            )],
        )
