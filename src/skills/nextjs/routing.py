
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import NEXTJS_EXPERT


@SkillRegistry.register
class GenerateRouteStructureSkill(BaseSkill):
    name = "nextjs.generate_route_structure"
    description = (
        "Design and generate the optimal Next.js App Router file structure "
        "for a given application type, with route groups and organization patterns."
    )
    category = SkillCategory.NEXTJS
    tags = ["routing", "architecture", "app-router", "file-structure"]
    parameters = [
        SkillParameter("app_type", "Type of application (e.g. SaaS dashboard, e-commerce, blog, marketing site)"),
        SkillParameter("features", "Comma-separated main features (e.g. auth, dashboard, billing, blog, admin)"),
        SkillParameter(
            "auth_strategy", "Authentication approach", required=False, default="nextauth",
            enum=["nextauth", "clerk", "supabase", "none"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_type: str,
        features: str,
        auth_strategy: str = "nextauth",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        prompt = f"""Design the Next.js 15 App Router file structure for a {app_type}.

Features needed: {', '.join(feature_list)}
Auth: {auth_strategy}

Create the optimal structure using:
- Route groups (parentheses) to share layouts without affecting URLs: (marketing), (app), (auth)
- Protected routes for authenticated sections
- Dynamic routes where needed
- Parallel routes for complex UIs if applicable
- Intercepting routes for modals if applicable

Return a directory tree showing:
- app/ directory structure
- Key files: layout.tsx, page.tsx, loading.tsx, error.tsx
- middleware.ts placement
- lib/, actions/, components/ organization

Format as a tree with brief annotations."""

        if self.llm:
            structure = await self.llm.chat(prompt, system_prompt=NEXTJS_EXPERT)
        else:
            structure = """app/
├── (marketing)/           # Public marketing pages
│   ├── layout.tsx         # Marketing layout (navbar + footer)
│   ├── page.tsx           # Landing page
│   ├── about/page.tsx
│   └── pricing/page.tsx
├── (auth)/                # Auth pages (no marketing layout)
│   ├── login/page.tsx
│   ├── register/page.tsx
│   └── layout.tsx
├── (app)/                 # Protected app (requires session)
│   ├── layout.tsx         # App shell (sidebar + topbar)
│   ├── dashboard/page.tsx
│   └── settings/
│       ├── page.tsx
│       └── billing/page.tsx
├── api/
│   └── [...route]/route.js    # JavaScript! Only .js exception in the project
├── layout.tsx             # Root layout (providers, fonts)
└── not-found.tsx

middleware.ts              # Auth guard, redirects"""

        return SkillResult(
            success=True,
            summary=f"Designed route structure for {app_type}",
            artifacts=[CodeArtifact(
                filename="ROUTE_STRUCTURE.md",
                content=f"# Route Structure\n\n```\n{structure}\n```\n",
                language="markdown",
            )],
            next_steps=[
                "Run: mkdir -p app/(marketing) app/(auth) app/(app)/dashboard",
                "Create layout.tsx for each route group",
                "Set up middleware.ts for auth protection",
            ],
        )


@SkillRegistry.register
class GenerateMiddlewareSkill(BaseSkill):
    name = "nextjs.generate_middleware"
    description = (
        "Generate Next.js middleware.ts for auth protection, redirects, "
        "locale detection, rate limiting, and request logging."
    )
    category = SkillCategory.NEXTJS
    tags = ["middleware", "auth", "redirects", "edge", "i18n"]
    parameters = [
        SkillParameter(
            "features",
            "Comma-separated middleware features: auth-guard, locale, redirect-www, security-headers, rate-limit",
            required=False, default="auth-guard",
        ),
        SkillParameter(
            "protected_paths",
            "Comma-separated protected route prefixes (e.g. /dashboard,/api,/admin)",
            required=False, default="/dashboard",
        ),
        SkillParameter(
            "auth_provider", "Auth provider", required=False, default="nextauth",
            enum=["nextauth", "clerk", "supabase", "custom"],
        ),
        SkillParameter(
            "locales", "Supported locales (e.g. en,pt-BR,es)", required=False, default="",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        features: str = "auth-guard",
        protected_paths: str = "/dashboard",
        auth_provider: str = "nextauth",
        locales: str = "",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
        path_list = [p.strip() for p in protected_paths.split(",") if p.strip()]

        prompt = f"""Generate Next.js middleware.ts with these features: {', '.join(feature_list)}

Protected paths: {', '.join(path_list)}
Auth provider: {auth_provider}
{"Supported locales: " + locales if locales else ""}

Requirements:
- Use NextRequest and NextResponse from 'next/server'
- {"Import auth from 'next-auth' for session check" if auth_provider == "nextauth" else "Use " + auth_provider + " auth helper"}
- matcher config to exclude _next, static files, and public assets
- {"Redirect unauthenticated users to /login with callbackUrl" if "auth-guard" in feature_list else ""}
- {"Detect locale from Accept-Language header, redirect if missing" if "locale" in feature_list else ""}
- {"Add security headers (X-Frame-Options, X-Content-Type-Options, etc.)" if "security-headers" in feature_list else ""}
- {"Redirect www to non-www" if "redirect-www" in feature_list else ""}
- TypeScript throughout

Generate the complete middleware.ts file."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="typescript", context=NEXTJS_EXPERT)
        else:
            code = (
                "import { NextRequest, NextResponse } from 'next/server'\n"
                "import { auth } from '@/auth'\n\n"
                f"const PROTECTED_PATHS = [{', '.join(repr(p) for p in path_list)}]\n\n"
                "export default auth(function middleware(request: NextRequest) {\n"
                "  const { pathname } = request.nextUrl\n"
                "  const session = (request as any).auth\n\n"
                "  const isProtected = PROTECTED_PATHS.some(p => pathname.startsWith(p))\n"
                "  if (isProtected && !session) {\n"
                "    const loginUrl = new URL('/login', request.url)\n"
                "    loginUrl.searchParams.set('callbackUrl', pathname)\n"
                "    return NextResponse.redirect(loginUrl)\n"
                "  }\n\n"
                "  return NextResponse.next()\n"
                "})\n\n"
                "export const config = {\n"
                "  matcher: ['/((?!_next/static|_next/image|favicon.ico|api/auth).*)'],\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated middleware with: {', '.join(feature_list)}",
            artifacts=[CodeArtifact(filename="middleware.ts", content=code, language="typescript")],
            next_steps=[
                "Place middleware.ts at the project root (same level as app/)",
                "Configure AUTH_SECRET in .env",
            ],
        )


@SkillRegistry.register
class GenerateAPIRouteSkill(BaseSkill):
    name = "nextjs.generate_api_route"
    description = (
        "Generate a Next.js App Router Route Handler at src/app/api/{name}/route.js. "
        "API routes are JavaScript files (not TypeScript) — the only JS exception in the project."
    )
    category = SkillCategory.NEXTJS
    tags = ["api-route", "route-handler", "rest", "javascript"]
    parameters = [
        SkillParameter(
            "route",
            "API route name or path relative to /api (e.g. products, users/[id], auth/login). "
            "Do not include /api/ prefix — it is added automatically.",
        ),
        SkillParameter("description", "What this API endpoint does"),
        SkillParameter(
            "methods",
            "HTTP methods to implement (comma-separated): GET, POST, PUT, PATCH, DELETE",
            required=False, default="GET,POST",
        ),
        SkillParameter(
            "auth", "Require authentication", required=False, default="true",
            enum=["true", "false", "optional"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        description: str,
        methods: str = "GET,POST",
        auth: str = "true",
        **_: Any,
    ) -> SkillResult:
        method_list = [m.strip().upper() for m in methods.split(",") if m.strip()]
        # Normalize: strip leading /api/ if caller included it
        clean_route = route.lstrip("/")
        if clean_route.startswith("api/"):
            clean_route = clean_route[len("api/"):]
        is_dynamic = "[" in clean_route
        file_path = f"src/app/api/{clean_route}/route.js"

        prompt = f"""Generate a Next.js App Router Route Handler.

File: `{file_path}`
Description: {description}
Methods: {', '.join(method_list)}
Auth required: {auth}
{"Dynamic segment in route" if is_dynamic else "Static route"}

IMPORTANT: Generate plain JavaScript (NOT TypeScript). No type annotations.

Requirements:
- Import only NextResponse from 'next/server' (no TypeScript types needed)
- {"Check session/auth at the top, return 401 JSON if not authenticated" if auth == "true" else ""}
- For mutation methods (POST/PUT/PATCH): parse request.json() and validate required fields
- Consistent error response format: {{ error: string, code: string }}
- Proper HTTP status codes (200, 201, 400, 401, 403, 404, 500)
- {"Extract dynamic params from the second argument: async function GET(request, {{ params }})" if is_dynamic else ""}

Generate the complete route.js with all {len(method_list)} exported method handler(s).
Plain JavaScript only — no TypeScript syntax."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="javascript", context=NEXTJS_EXPERT)
        else:
            lines = ["import { NextResponse } from 'next/server'\n"]
            if auth == "true":
                lines.append("import { auth } from '@/auth'\n")
            lines.append("")
            for method in method_list:
                param_sig = "(request, { params })" if is_dynamic else "(request)"
                body_lines = []
                if auth == "true":
                    body_lines += [
                        "  const session = await auth()",
                        "  if (!session) {",
                        "    return NextResponse.json({ error: 'Unauthorized', code: 'UNAUTHORIZED' }, { status: 401 })",
                        "  }",
                        "",
                    ]
                if method in ("POST", "PUT", "PATCH"):
                    body_lines += [
                        "  const body = await request.json()",
                        "",
                    ]
                body_lines += [
                    f"  // TODO: implement {method} — {description}",
                    "  return NextResponse.json({ data: null })",
                ]
                handler = (
                    f"export async function {method}{param_sig} {{\n"
                    f"  try {{\n"
                    + "\n".join(f"    {line}" for line in body_lines)
                    + "\n  } catch (error) {\n"
                    "    console.error(error)\n"
                    "    return NextResponse.json({ error: 'Internal server error', code: 'INTERNAL_ERROR' }, { status: 500 })\n"
                    "  }\n"
                    "}"
                )
                lines.append(handler)
            code = "\n".join(lines) + "\n"

        return SkillResult(
            success=True,
            summary=f"Generated Route Handler `{file_path}` [{', '.join(method_list)}]",
            artifacts=[CodeArtifact(
                filename=file_path, content=code, language="javascript",
            )],
            next_steps=[
                f"File created at: {file_path}",
                "API accessible at: /api/" + clean_route,
                "Remember: route.js uses JavaScript — no TypeScript type annotations",
            ],
        )
