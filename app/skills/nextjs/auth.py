
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import NEXTJS_EXPERT


@SkillRegistry.register
class SetupNextAuthSkill(BaseSkill):
    name = "nextjs.setup_nextauth"
    description = (
        "Set up NextAuth.js v5 (Auth.js) with OAuth providers, credentials, "
        "database adapter, session management, and TypeScript types."
    )
    category = SkillCategory.NEXTJS
    tags = ["auth", "nextauth", "oauth", "session", "jwt"]
    parameters = [
        SkillParameter(
            "providers",
            "Comma-separated OAuth providers: google, github, discord, twitter, credentials",
            required=False, default="google,github",
        ),
        SkillParameter(
            "adapter", "Database adapter", required=False, default="prisma",
            enum=["prisma", "drizzle", "supabase", "mongodb", "none"],
        ),
        SkillParameter(
            "session_strategy", "Session strategy", required=False, default="database",
            enum=["database", "jwt"],
        ),
        SkillParameter(
            "features",
            "Comma-separated features: rbac, email-verification, 2fa, callbacks",
            required=False, default="callbacks",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        providers: str = "google,github",
        adapter: str = "prisma",
        session_strategy: str = "database",
        features: str = "callbacks",
        **_: Any,
    ) -> SkillResult:
        provider_list = [p.strip() for p in providers.split(",") if p.strip()]
        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        prompt = f"""Set up NextAuth.js v5 (Auth.js) for a Next.js 15 app.

Providers: {', '.join(provider_list)}
Database adapter: {adapter}
Session strategy: {session_strategy}
Additional features: {', '.join(feature_list)}

Generate these files:
1. `auth.ts` — main Auth.js config with providers, adapter, callbacks
2. `auth.config.ts` — edge-compatible config (no DB) for middleware
3. `app/api/auth/[...nextauth]/route.ts` — route handler
4. `types/next-auth.d.ts` — TypeScript module augmentation

Requirements:
- TypeScript throughout
- Session callback to include user.id and user.role
- JWT callback for custom claims
- {"RBAC: include role in session and JWT" if "rbac" in feature_list else ""}
- Credentials provider with bcrypt password verification if credentials included
- Proper error handling and authorized callbacks"""

        if self.llm:
            auth_ts = await self.llm.generate_code(
                prompt + "\n\nGenerate auth.ts:", language="typescript", context=NEXTJS_EXPERT
            )
            route_ts = await self.llm.generate_code(
                prompt + "\n\nGenerate only app/api/auth/[...nextauth]/route.ts:",
                language="typescript", context=NEXTJS_EXPERT,
            )
        else:
            providers_import = "\n".join(
                f"import {p.title()}Provider from 'next-auth/providers/{p}'"
                for p in provider_list if p != "credentials"
            )
            auth_ts = (
                f"import NextAuth from 'next-auth'\n"
                f"import {{ PrismaAdapter }} from '@auth/prisma-adapter'\n"
                f"import {{ prisma }} from '@/lib/prisma'\n"
                f"{providers_import}\n\n"
                f"export const {{ handlers, auth, signIn, signOut }} = NextAuth({{\n"
                f"  adapter: PrismaAdapter(prisma),\n"
                f"  session: {{ strategy: '{session_strategy}' }},\n"
                f"  providers: [\n"
                + "".join(
                    f"    {p.title()}Provider({{ clientId: process.env.{p.upper()}_CLIENT_ID!, clientSecret: process.env.{p.upper()}_CLIENT_SECRET! }}),\n"
                    for p in provider_list if p != "credentials"
                )
                + f"  ],\n"
                f"  callbacks: {{\n"
                f"    session: async ({{ session, user }}) => ({{\n"
                f"      ...session,\n"
                f"      user: {{ ...session.user, id: user.id }},\n"
                f"    }}),\n"
                f"  }},\n"
                f"}})\n"
            )
            route_ts = (
                "import { handlers } from '@/auth'\n"
                "export const { GET, POST } = handlers\n"
            )

        deps = ["next-auth@beta"]
        if adapter == "prisma":
            deps.append("@auth/prisma-adapter")

        return SkillResult(
            success=True,
            summary=f"Generated NextAuth.js v5 setup with {', '.join(provider_list)}",
            artifacts=[
                CodeArtifact(filename="auth.ts", content=auth_ts, language="typescript"),
                CodeArtifact(filename="app/api/auth/[...nextauth]/route.ts", content=route_ts, language="typescript"),
            ],
            dependencies=deps,
            instructions=[
                "Add AUTH_SECRET to .env: npx auth secret",
                f"Add provider credentials to .env ({', '.join(p.upper() + '_CLIENT_ID/_SECRET' for p in provider_list if p != 'credentials')})",
                "Run database migration for auth tables",
            ],
        )


@SkillRegistry.register
class GenerateProtectedRouteSkill(BaseSkill):
    name = "nextjs.generate_protected_route"
    description = (
        "Generate a protected page/layout that validates session, "
        "redirects unauthenticated users, and supports role-based access control."
    )
    category = SkillCategory.NEXTJS
    tags = ["auth", "protected", "rbac", "session"]
    parameters = [
        SkillParameter("route", "Route to protect (e.g. /dashboard, /admin)"),
        SkillParameter("component_type", "Component type", required=False, default="page", enum=["page", "layout"]),
        SkillParameter("required_role", "Required user role (leave empty for any authenticated user)", required=False, default=""),
        SkillParameter("redirect_to", "Redirect destination if not authorized", required=False, default="/login"),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        component_type: str = "page",
        required_role: str = "",
        redirect_to: str = "/login",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate a protected Next.js {component_type} for `{route}`.

Auth: NextAuth.js v5 (auth() from '@/auth')
{"Required role: " + required_role if required_role else "Any authenticated user"}
Redirect if unauthorized: {redirect_to}

Requirements:
- Server Component that calls auth() at the top
- Redirect to {redirect_to}?callbackUrl={route} if no session
- {"Check session.user.role === '" + required_role + "', redirect to /unauthorized if wrong role" if required_role else ""}
- Pass user data to child components as props
- TypeScript with Session type

Generate the complete {component_type}.tsx."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                "import { auth } from '@/auth'\n"
                "import { redirect } from 'next/navigation'\n\n"
                f"export default async function {'Page' if component_type == 'page' else 'Layout'}({{ {'children' if component_type == 'layout' else ''} }}{': { children: React.ReactNode }' if component_type == 'layout' else ''}) {{\n"
                "  const session = await auth()\n"
                "  if (!session?.user) {\n"
                f"    redirect('{redirect_to}?callbackUrl={route}')\n"
                "  }\n"
                + (f"  if (session.user.role !== '{required_role}') {{\n    redirect('/unauthorized')\n  }}\n" if required_role else "")
                + "\n"
                "  return (\n"
                "    <main>\n"
                "      {/* Protected content — session.user is guaranteed here */}\n"
                + ("      {children}\n" if component_type == "layout" else "")
                + "    </main>\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated protected {component_type} for `{route}`",
            artifacts=[CodeArtifact(
                filename=f"app{route}/{component_type}.tsx", content=code, language="tsx",
            )],
        )
