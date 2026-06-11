"""Typography system skills."""
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class GenerateTypeScaleSkill(BaseSkill):
    name = "design.generate_type_scale"
    description = "Generate a harmonious typographic scale with fluid type sizes and proper line-heights."
    category = SkillCategory.DESIGN
    tags = ["typography", "type-scale", "fluid-type", "tailwind"]
    parameters = [
        SkillParameter("base_size", "Base font size in px", required=False, default="16"),
        SkillParameter("scale_ratio", "Scale ratio (e.g. 1.25 Major Third, 1.333 Perfect Fourth)", required=False, default="1.25"),
        SkillParameter("steps", "Number of scale steps above base (2-6)", required=False, default="5"),
    ]

    async def execute(  # type: ignore[override]
        self,
        base_size: str = "16",
        scale_ratio: str = "1.25",
        steps: str = "5",
        **_: Any,
    ) -> SkillResult:
        base = float(base_size)
        ratio = float(scale_ratio)
        num_steps = int(steps)

        sizes = {}
        step_names = ["sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl", "6xl"]
        for i in range(-1, num_steps + 1):
            size_px = base * (ratio ** i)
            name = step_names[i + 1] if i + 1 < len(step_names) else f"{i}xl"
            sizes[name] = size_px

        config = "// tailwind.config.ts — extend fontSize\ntheme: {\n  extend: {\n    fontSize: {\n"
        for name, px in sizes.items():
            line_height = max(1.2, 1.5 - (px - base) * 0.01)
            config += f"      '{name}': ['{px:.1f}px', {{ lineHeight: '{line_height:.2f}' }}],\n"
        config += "    },\n  },\n}\n"

        css = "/* Fluid type scale — globals.css */\n:root {\n"
        for name, px in sizes.items():
            css += f"  --text-{name}: {px:.1f}px;\n"
        css += "}\n"

        return SkillResult(
            success=True,
            summary=f"Generated type scale: ratio {scale_ratio}, {num_steps} steps",
            artifacts=[
                CodeArtifact(filename="design/type-scale.ts", content=config, language="typescript"),
                CodeArtifact(filename="design/type-scale.css", content=css, language="css"),
            ],
        )


@SkillRegistry.register
class SetupNextFontsSkill(BaseSkill):
    name = "design.setup_next_fonts"
    description = "Configure next/font/google with multiple font families, CSS variables, and Tailwind integration."
    category = SkillCategory.DESIGN
    tags = ["fonts", "next-font", "google-fonts", "performance", "cls"]
    parameters = [
        SkillParameter(
            "font_config",
            "Font config as name:weights:variable (e.g. Inter:400,500,600,700:--font-sans, Playfair_Display:700,900:--font-heading)",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        font_config: str,
        **_: Any,
    ) -> SkillResult:
        fonts = []
        for entry in font_config.split(","):
            parts = entry.strip().split(":")
            if len(parts) >= 1:
                name = parts[0].strip()
                weights = parts[1].strip() if len(parts) > 1 else "400,500,600,700"
                variable = parts[2].strip() if len(parts) > 2 else f"--font-{name.lower()}"
                fonts.append({"name": name, "weights": weights, "variable": variable})

        imports = "\n".join(f"import {{ {f['name']} }} from 'next/font/google'" for f in fonts)
        instances = "\n\n".join(
            f"const {f['name'].lower()} = {f['name']}({{\n"
            f"  subsets: ['latin'],\n"
            f"  weight: [{', '.join(repr(w) for w in f['weights'].split(','))}],\n"
            f"  variable: '{f['variable']}',\n"
            f"  display: 'swap',\n"
            f"}})"
            for f in fonts
        )
        class_names = " ".join(f"${{{f['name'].lower()}.variable}}" for f in fonts)
        tailwind_ext = "".join(
            f"  '{f['variable'].lstrip('--')}': ['var({f['variable']})', 'system-ui', 'sans-serif'],\n"
            for f in fonts
        )

        layout_code = (
            f"{imports}\n\n"
            f"{instances}\n\n"
            "export default function RootLayout({ children }: { children: React.ReactNode }) {\n"
            "  return (\n"
            f'    <html lang="en" className={"`{class_names}`"}>\n'
            '      <body className="font-sans antialiased">{children}</body>\n'
            "    </html>\n"
            "  )\n"
            "}\n"
        )

        tailwind_snippet = (
            "// tailwind.config.ts\ntheme: {\n"
            "  extend: {\n"
            "    fontFamily: {\n"
            + tailwind_ext
            + "    },\n  },\n}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Configured {len(fonts)} font(s) with next/font",
            artifacts=[
                CodeArtifact(filename="app/layout.tsx", content=layout_code, language="tsx"),
                CodeArtifact(filename="tailwind.fonts.config.ts", content=tailwind_snippet, language="typescript"),
            ],
        )
