
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import DESIGN_EXPERT


@SkillRegistry.register
class GenerateColorPaletteSkill(BaseSkill):
    name = "design.generate_color_palette"
    description = (
        "Generate a complete, accessible color palette with light/dark variants, "
        "semantic colors, and CSS custom properties from a base brand color."
    )
    category = SkillCategory.DESIGN
    tags = ["colors", "palette", "design-tokens", "accessibility", "dark-mode"]
    parameters = [
        SkillParameter("brand_color", "Primary brand color in hex (e.g. #7c3aed)"),
        SkillParameter("palette_name", "Name for the color scale (e.g. violet, ocean, forest)", required=False, default="primary"),
        SkillParameter(
            "style", "Color style", required=False, default="vibrant",
            enum=["vibrant", "muted", "pastel", "deep", "corporate"],
        ),
        SkillParameter("generate_semantic", "Generate semantic colors (success, warning, error, info)", required=False, default="true", enum=["true", "false"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        brand_color: str,
        palette_name: str = "primary",
        style: str = "vibrant",
        generate_semantic: str = "true",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate a complete color system for brand color {brand_color}.

Palette name: {palette_name}
Style: {style}
Include semantic colors: {generate_semantic}

Generate:
1. A 50-950 scale (like Tailwind) for the brand color
2. CSS custom properties in HSL for theming
3. {"Semantic colors: --color-success (green), --color-warning (amber), --color-error (red), --color-info (blue)" if generate_semantic == "true" else ""}
4. Suggested Tailwind config extension
5. Ensure WCAG AA contrast (4.5:1 for normal text, 3:1 for large text)

Format:
- CSS variables block
- JavaScript/TS color object for Tailwind
- Usage examples in Tailwind classes

Colors must work for both light and dark modes."""

        if self.llm:
            result = await self.llm.chat(prompt, system_prompt=DESIGN_EXPERT)
        else:
            result = f"""/* Color palette for {brand_color} */
:root {{
  --{palette_name}-50: /* lightest tint */;
  --{palette_name}-100: ;
  --{palette_name}-200: ;
  --{palette_name}-300: ;
  --{palette_name}-400: ;
  --{palette_name}-500: {brand_color}; /* base */
  --{palette_name}-600: ;
  --{palette_name}-700: ;
  --{palette_name}-800: ;
  --{palette_name}-900: ;
  --{palette_name}-950: ; /* darkest shade */
}}

/* Semantic colors */
--color-success: 142 76% 36%;
--color-warning: 38 92% 50%;
--color-error: 0 84% 60%;
--color-info: 217 91% 60%;"""

        return SkillResult(
            success=True,
            summary=f"Generated {style} color palette for {brand_color}",
            artifacts=[CodeArtifact(
                filename="design/color-palette.css",
                content=result if isinstance(result, str) and ":" in result else f"/* Generated palette for {brand_color} */\n{result}",
                language="css",
            )],
            next_steps=[
                "Add CSS variables to globals.css",
                "Extend Tailwind config with the color scale",
                "Test contrast ratios with WebAIM Contrast Checker",
            ],
        )


@SkillRegistry.register
class GenerateDarkModeSkill(BaseSkill):
    name = "design.implement_dark_mode"
    description = (
        "Implement dark mode with ThemeProvider, system preference detection, "
        "persistent user preference, and smooth transitions."
    )
    category = SkillCategory.DESIGN
    tags = ["dark-mode", "theme", "next-themes", "css-variables"]
    parameters = [
        SkillParameter(
            "provider", "Theme provider library", required=False, default="next-themes",
            enum=["next-themes", "custom"],
        ),
        SkillParameter("themes", "Available themes (comma-separated)", required=False, default="light,dark,system"),
        SkillParameter("default_theme", "Default theme", required=False, default="system", enum=["light", "dark", "system"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        provider: str = "next-themes",
        themes: str = "light,dark,system",
        default_theme: str = "system",
        **_: Any,
    ) -> SkillResult:
        theme_list = [t.strip() for t in themes.split(",") if t.strip()]

        provider_code = (
            '"use client"\n\n'
            'import { ThemeProvider as NextThemesProvider } from "next-themes"\n'
            'import type { ThemeProviderProps } from "next-themes"\n\n'
            'export function ThemeProvider({ children, ...props }: ThemeProviderProps) {\n'
            '  return <NextThemesProvider {...props}>{children}</NextThemesProvider>\n'
            '}\n'
        )

        toggle_code = (
            '"use client"\n\n'
            'import { useTheme } from "next-themes"\n'
            'import { Moon, Sun, Monitor } from "lucide-react"\n'
            'import { Button } from "@/components/ui/button"\n'
            'import {\n'
            '  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger\n'
            '} from "@/components/ui/dropdown-menu"\n\n'
            'export function ThemeToggle() {\n'
            '  const { setTheme, theme } = useTheme()\n'
            '  return (\n'
            '    <DropdownMenu>\n'
            '      <DropdownMenuTrigger asChild>\n'
            '        <Button variant="ghost" size="icon" aria-label="Toggle theme">\n'
            '          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />\n'
            '          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />\n'
            '        </Button>\n'
            '      </DropdownMenuTrigger>\n'
            '      <DropdownMenuContent align="end">\n'
            + "".join(
                f'        <DropdownMenuItem onClick={{() => setTheme("{t}")}}>{t.title()}</DropdownMenuItem>\n'
                for t in theme_list
            )
            + '      </DropdownMenuContent>\n'
            '    </DropdownMenu>\n'
            '  )\n'
            '}\n'
        )

        layout_snippet = (
            "// In app/layout.tsx, wrap with ThemeProvider:\n"
            "<ThemeProvider\n"
            f'  attribute="class"\n'
            f'  defaultTheme="{default_theme}"\n'
            f'  enableSystem\n'
            f'  disableTransitionOnChange\n'
            ">\n"
            "  {children}\n"
            "</ThemeProvider>\n"
        )

        return SkillResult(
            success=True,
            summary=f"Implemented dark mode with {provider} ({default_theme} default)",
            artifacts=[
                CodeArtifact(filename="components/theme-provider.tsx", content=provider_code, language="tsx"),
                CodeArtifact(filename="components/theme-toggle.tsx", content=toggle_code, language="tsx"),
                CodeArtifact(filename="DARK_MODE_SETUP.md", content=f"```tsx\n{layout_snippet}\n```", language="markdown"),
            ],
            dependencies=["next-themes"],
            instructions=[
                "npm install next-themes",
                "Add ThemeProvider to app/layout.tsx",
                "Add ThemeToggle to your navigation",
            ],
        )
