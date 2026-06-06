
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import NEXTJS_EXPERT


@SkillRegistry.register
class OptimizeImagesSkill(BaseSkill):
    name = "nextjs.optimize_images"
    description = (
        "Generate optimized image components using next/image with proper sizing, "
        "priority loading, blur placeholder, and responsive srcset patterns."
    )
    category = SkillCategory.NEXTJS
    tags = ["performance", "images", "next/image", "core-web-vitals", "lcp"]
    parameters = [
        SkillParameter("use_case", "Image use case (e.g. hero banner, product card, avatar, gallery, blog thumbnail)"),
        SkillParameter(
            "source", "Image source type", required=False, default="remote",
            enum=["local", "remote", "cms", "cloudinary", "s3"],
        ),
        SkillParameter("remote_domains", "Comma-separated remote domains (for remote sources)", required=False, default=""),
    ]

    async def execute(  # type: ignore[override]
        self,
        use_case: str,
        source: str = "remote",
        remote_domains: str = "",
        **_: Any,
    ) -> SkillResult:
        domains = [d.strip() for d in remote_domains.split(",") if d.strip()]

        prompt = f"""Generate an optimized Next.js image component for: {use_case}

Image source: {source}
{"Remote domains: " + ', '.join(domains) if domains else ""}

Requirements:
- Use next/image Image component (never <img>)
- Correct `sizes` attribute matching the layout breakpoints
- `priority` prop for above-the-fold images (LCP candidate)
- `placeholder="blur"` with blurDataURL for local images
- `fill` layout for containers of unknown size
- next.config.ts remotePatterns configuration
- TypeScript interface for component props
- Responsive sizes string matching Tailwind breakpoints

Generate the image component AND the next.config.ts remotePatterns if needed."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                "import Image from 'next/image'\n\n"
                "interface OptimizedImageProps {\n"
                "  src: string\n"
                "  alt: string\n"
                "  priority?: boolean\n"
                "  className?: string\n"
                "}\n\n"
                "export function OptimizedImage({ src, alt, priority = false, className }: OptimizedImageProps) {\n"
                "  return (\n"
                "    <div className={`relative overflow-hidden ${className}`}>\n"
                "      <Image\n"
                "        src={src}\n"
                "        alt={alt}\n"
                "        fill\n"
                "        priority={priority}\n"
                "        sizes=\"(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw\"\n"
                "        className=\"object-cover\"\n"
                "      />\n"
                "    </div>\n"
                "  )\n"
                "}\n"
            )

        config_code = ""
        if domains:
            config_code = (
                "import type { NextConfig } from 'next'\n\n"
                "const config: NextConfig = {\n"
                "  images: {\n"
                "    remotePatterns: [\n"
                + "".join(
                    f"      {{ protocol: 'https', hostname: '{d}' }},\n"
                    for d in domains
                )
                + "    ],\n"
                "  },\n"
                "}\n\n"
                "export default config\n"
            )

        artifacts = [CodeArtifact(filename="components/OptimizedImage.tsx", content=code, language="tsx")]
        if config_code:
            artifacts.append(CodeArtifact(filename="next.config.ts", content=config_code, language="typescript"))

        return SkillResult(
            success=True,
            summary=f"Generated optimized image component for {use_case}",
            artifacts=artifacts,
            next_steps=[
                "Use priority={true} for hero/LCP images",
                "Always provide meaningful alt text",
                "Run Lighthouse to verify LCP improvement",
            ],
        )


@SkillRegistry.register
class ImplementFontOptimizationSkill(BaseSkill):
    name = "nextjs.optimize_fonts"
    description = (
        "Set up zero-layout-shift font loading with next/font/google, "
        "CSS variable integration, fallback fonts, and Tailwind configuration."
    )
    category = SkillCategory.NEXTJS
    tags = ["performance", "fonts", "cls", "next/font", "tailwind"]
    parameters = [
        SkillParameter(
            "fonts",
            "Comma-separated fonts with weights (e.g. Inter:400,500,600,700, Playfair_Display:700,900)",
        ),
        SkillParameter(
            "usage", "How fonts are used", required=False, default="body-and-heading",
            enum=["body-and-heading", "body-only", "heading-only", "monospace", "display"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        fonts: str,
        usage: str = "body-and-heading",
        **_: Any,
    ) -> SkillResult:
        font_list = [f.strip() for f in fonts.split(",") if f.strip()]

        prompt = f"""Implement optimized font loading with next/font/google.

Fonts needed: {', '.join(font_list)}
Usage: {usage}

Generate:
1. Font configuration in `app/layout.tsx` (font imports + CSS variables on body)
2. Tailwind `tailwind.config.ts` extending fontFamily with the CSS variables
3. Usage example in a component

Requirements:
- Import from 'next/font/google'
- Use `variable` option for CSS custom properties: `--font-sans`, `--font-heading`
- `subsets: ['latin']`, `display: 'swap'`
- Apply className to body element in root layout
- Tailwind config extends theme.fontFamily to reference CSS vars
- Zero layout shift (preloaded automatically by next/font)"""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="typescript", context=NEXTJS_EXPERT)
        else:
            # Parse first font name
            font_name = font_list[0].split(":")[0].strip().replace(" ", "_") if font_list else "Inter"
            code = (
                f"import {{ {font_name} }} from 'next/font/google'\n\n"
                f"const font = {font_name}({{\n"
                "  subsets: ['latin'],\n"
                "  display: 'swap',\n"
                "  variable: '--font-sans',\n"
                "})\n\n"
                "export default function RootLayout({ children }: { children: React.ReactNode }) {\n"
                "  return (\n"
                "    <html lang=\"en\" className={font.variable}>\n"
                "      <body className=\"font-sans antialiased\">{children}</body>\n"
                "    </html>\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Configured optimized font loading for: {', '.join(font_list)}",
            artifacts=[CodeArtifact(filename="app/layout.tsx", content=code, language="tsx")],
            next_steps=[
                "Add fontFamily to tailwind.config.ts theme extension",
                "Remove any @import Google Fonts in CSS (redundant)",
            ],
        )


@SkillRegistry.register
class ImplementCodeSplittingSkill(BaseSkill):
    name = "nextjs.implement_code_splitting"
    description = (
        "Implement dynamic imports and code splitting to reduce initial bundle size, "
        "with loading states and SSR options."
    )
    category = SkillCategory.NEXTJS
    tags = ["performance", "bundle", "dynamic-import", "code-splitting"]
    parameters = [
        SkillParameter("components", "Comma-separated component names to lazy load (e.g. RichEditor, ChartDashboard, MapView)"),
        SkillParameter(
            "strategy", "Loading strategy", required=False, default="on-interaction",
            enum=["on-interaction", "on-viewport", "immediately", "on-route"],
        ),
        SkillParameter("ssr", "Enable server-side rendering for dynamic imports", required=False, default="false", enum=["true", "false"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        components: str,
        strategy: str = "on-interaction",
        ssr: str = "false",
        **_: Any,
    ) -> SkillResult:
        comp_list = [c.strip() for c in components.split(",") if c.strip()]

        code = "import dynamic from 'next/dynamic'\n"
        code += "import { useState } from 'react'\n\n"

        for comp in comp_list:
            code += (
                f"const {comp} = dynamic(() => import('@/components/{comp}'), {{\n"
                f"  loading: () => <div className=\"animate-pulse h-32 rounded-lg bg-muted\" />,\n"
                f"  ssr: {ssr},\n"
                f"}})\n\n"
            )

        code += "// Usage example:\nexport function ExamplePage() {\n"
        if strategy == "on-interaction":
            code += "  const [show, setShow] = useState(false)\n\n"
            code += "  return (\n    <div>\n"
            code += "      <button onClick={() => setShow(true)}>Load component</button>\n"
            for comp in comp_list:
                code += f"      {{show && <{comp} />}}\n"
            code += "    </div>\n  )\n}\n"
        else:
            code += "  return (\n    <div>\n"
            for comp in comp_list:
                code += f"      <{comp} />\n"
            code += "    </div>\n  )\n}\n"

        return SkillResult(
            success=True,
            summary=f"Implemented dynamic imports for: {', '.join(comp_list)}",
            artifacts=[CodeArtifact(filename="components/dynamic-imports.tsx", content=code, language="tsx")],
            next_steps=[
                "Run `next build && next analyze` to verify bundle reduction",
                "Check Network tab — components should load as separate chunks",
            ],
        )
