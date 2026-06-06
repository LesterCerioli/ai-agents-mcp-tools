
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import NEXTJS_EXPERT


@SkillRegistry.register
class GenerateMetadataSkill(BaseSkill):
    name = "nextjs.generate_metadata"
    description = (
        "Generate Next.js generateMetadata() function and static metadata exports "
        "with Open Graph, Twitter cards, canonical URLs, and dynamic page data."
    )
    category = SkillCategory.NEXTJS
    tags = ["seo", "metadata", "opengraph", "twitter-card", "og"]
    parameters = [
        SkillParameter("page_name", "Page name (e.g. Product Detail, Blog Post, Home, About)"),
        SkillParameter("description", "What this page shows — used for meta description"),
        SkillParameter(
            "type", "Metadata type", required=False, default="dynamic",
            enum=["static", "dynamic"],
        ),
        SkillParameter("site_name", "Website/brand name", required=False, default="My App"),
        SkillParameter("og_image_route", "OG image route (e.g. /og, /api/og)", required=False, default="/og"),
    ]

    async def execute(  # type: ignore[override]
        self,
        page_name: str,
        description: str,
        type: str = "dynamic",
        site_name: str = "My App",
        og_image_route: str = "/og",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate Next.js {type} metadata for the `{page_name}` page.

Description: {description}
Site name: {site_name}
OG image route: {og_image_route}

Requirements:
- {"generateMetadata({ params, searchParams }) async function" if type == "dynamic" else "export const metadata: Metadata object"}
- title.default and title.template pattern
- description from page content
- openGraph: type, title, description, url, siteName, images (with og image URL)
- twitter: card='summary_large_image', title, description, images
- alternates.canonical with absolute URL
- robots: index, follow
- {"Extract entity data from params to build dynamic metadata" if type == "dynamic" else ""}
- Use metadataBase with process.env.NEXT_PUBLIC_BASE_URL

Generate only the metadata export — no full page component needed."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="typescript", context=NEXTJS_EXPERT)
        else:
            if type == "static":
                code = (
                    "import type { Metadata } from 'next'\n\n"
                    f"export const metadata: Metadata = {{\n"
                    f"  metadataBase: new URL(process.env.NEXT_PUBLIC_BASE_URL ?? 'http://localhost:3000'),\n"
                    f"  title: {{\n"
                    f"    default: '{page_name} | {site_name}',\n"
                    f"    template: '%s | {site_name}',\n"
                    f"  }},\n"
                    f"  description: '{description}',\n"
                    f"  openGraph: {{\n"
                    f"    type: 'website',\n"
                    f"    title: '{page_name} | {site_name}',\n"
                    f"    description: '{description}',\n"
                    f"    siteName: '{site_name}',\n"
                    f"    images: [{{ url: '{og_image_route}', width: 1200, height: 630 }}],\n"
                    f"  }},\n"
                    f"  twitter: {{\n"
                    f"    card: 'summary_large_image',\n"
                    f"    title: '{page_name} | {site_name}',\n"
                    f"    description: '{description}',\n"
                    f"    images: ['{og_image_route}'],\n"
                    f"  }},\n"
                    f"}}\n"
                )
            else:
                code = (
                    "import type { Metadata } from 'next'\n\n"
                    "interface Props {\n"
                    "  params: Promise<{ slug: string }>\n"
                    "}\n\n"
                    "export async function generateMetadata({ params }: Props): Promise<Metadata> {\n"
                    "  const { slug } = await params\n"
                    "  // const entity = await getEntityBySlug(slug)\n"
                    "  const title = slug // Replace with entity.title\n"
                    f"  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL ?? 'http://localhost:3000'\n\n"
                    "  return {\n"
                    f"    metadataBase: new URL(baseUrl),\n"
                    f"    title: `${{title}} | {site_name}`,\n"
                    f"    description: '{description}',\n"
                    "    openGraph: {\n"
                    "      type: 'article',\n"
                    f"      title: `${{title}} | {site_name}`,\n"
                    f"      siteName: '{site_name}',\n"
                    f"      images: [`${{baseUrl}}{og_image_route}?slug=${{slug}}`],\n"
                    "    },\n"
                    "    twitter: {\n"
                    "      card: 'summary_large_image',\n"
                    f"      images: [`${{baseUrl}}{og_image_route}?slug=${{slug}}`],\n"
                    "    },\n"
                    "    alternates: {\n"
                    "      canonical: `${baseUrl}/${slug}`,\n"
                    "    },\n"
                    "  }\n"
                    "}\n"
                )

        return SkillResult(
            success=True,
            summary=f"Generated {type} metadata for {page_name}",
            artifacts=[CodeArtifact(filename="metadata.ts", content=code, language="typescript")],
            next_steps=[
                "Set NEXT_PUBLIC_BASE_URL in .env",
                "Create the OG image route at " + og_image_route,
                "Validate with https://developers.facebook.com/tools/debug/",
            ],
        )


@SkillRegistry.register
class GenerateOGImageSkill(BaseSkill):
    name = "nextjs.generate_og_image"
    description = (
        "Generate a Next.js opengraph-image.tsx or dynamic OG image route "
        "using @vercel/og with customizable layout and branding."
    )
    category = SkillCategory.NEXTJS
    tags = ["og-image", "social", "seo", "vercel-og", "opengraph"]
    parameters = [
        SkillParameter("route", "Where to place the OG image (e.g. /og, /blog/[slug])"),
        SkillParameter("layout_description", "Description of the OG image design (e.g. gradient background with title and logo)"),
        SkillParameter(
            "type", "OG image type", required=False, default="api-route",
            enum=["api-route", "file-convention"],
        ),
        SkillParameter("brand_color", "Primary brand color (hex, e.g. #7c3aed)", required=False, default="#000000"),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        layout_description: str,
        type: str = "api-route",
        brand_color: str = "#000000",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate a Next.js OG image for the route `{route}`.

Design: {layout_description}
Brand color: {brand_color}
Type: {type}

Requirements:
- Use ImageResponse from 'next/og'
- Width: 1200, Height: 630 (standard OG size)
- Accept query params: title, description, image (via searchParams or props)
- CSS-in-JS styles (tw prop or style objects)
- Fallback values for missing params
- {"Export as GET route handler" if type == "api-route" else "Export as opengraph-image.tsx convention"}
- Font loading with fetch() from Google Fonts
- Visually professional: gradient, proper typography hierarchy

Generate the complete OG image file."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                "import { ImageResponse } from 'next/og'\n"
                "import type { NextRequest } from 'next/server'\n\n"
                "export const runtime = 'edge'\n"
                "export const contentType = 'image/png'\n"
                "export const size = { width: 1200, height: 630 }\n\n"
                "export async function GET(request: NextRequest) {\n"
                "  const { searchParams } = new URL(request.url)\n"
                "  const title = searchParams.get('title') ?? 'Default Title'\n"
                "  const description = searchParams.get('description') ?? ''\n\n"
                "  return new ImageResponse(\n"
                "    (\n"
                "      <div\n"
                "        style={{\n"
                "          width: '100%',\n"
                "          height: '100%',\n"
                f"          background: 'linear-gradient(135deg, {brand_color} 0%, #1a1a2e 100%)',\n"
                "          display: 'flex',\n"
                "          flexDirection: 'column',\n"
                "          alignItems: 'flex-start',\n"
                "          justifyContent: 'flex-end',\n"
                "          padding: '60px',\n"
                "        }}\n"
                "      >\n"
                "        <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 24, margin: 0 }}>\n"
                "          {description}\n"
                "        </p>\n"
                "        <h1 style={{ color: 'white', fontSize: 64, fontWeight: 700, margin: '16px 0 0' }}>\n"
                "          {title}\n"
                "        </h1>\n"
                "      </div>\n"
                "    ),\n"
                "    { width: 1200, height: 630 }\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated OG image handler at {route}",
            artifacts=[CodeArtifact(
                filename=f"app{route}/route.ts" if type == "api-route" else f"app{route}/opengraph-image.tsx",
                content=code, language="tsx",
            )],
            next_steps=[
                "Test: GET /og?title=Hello&description=World",
                "Reference in metadata: images: [`${baseUrl}/og?title=${encodeURIComponent(title)}`]",
            ],
        )


@SkillRegistry.register
class GenerateSitemapSkill(BaseSkill):
    name = "nextjs.generate_sitemap"
    description = (
        "Generate sitemap.ts for static and dynamic routes, "
        "with proper changefreq, priority, and lastModified dates."
    )
    category = SkillCategory.NEXTJS
    tags = ["seo", "sitemap", "xml", "static-generation"]
    parameters = [
        SkillParameter("static_routes", "Comma-separated static routes (e.g. /,/about,/pricing,/blog)", required=False, default="/,/about"),
        SkillParameter("dynamic_entities", "Comma-separated dynamic entities to include (e.g. blog-posts,products,docs-pages)", required=False, default=""),
        SkillParameter("base_url_env", "Environment variable for base URL", required=False, default="NEXT_PUBLIC_BASE_URL"),
    ]

    async def execute(  # type: ignore[override]
        self,
        static_routes: str = "/,/about",
        dynamic_entities: str = "",
        base_url_env: str = "NEXT_PUBLIC_BASE_URL",
        **_: Any,
    ) -> SkillResult:
        route_list = [r.strip() for r in static_routes.split(",") if r.strip()]
        entity_list = [e.strip() for e in dynamic_entities.split(",") if e.strip()]

        code = (
            "import type { MetadataRoute } from 'next'\n\n"
            f"const BASE_URL = process.env.{base_url_env} ?? 'http://localhost:3000'\n\n"
            "export default async function sitemap(): Promise<MetadataRoute.Sitemap> {\n"
            "  const staticRoutes: MetadataRoute.Sitemap = [\n"
        )

        for route in route_list:
            priority = "1" if route == "/" else "0.8"
            freq = "daily" if route == "/" else "weekly"
            code += (
                f"    {{\n"
                f"      url: `${{BASE_URL}}{route}`,\n"
                f"      lastModified: new Date(),\n"
                f"      changeFrequency: '{freq}',\n"
                f"      priority: {priority},\n"
                f"    }},\n"
            )

        code += "  ]\n\n"

        if entity_list:
            for entity in entity_list:
                code += (
                    f"  // const {entity.replace('-', '_')} = await getAll{entity.replace('-', '_').title().replace('_', '')}()\n"
                    f"  // const {entity.replace('-', '_')}Routes = {entity.replace('-', '_')}.map(item => ({{\n"
                    f"  //   url: `${{BASE_URL}}/{entity.replace('-', '/')}/${{item.slug}}`,\n"
                    f"  //   lastModified: item.updatedAt,\n"
                    f"  //   changeFrequency: 'weekly' as const,\n"
                    f"  //   priority: 0.7,\n"
                    f"  // }}))\n\n"
                )

        code += "  return [\n    ...staticRoutes,\n"
        for entity in entity_list:
            code += f"    // ...{entity.replace('-', '_')}Routes,\n"
        code += "  ]\n}\n"

        return SkillResult(
            success=True,
            summary=f"Generated sitemap with {len(route_list)} static routes",
            artifacts=[CodeArtifact(filename="app/sitemap.ts", content=code, language="typescript")],
            next_steps=[
                "Uncomment and implement dynamic entity fetching",
                "Submit sitemap to Google Search Console",
                "Verify at: /sitemap.xml",
            ],
        )
