
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import VERCEL_EXPERT


@SkillRegistry.register
class GenerateVercelConfigSkill(BaseSkill):
    name = "vercel.generate_config"
    description = "Generate vercel.ts configuration with rewrites, redirects, headers, crons, and caching."
    category = SkillCategory.VERCEL
    tags = ["vercel", "deployment", "config", "caching", "rewrites"]
    parameters = [
        SkillParameter("framework", "Framework being deployed", required=False, default="nextjs", enum=["nextjs", "astro", "sveltekit", "nuxt", "remix"]),
        SkillParameter(
            "features",
            "Comma-separated features: rewrites, redirects, security-headers, crons, regions",
            required=False, default="security-headers",
        ),
        SkillParameter("regions", "Deployment regions (comma-separated)", required=False, default="iad1"),
    ]

    async def execute(  # type: ignore[override]
        self,
        framework: str = "nextjs",
        features: str = "security-headers",
        regions: str = "iad1",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
        region_list = [r.strip() for r in regions.split(",") if r.strip()]

        config = (
            "import type { VercelConfig } from '@vercel/config'\n\n"
            "export const config: VercelConfig = {\n"
            f"  framework: '{framework}',\n"
            f"  regions: [{', '.join(repr(r) for r in region_list)}],\n"
        )

        if "rewrites" in feature_list:
            config += (
                "  rewrites: [\n"
                "    // { source: '/api/:path*', destination: 'https://api.example.com/:path*' },\n"
                "  ],\n"
            )

        if "redirects" in feature_list:
            config += (
                "  redirects: [\n"
                "    // { source: '/old-path', destination: '/new-path', permanent: true },\n"
                "  ],\n"
            )

        if "security-headers" in feature_list:
            config += (
                "  headers: [\n"
                "    {\n"
                "      source: '/(.*)',\n"
                "      headers: [\n"
                "        { key: 'X-DNS-Prefetch-Control', value: 'on' },\n"
                "        { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },\n"
                "        { key: 'X-Frame-Options', value: 'SAMEORIGIN' },\n"
                "        { key: 'X-Content-Type-Options', value: 'nosniff' },\n"
                "        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },\n"
                "        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },\n"
                "      ],\n"
                "    },\n"
                "    {\n"
                "      source: '/api/(.*)',\n"
                "      headers: [\n"
                "        { key: 'Cache-Control', value: 'no-store' },\n"
                "        { key: 'Access-Control-Allow-Origin', value: '*' },\n"
                "      ],\n"
                "    },\n"
                "  ],\n"
            )

        if "crons" in feature_list:
            config += (
                "  crons: [\n"
                "    { path: '/api/cron/daily-cleanup', schedule: '0 0 * * *' },\n"
                "    { path: '/api/cron/hourly-sync', schedule: '0 * * * *' },\n"
                "  ],\n"
            )

        config += "}\n"

        return SkillResult(
            success=True,
            summary=f"Generated Vercel config for {framework} with: {', '.join(feature_list)}",
            artifacts=[CodeArtifact(filename="vercel.ts", content=config, language="typescript")],
            dev_dependencies=["@vercel/config"],
        )


@SkillRegistry.register
class GenerateDeploymentChecklistSkill(BaseSkill):
    name = "vercel.deployment_checklist"
    description = "Generate a comprehensive pre-deployment checklist for Next.js apps on Vercel."
    category = SkillCategory.VERCEL
    tags = ["deployment", "checklist", "production", "quality"]
    parameters = [
        SkillParameter("app_type", "Application type (e.g. SaaS, e-commerce, blog, marketing)", required=False, default="SaaS"),
        SkillParameter("has_database", "Does the app use a database?", required=False, default="true", enum=["true", "false"]),
        SkillParameter("has_auth", "Does the app use authentication?", required=False, default="true", enum=["true", "false"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_type: str = "SaaS",
        has_database: str = "true",
        has_auth: str = "true",
        **_: Any,
    ) -> SkillResult:
        checklist = (
            f"# Production Deployment Checklist — {app_type}\n\n"
            "## Build & Code Quality\n"
            "- [ ] `npm run build` passes without errors or warnings\n"
            "- [ ] TypeScript: `tsc --noEmit` passes\n"
            "- [ ] Linting: `eslint` passes\n"
            "- [ ] All tests pass: `npm test`\n"
            "- [ ] Bundle size reviewed: `npm run analyze`\n\n"
            "## Environment Variables\n"
            "- [ ] All required env vars set in Vercel dashboard\n"
            "- [ ] `NEXT_PUBLIC_*` vars reviewed (public by default)\n"
            "- [ ] No secrets committed to git\n"
            "- [ ] `.env.example` updated with new vars\n\n"
        )

        if has_database == "true":
            checklist += (
                "## Database\n"
                "- [ ] Production database URL configured\n"
                "- [ ] All migrations run on production database\n"
                "- [ ] Connection pooling configured (PgBouncer/Prisma Accelerate)\n"
                "- [ ] Database backups enabled\n"
                "- [ ] Seed data/initial data applied\n\n"
            )

        if has_auth == "true":
            checklist += (
                "## Authentication\n"
                "- [ ] AUTH_SECRET set (different from development)\n"
                "- [ ] OAuth app URLs updated to production domain\n"
                "- [ ] Email verification working\n"
                "- [ ] Session/JWT expiry configured correctly\n\n"
            )

        checklist += (
            "## Performance\n"
            "- [ ] Images using next/image\n"
            "- [ ] Fonts loaded via next/font\n"
            "- [ ] Core Web Vitals: LCP < 2.5s, CLS < 0.1, INP < 200ms\n"
            "- [ ] Lighthouse score ≥ 90\n"
            "- [ ] Critical routes have ISR/static generation where possible\n\n"
            "## Security\n"
            "- [ ] Security headers configured in vercel.ts\n"
            "- [ ] CORS configured for API routes\n"
            "- [ ] Rate limiting on auth and mutation endpoints\n"
            "- [ ] Input validation on all form inputs\n"
            "- [ ] SQL injection prevention (parameterized queries/ORM)\n\n"
            "## SEO & Metadata\n"
            "- [ ] All pages have unique title and description\n"
            "- [ ] Open Graph images configured\n"
            "- [ ] sitemap.xml accessible at /sitemap.xml\n"
            "- [ ] robots.txt configured\n"
            "- [ ] Canonical URLs set\n\n"
            "## Monitoring\n"
            "- [ ] Error monitoring set up (Sentry)\n"
            "- [ ] Vercel Analytics enabled\n"
            "- [ ] Uptime monitoring configured\n"
            "- [ ] Alerts configured for error spikes\n\n"
            "## Final\n"
            "- [ ] Preview deployment tested\n"
            "- [ ] Staging environment validated\n"
            "- [ ] Rollback plan ready (previous deployment tagged)\n"
            "- [ ] Team notified of deployment\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated deployment checklist for {app_type}",
            artifacts=[CodeArtifact(filename="DEPLOYMENT_CHECKLIST.md", content=checklist, language="markdown")],
        )
