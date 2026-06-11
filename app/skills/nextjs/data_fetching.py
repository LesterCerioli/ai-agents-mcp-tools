
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import NEXTJS_EXPERT


@SkillRegistry.register
class GenerateServerFetchSkill(BaseSkill):
    name = "nextjs.generate_server_fetch"
    description = (
        "Generate server-side data fetching with Next.js fetch() cache control, "
        "parallel fetching, Suspense boundaries, and proper TypeScript types."
    )
    category = SkillCategory.NEXTJS
    tags = ["data-fetching", "server-component", "cache", "fetch"]
    parameters = [
        SkillParameter("name", "Function name (e.g. getProducts, getUserProfile, getDashboardData)"),
        SkillParameter("endpoint", "API endpoint or data source description"),
        SkillParameter(
            "strategy", "Caching strategy", required=False, default="revalidate",
            enum=["static", "revalidate", "dynamic", "no-store"],
        ),
        SkillParameter(
            "revalidate_seconds", "Revalidation interval in seconds (for 'revalidate' strategy)",
            required=False, default="3600",
        ),
        SkillParameter("return_type", "TypeScript return type (e.g. Product[], UserProfile, DashboardData)", required=False, default=""),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        endpoint: str,
        strategy: str = "revalidate",
        revalidate_seconds: str = "3600",
        return_type: str = "",
        **_: Any,
    ) -> SkillResult:
        cache_option = {
            "static": "force-cache",
            "revalidate": f"next: {{ revalidate: {revalidate_seconds} }}",
            "dynamic": "no-store",
            "no-store": "no-store",
        }.get(strategy, "no-store")

        prompt = f"""Generate a Next.js server-side data fetching function `{name}`.

Endpoint/source: {endpoint}
Cache strategy: {strategy} ({cache_option})
{"Return type: " + return_type if return_type else ""}

Requirements:
- Async function using fetch() with proper cache config
- TypeScript types for response data
- Error handling: throw descriptive error for non-ok responses
- Support for optional params/filters
- Export as named export
- Add unstable_cache wrapper if appropriate for {strategy} strategy
- Include JSDoc comment with revalidation note

Generate `lib/data/{name}.ts` with the fetch function and types."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="typescript", context=NEXTJS_EXPERT)
        else:
            rt = return_type or "unknown"
            code = (
                f"import {{ unstable_cache }} from 'next/cache'\n\n"
                f"// Revalidates every {revalidate_seconds}s\n"
                f"export const {name} = unstable_cache(\n"
                f"  async (): Promise<{rt}> => {{\n"
                f"    const response = await fetch('{endpoint}', {{\n"
                f"      {'next: { revalidate: ' + revalidate_seconds + ' }' if strategy == 'revalidate' else 'cache: \"' + cache_option + '\"'},\n"
                f"    }})\n\n"
                f"    if (!response.ok) {{\n"
                f"      throw new Error(`Failed to fetch: ${{response.status}} ${{response.statusText}}`)\n"
                f"    }}\n\n"
                f"    return response.json() as Promise<{rt}>\n"
                f"  }},\n"
                f"  ['{name}'],\n"
                f"  {{ revalidate: {revalidate_seconds}, tags: ['{name}'] }}\n"
                f")\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated `{name}` with {strategy} caching",
            artifacts=[CodeArtifact(filename=f"lib/data/{name}.ts", content=code, language="typescript")],
            next_steps=[
                f"Use in Server Component: const data = await {name}()",
                f"Revalidate manually: revalidateTag('{name}')",
            ],
        )


@SkillRegistry.register
class GenerateStreamingPageSkill(BaseSkill):
    name = "nextjs.generate_streaming_page"
    description = (
        "Generate a Next.js streaming page using Suspense boundaries for progressive rendering, "
        "improving TTFB and perceived performance."
    )
    category = SkillCategory.NEXTJS
    tags = ["streaming", "suspense", "performance", "ux"]
    parameters = [
        SkillParameter("route", "Page route (e.g. /dashboard, /products/[id])"),
        SkillParameter(
            "sections",
            "Comma-separated sections to stream independently (e.g. header:fast, stats:slow, chart:slow, feed:medium)",
        ),
        SkillParameter("description", "What the page displays"),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        sections: str,
        description: str,
        **_: Any,
    ) -> SkillResult:
        section_list = [s.strip() for s in sections.split(",") if s.strip()]

        prompt = f"""Generate a Next.js streaming page for `{route}`.

Page description: {description}
Sections to stream: {', '.join(section_list)}

Requirements:
- Main page.tsx is a Server Component
- Wrap each slow section in <Suspense fallback={{<SectionSkeleton />}}>
- Fast sections render immediately, slow sections stream in
- Create async component for each section that fetches its own data
- Create skeleton fallback for each section
- Use Promise.all() for parallel fetches within the same section where safe
- TypeScript throughout

Generate page.tsx with all section components and their skeleton fallbacks."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            suspense_blocks = "\n".join(
                f"      <Suspense fallback={{<div className=\"animate-pulse h-32 rounded-lg bg-muted\" />}}>\n"
                f"        <{s.split(':')[0].title()}Section />\n"
                f"      </Suspense>"
                for s in section_list
            )
            code = (
                "import { Suspense } from 'react'\n\n"
                f"export default async function Page() {{\n"
                f"  return (\n"
                f"    <main className=\"space-y-6 p-8\">\n"
                f"{suspense_blocks}\n"
                f"    </main>\n"
                f"  )\n"
                f"}}\n\n"
                + "\n\n".join(
                    f"async function {s.split(':')[0].title()}Section() {{\n"
                    f"  // const data = await fetch{s.split(':')[0].title()}Data()\n"
                    f"  return <div>{s.split(':')[0].title()} content</div>\n"
                    f"}}"
                    for s in section_list
                )
                + "\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated streaming page with {len(section_list)} Suspense boundaries",
            artifacts=[CodeArtifact(filename=f"app{route}/page.tsx", content=code, language="tsx")],
            next_steps=[
                "Create individual data fetching functions for each section",
                "Add loading.tsx for the initial page shell",
            ],
        )


@SkillRegistry.register
class ImplementISRSkill(BaseSkill):
    name = "nextjs.implement_isr"
    description = (
        "Implement Incremental Static Regeneration (ISR) with generateStaticParams "
        "for dynamic routes, on-demand revalidation, and fallback strategies."
    )
    category = SkillCategory.NEXTJS
    tags = ["isr", "static-generation", "generateStaticParams", "revalidation"]
    parameters = [
        SkillParameter("route", "Dynamic route (e.g. /blog/[slug], /products/[id]/[variant])"),
        SkillParameter("entity", "Entity being rendered (e.g. blog post, product, article)"),
        SkillParameter(
            "revalidate_seconds", "How often to revalidate in seconds",
            required=False, default="3600",
        ),
        SkillParameter(
            "fallback", "Fallback for ungenerated pages", required=False, default="blocking",
            enum=["blocking", "true", "false"],
        ),
        SkillParameter("total_items", "Approximate total items to pre-generate (0 = none)", required=False, default="100"),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        entity: str,
        revalidate_seconds: str = "3600",
        fallback: str = "blocking",
        total_items: str = "100",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Implement ISR for the dynamic route `{route}` showing `{entity}` content.

Revalidation: every {revalidate_seconds} seconds
Fallback: {fallback}
Pre-generate: {total_items} most popular items

Requirements:
- `export const revalidate = {revalidate_seconds}` at page level
- `export async function generateStaticParams()` fetching top {total_items} {entity} slugs/ids
- Async page component with typed params
- Handle not-found case with `notFound()` from next/navigation
- On-demand revalidation API route at `app/api/revalidate/route.ts`

Generate both the page and the revalidation API route."""

        if self.llm:
            page_code = await self.llm.generate_code(
                prompt + "\n\nGenerate the page.tsx first.", language="tsx", context=NEXTJS_EXPERT
            )
            api_code = await self.llm.generate_code(
                prompt + "\n\nNow generate only the revalidation API route handler.", language="typescript", context=NEXTJS_EXPERT
            )
        else:
            param = route.split("[")[1].split("]")[0] if "[" in route else "id"
            page_code = (
                f"import {{ notFound }} from 'next/navigation'\n\n"
                f"export const revalidate = {revalidate_seconds}\n\n"
                f"export async function generateStaticParams() {{\n"
                f"  // const items = await getAllActive{entity.title()}s({{ limit: {total_items} }})\n"
                f"  // return items.map(item => ({{ {param}: item.{param} }}))\n"
                f"  return []\n"
                f"}}\n\n"
                f"interface PageProps {{\n"
                f"  params: Promise<{{ {param}: string }}>\n"
                f"}}\n\n"
                f"export default async function Page({{ params }}: PageProps) {{\n"
                f"  const {{ {param} }} = await params\n"
                f"  // const {entity} = await get{entity.title()}By{param.title()}({param})\n"
                f"  // if (!{entity}) notFound()\n"
                f"  return <main>{{{param}}}</main>\n"
                f"}}\n"
            )
            api_code = (
                "import { revalidatePath, revalidateTag } from 'next/cache'\n"
                "import { NextRequest, NextResponse } from 'next/server'\n\n"
                "export async function POST(request: NextRequest) {\n"
                "  const secret = request.nextUrl.searchParams.get('secret')\n"
                "  if (secret !== process.env.REVALIDATION_SECRET) {\n"
                "    return NextResponse.json({ error: 'Invalid secret' }, { status: 401 })\n"
                "  }\n"
                "  const { path, tag } = await request.json() as { path?: string; tag?: string }\n"
                "  if (path) revalidatePath(path)\n"
                "  if (tag) revalidateTag(tag)\n"
                "  return NextResponse.json({ revalidated: true, timestamp: Date.now() })\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Implemented ISR for `{route}` with {revalidate_seconds}s revalidation",
            artifacts=[
                CodeArtifact(filename=f"app{route}/page.tsx", content=page_code, language="tsx"),
                CodeArtifact(filename="app/api/revalidate/route.ts", content=api_code, language="typescript"),
            ],
            instructions=[
                "Add REVALIDATION_SECRET to your .env file",
                f"Trigger revalidation: POST /api/revalidate?secret=xxx with body {{ path: '{route}' }}",
            ],
        )
