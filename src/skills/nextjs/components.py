
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import NEXTJS_EXPERT, STYLED_COMPONENTS_EXPERT


@SkillRegistry.register
class GenerateComponentSkill(BaseSkill):
    name = "nextjs.generate_component"
    description = (
        "Generate a production-ready Next.js component (Server or Client) with TypeScript, "
        "proper types, Tailwind CSS or styled-components, accessibility, and Next.js 15 best practices."
    )
    category = SkillCategory.NEXTJS
    tags = ["component", "react", "typescript", "rsc", "client"]
    parameters = [
        SkillParameter("name", "Component name in PascalCase (e.g. UserCard, ProductList)"),
        SkillParameter("description", "What the component does and what data it displays"),
        SkillParameter(
            "type", "Component type", required=False, default="server",
            enum=["server", "client", "shared"],
        ),
        SkillParameter(
            "props", "Comma-separated prop names (e.g. userId, title, onClose)",
            required=False, default="",
        ),
        SkillParameter(
            "features",
            "Comma-separated features to include: loading, skeleton, error, empty-state, animation, pagination",
            required=False, default="",
        ),
        SkillParameter(
            "styling", "Styling library to use", required=False, default="tailwind",
            enum=["tailwind", "tailwind+shadcn", "css-modules", "styled-components"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        description: str,
        type: str = "server",
        props: str = "",
        features: str = "",
        styling: str = "tailwind",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
        prop_list = [p.strip() for p in props.split(",") if p.strip()]

        is_styled = styling == "styled-components"
        # styled-components always needs 'use client'
        effective_type = "client" if is_styled else type

        prompt = f"""Generate a Next.js 15 {effective_type} component called `{name}`.

Description: {description}

Requirements:
- {"'use client' directive at the top (REQUIRED — styled-components is runtime CSS-in-JS)" if is_styled else "Add 'use client' directive at the top" if effective_type == "client" else "Server Component — no 'use client' directive"}
- TypeScript with strict types — define a `{name}Props` interface
- Styling: {styling}
{"""- Use styled-components v6:
  * Import styled from 'styled-components'
  * Define all styled components OUTSIDE the function body (performance)
  * Use $ prefix for transient props (e.g. $isActive: boolean) to avoid DOM warnings
  * Use shouldForwardProp for custom boolean/enum props
  * Name styled components with Styled prefix (e.g. StyledWrapper, StyledTitle)
  * Use css helper from styled-components for shared style blocks
  * Typed: styled.div<{ $variant: 'primary' | 'secondary' }>``""" if is_styled else ""}
- Props needed: {', '.join(prop_list) if prop_list else 'derive sensible props from the description'}
- Additional features: {', '.join(feature_list) if feature_list else 'clean, focused component'}
- Semantic HTML + ARIA attributes for accessibility
- Export as named export: `export function {name}`

Generate the complete `{name}.tsx` file."""

        ctx = STYLED_COMPONENTS_EXPERT if is_styled else NEXTJS_EXPERT

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=ctx)
        else:
            if is_styled:
                code = (
                    '"use client"\n\n'
                    "import styled, { css } from 'styled-components'\n\n"
                    f"// Styled components defined outside the function body for performance\n"
                    f"const StyledWrapper = styled.section`\n"
                    f"  display: flex;\n"
                    f"  flex-direction: column;\n"
                    f"  gap: 1rem;\n"
                    f"  padding: 1.5rem;\n"
                    f"`\n\n"
                    f"const StyledTitle = styled.h2`\n"
                    f"  font-size: 1.5rem;\n"
                    f"  font-weight: 600;\n"
                    f"  color: ${{({{ theme }}) => theme.colors?.primary ?? 'inherit'}};\n"
                    f"`\n\n"
                    f"interface {name}Props {{\n"
                    f"  className?: string\n"
                    f"}}\n\n"
                    f"export function {name}({{ className }}: {name}Props) {{\n"
                    f"  return (\n"
                    f"    <StyledWrapper className={{className}}>\n"
                    f"      <StyledTitle>{name}</StyledTitle>\n"
                    f"    </StyledWrapper>\n"
                    f"  )\n"
                    f"}}\n"
                )
            else:
                directive = '"use client"\n\n' if effective_type == "client" else ""
                code = (
                    f'{directive}interface {name}Props {{\n'
                    f'  className?: string\n'
                    f'}}\n\n'
                    f'export function {name}({{ className }}: {name}Props) {{\n'
                    f'  return (\n'
                    f'    <section className={{`space-y-4 ${{className}}`}}>\n'
                    f'      <h2 className="text-2xl font-semibold">{name}</h2>\n'
                    f'    </section>\n'
                    f'  )\n'
                    f'}}\n'
                )

        deps = ["styled-components"] if is_styled else []

        return SkillResult(
            success=True,
            summary=f"Generated {effective_type} component `{name}` ({styling})",
            artifacts=[CodeArtifact(
                filename=f"components/{name}.tsx",
                content=code,
                language="tsx",
                description=f"Next.js {effective_type} component with {styling}",
            )],
            dependencies=deps,
            next_steps=[
                *(["Ensure StyledComponentsRegistry is set up in app/layout.tsx (run nextjs.setup_styled_components first)"] if is_styled else []),
                f"import {{ {name} }} from '@/components/{name}'",
                "Add the component to your page or layout",
                "Customize props and styles as needed",
            ],
        )


@SkillRegistry.register
class GeneratePageSkill(BaseSkill):
    name = "nextjs.generate_page"
    description = (
        "Generate a Next.js App Router page (page.tsx) with proper metadata, "
        "async data fetching, TypeScript params, and loading/error boundaries."
    )
    category = SkillCategory.NEXTJS
    tags = ["page", "app-router", "metadata", "typescript"]
    parameters = [
        SkillParameter("route", "Route path (e.g. /products, /blog/[slug], /dashboard/settings)"),
        SkillParameter("description", "What this page shows and does"),
        SkillParameter(
            "features",
            "Comma-separated: metadata, dynamic-params, suspense, auth-check, breadcrumbs",
            required=False, default="metadata",
        ),
        SkillParameter(
            "data_source", "Where data comes from (e.g. database, REST API, GraphQL)",
            required=False, default="",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        description: str,
        features: str = "metadata",
        data_source: str = "",
        **_: Any,
    ) -> SkillResult:
        is_dynamic = "[" in route
        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        prompt = f"""Generate a Next.js 15 App Router page for the route `{route}`.

Page description: {description}
{"Dynamic route params detected in: " + route if is_dynamic else "Static route"}
{"Data source: " + data_source if data_source else ""}

Requirements:
- File: `app{route}/page.tsx`
- Async page component with proper TypeScript
- {"Include generateMetadata() function" if "metadata" in feature_list else ""}
- {"Include params and searchParams types" if is_dynamic else ""}
- {"Wrap data fetching in Suspense" if "suspense" in feature_list else "Server-side data fetching with fetch()"}
- {"Add auth/session check at the top" if "auth-check" in feature_list else ""}
- Export as default: `export default async function Page`
- Use semantic HTML (main, article, section, nav)

Generate the complete page.tsx file."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            slug = route.replace("/", "").replace("[", "").replace("]", "") or "Home"
            code = (
                f"import type {{ Metadata }} from 'next'\n\n"
                f"export const metadata: Metadata = {{\n"
                f"  title: '{slug} Page',\n"
                f"}}\n\n"
                f"export default async function Page() {{\n"
                f"  return (\n"
                f"    <main className=\"container mx-auto px-4 py-8\">\n"
                f"      <h1 className=\"text-3xl font-bold\">{slug}</h1>\n"
                f"    </main>\n"
                f"  )\n"
                f"}}\n"
            )

        filename = f"app{route}/page.tsx"
        return SkillResult(
            success=True,
            summary=f"Generated page for route `{route}`",
            artifacts=[CodeArtifact(filename=filename, content=code, language="tsx")],
            next_steps=[
                f"Create the directory: app{route}/",
                "Add loading.tsx and error.tsx alongside the page",
                "Run `next dev` to see the page",
            ],
        )


@SkillRegistry.register
class GenerateLayoutSkill(BaseSkill):
    name = "nextjs.generate_layout"
    description = (
        "Generate a Next.js layout.tsx with providers, navigation, sidebar, "
        "font loading, and proper metadata configuration."
    )
    category = SkillCategory.NEXTJS
    tags = ["layout", "app-router", "providers", "navigation"]
    parameters = [
        SkillParameter("name", "Layout name (e.g. Root, Dashboard, Marketing)"),
        SkillParameter("route", "Route segment (e.g. / for root, /dashboard for dashboard layout)"),
        SkillParameter(
            "includes",
            "Comma-separated elements: navbar, sidebar, footer, providers, toast, auth-guard",
            required=False, default="navbar,footer",
        ),
        SkillParameter(
            "fonts", "Google Fonts to load via next/font (e.g. Inter, Geist, Roboto)",
            required=False, default="Geist",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        route: str,
        includes: str = "navbar,footer",
        fonts: str = "Geist",
        **_: Any,
    ) -> SkillResult:
        include_list = [i.strip() for i in includes.split(",") if i.strip()]
        is_root = route == "/"

        prompt = f"""Generate a Next.js 15 App Router layout called `{name}Layout` for the `{route}` route segment.

Includes: {', '.join(include_list)}
Fonts: {fonts} (via next/font/google)
{"Root layout — include <html> and <body> tags, font CSS variables" if is_root else "Nested layout — wrap children without html/body"}

Requirements:
- {"Root layout with html lang and font className on body" if is_root else "Nested layout component"}
- Load fonts with next/font/google for zero layout shift
- {"Wrap children in providers (ThemeProvider, QueryClientProvider, etc.)" if "providers" in include_list else ""}
- {"Add responsive navigation component" if "navbar" in include_list else ""}
- {"Add sidebar with navigation links" if "sidebar" in include_list else ""}
- {"Add footer component" if "footer" in include_list else ""}
- {"Add Toaster from sonner for notifications" if "toast" in include_list else ""}
- Proper TypeScript with children: React.ReactNode
- Export as default: `export default function {name}Layout`

Generate the complete layout.tsx file."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                f"import type {{ ReactNode }} from 'react'\n\n"
                f"interface {name}LayoutProps {{\n"
                f"  children: ReactNode\n"
                f"}}\n\n"
                f"export default function {name}Layout({{ children }}: {name}LayoutProps) {{\n"
                f"  return (\n"
                f"    <div className=\"min-h-screen flex flex-col\">\n"
                f"      <main className=\"flex-1\">{'{'}children{'}'}</main>\n"
                f"    </div>\n"
                f"  )\n"
                f"}}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated {name}Layout for `{route}`",
            artifacts=[CodeArtifact(
                filename=f"app{'' if route == '/' else route}/layout.tsx",
                content=code, language="tsx",
            )],
            dependencies=["next", "react"],
            next_steps=[
                "Create child page.tsx files",
                "Add providers to the layout",
                "Configure fonts in tailwind.config.ts",
            ],
        )


@SkillRegistry.register
class GenerateLoadingSkill(BaseSkill):
    name = "nextjs.generate_loading"
    description = (
        "Generate loading.tsx with skeleton screens that match the page layout, "
        "using Suspense boundaries and accessible loading states."
    )
    category = SkillCategory.NEXTJS
    tags = ["loading", "skeleton", "suspense", "ux"]
    parameters = [
        SkillParameter("route", "Route segment this loading screen is for"),
        SkillParameter("layout", "Description of the page layout to create matching skeletons"),
        SkillParameter(
            "style", "Loading style", required=False, default="skeleton",
            enum=["skeleton", "spinner", "shimmer", "pulse"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        layout: str,
        style: str = "skeleton",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate a Next.js loading.tsx for the `{route}` route.

Page layout to match: {layout}
Loading style: {style}

Requirements:
- Create skeleton placeholders that match the real page layout
- Use Tailwind CSS animate-pulse for skeleton effect
- Add aria-busy and aria-label for accessibility
- Match the visual structure of the actual page
- Export as default: `export default function Loading`
- No 'use client' needed (this is a Server Component)

Generate the complete loading.tsx that closely mirrors the page structure with skeleton placeholders."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                "export default function Loading() {\n"
                "  return (\n"
                "    <div aria-busy=\"true\" aria-label=\"Loading content\" className=\"animate-pulse space-y-4 p-8\">\n"
                "      <div className=\"h-8 w-48 rounded-lg bg-muted\" />\n"
                "      <div className=\"space-y-2\">\n"
                "        <div className=\"h-4 rounded bg-muted\" />\n"
                "        <div className=\"h-4 w-5/6 rounded bg-muted\" />\n"
                "        <div className=\"h-4 w-4/6 rounded bg-muted\" />\n"
                "      </div>\n"
                "      <div className=\"grid grid-cols-3 gap-4\">\n"
                "        {Array.from({ length: 6 }).map((_, i) => (\n"
                "          <div key={i} className=\"h-32 rounded-xl bg-muted\" />\n"
                "        ))}\n"
                "      </div>\n"
                "    </div>\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated skeleton loading screen for `{route}`",
            artifacts=[CodeArtifact(
                filename=f"app{route}/loading.tsx", content=code, language="tsx",
            )],
        )


@SkillRegistry.register
class GenerateErrorPageSkill(BaseSkill):
    name = "nextjs.generate_error_page"
    description = (
        "Generate error.tsx and global-error.tsx with retry functionality, "
        "user-friendly messages, and error reporting integration."
    )
    category = SkillCategory.NEXTJS
    tags = ["error", "error-boundary", "client", "ux"]
    parameters = [
        SkillParameter("route", "Route this error boundary covers"),
        SkillParameter(
            "type", "Error page type", required=False, default="error",
            enum=["error", "global-error", "not-found"],
        ),
        SkillParameter(
            "reporting", "Error reporting service", required=False, default="none",
            enum=["none", "sentry", "console"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        route: str,
        type: str = "error",
        reporting: str = "none",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate a Next.js `{type}.tsx` for the `{route}` route.

Error reporting: {reporting}

Requirements:
- Must be a Client Component ('use client' required for error.tsx)
- Props: {{ error: Error & {{ digest?: string }}, reset: () => void }}
- User-friendly error message (not raw error text)
- Retry button that calls reset()
- {"useEffect to report error to " + reporting if reporting != "none" else ""}
- Accessible: role=\"alert\", aria-live=\"assertive\"
- Styled with Tailwind (centered, clean error UI)
- Option to go back to home page

Generate the complete {type}.tsx file."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                '"use client"\n\n'
                "import { useEffect } from 'react'\n\n"
                "interface ErrorPageProps {\n"
                "  error: Error & { digest?: string }\n"
                "  reset: () => void\n"
                "}\n\n"
                "export default function ErrorPage({ error, reset }: ErrorPageProps) {\n"
                "  useEffect(() => {\n"
                "    console.error('Application error:', error)\n"
                "  }, [error])\n\n"
                "  return (\n"
                "    <div role=\"alert\" className=\"flex min-h-[400px] flex-col items-center justify-center gap-4 p-8 text-center\">\n"
                "      <h2 className=\"text-2xl font-semibold\">Something went wrong</h2>\n"
                "      <p className=\"text-muted-foreground\">An unexpected error occurred. Please try again.</p>\n"
                "      <div className=\"flex gap-3\">\n"
                "        <button onClick={reset} className=\"rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90\">\n"
                "          Try again\n"
                "        </button>\n"
                "        <a href=\"/\" className=\"rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent\">\n"
                "          Go home\n"
                "        </a>\n"
                "      </div>\n"
                "    </div>\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated {type} error boundary for `{route}`",
            artifacts=[CodeArtifact(
                filename=f"app{route}/{type}.tsx", content=code, language="tsx",
            )],
            dependencies=["sentry"] if reporting == "sentry" else [],
        )


@SkillRegistry.register
class GenerateFormComponentSkill(BaseSkill):
    name = "nextjs.generate_form_component"
    description = (
        "Generate a React form component with React Hook Form, Zod validation, "
        "Server Actions integration, accessible error messages, and shadcn/ui fields."
    )
    category = SkillCategory.NEXTJS
    tags = ["form", "react-hook-form", "zod", "server-action", "validation"]
    parameters = [
        SkillParameter("name", "Form component name (e.g. LoginForm, CreateProductForm)"),
        SkillParameter("fields", "Comma-separated field definitions (e.g. email:email, password:password, name:text)"),
        SkillParameter("action", "What the form does when submitted (e.g. create a user, login, update product)"),
        SkillParameter(
            "submit_type", "How the form submits", required=False, default="server-action",
            enum=["server-action", "api-route", "mutation"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        fields: str,
        action: str,
        submit_type: str = "server-action",
        **_: Any,
    ) -> SkillResult:
        field_list = [f.strip() for f in fields.split(",") if f.strip()]

        prompt = f"""Generate a form component `{name}` that: {action}

Fields: {', '.join(field_list)}
Submission: {submit_type}

Requirements:
- 'use client' directive
- React Hook Form v7 with useForm()
- Zod schema for validation with descriptive error messages
- shadcn/ui components: Form, FormField, FormItem, FormLabel, FormControl, FormMessage
- Handle pending/loading state with useTransition or isPending
- Display field-level error messages accessibly
- {"useActionState for Server Action binding" if submit_type == "server-action" else "useQuery mutation hook" if submit_type == "mutation" else "fetch POST to API route"}
- Success/error toast notification via sonner
- Accessible: proper labels, aria-describedby for errors

Generate `{name}.tsx` with Zod schema, form component, and all imports."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                '"use client"\n\n'
                "import { useForm } from 'react-hook-form'\n"
                "import { zodResolver } from '@hookform/resolvers/zod'\n"
                "import { z } from 'zod'\n"
                "import { Button } from '@/components/ui/button'\n"
                "import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'\n"
                "import { Input } from '@/components/ui/input'\n\n"
                f"const {name.replace('Form', '')}Schema = z.object({{\n"
                "  email: z.string().email('Invalid email address'),\n"
                "  password: z.string().min(8, 'Password must be at least 8 characters'),\n"
                "})\n\n"
                f"type {name.replace('Form', '')}Data = z.infer<typeof {name.replace('Form', '')}Schema>\n\n"
                f"export function {name}() {{\n"
                f"  const form = useForm<{name.replace('Form', '')}Data>({{\n"
                f"    resolver: zodResolver({name.replace('Form', '')}Schema),\n"
                "  })\n\n"
                "  async function onSubmit(data: " + name.replace("Form", "") + "Data) {\n"
                "    console.log(data)\n"
                "  }\n\n"
                "  return (\n"
                "    <Form {...form}>\n"
                "      <form onSubmit={form.handleSubmit(onSubmit)} className=\"space-y-4\">\n"
                "        <FormField control={form.control} name=\"email\" render={({ field }) => (\n"
                "          <FormItem>\n"
                "            <FormLabel>Email</FormLabel>\n"
                "            <FormControl><Input type=\"email\" {...field} /></FormControl>\n"
                "            <FormMessage />\n"
                "          </FormItem>\n"
                "        )} />\n"
                "        <Button type=\"submit\" disabled={form.formState.isSubmitting}>Submit</Button>\n"
                "      </form>\n"
                "    </Form>\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated form component `{name}`",
            artifacts=[CodeArtifact(filename=f"components/{name}.tsx", content=code, language="tsx")],
            dependencies=["react-hook-form", "@hookform/resolvers", "zod", "sonner"],
            instructions=[
                "Run: npx shadcn@latest add form input button",
                "Create the matching Server Action or API route",
            ],
        )


@SkillRegistry.register
class SetupStyledComponentsSkill(BaseSkill):
    name = "nextjs.setup_styled_components"
    description = (
        "Set up styled-components v6 with Next.js 15 App Router: SSR registry, "
        "ThemeProvider, global styles, next.config.ts, and TypeScript theme types."
    )
    category = SkillCategory.NEXTJS
    tags = ["styled-components", "css-in-js", "ssr", "theme", "setup"]
    parameters = [
        SkillParameter(
            "theme_tokens",
            "Comma-separated design tokens as name:value (e.g. primary:#7c3aed,secondary:#0ea5e9,radius:8px,fontSans:Inter)",
            required=False, default="primary:#7c3aed,secondary:#0ea5e9,background:#ffffff,text:#0f0f0f,radius:8px",
        ),
        SkillParameter(
            "features",
            "Comma-separated features: dark-mode, global-styles, animations",
            required=False, default="global-styles,dark-mode",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        theme_tokens: str = "primary:#7c3aed,secondary:#0ea5e9,background:#ffffff,text:#0f0f0f,radius:8px",
        features: str = "global-styles,dark-mode",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        # Parse theme tokens
        tokens: dict[str, str] = {}
        for pair in theme_tokens.split(","):
            pair = pair.strip()
            if ":" in pair:
                k, v = pair.split(":", 1)
                tokens[k.strip()] = v.strip()

        # 1. StyledComponentsRegistry — required for SSR in App Router
        registry_code = (
            '"use client"\n\n'
            "import React, { useState } from 'react'\n"
            "import { useServerInsertedHTML } from 'next/navigation'\n"
            "import { ServerStyleSheet, StyleSheetManager } from 'styled-components'\n\n"
            "export function StyledComponentsRegistry({ children }: { children: React.ReactNode }) {\n"
            "  const [styledComponentsStyleSheet] = useState(() => new ServerStyleSheet())\n\n"
            "  useServerInsertedHTML(() => {\n"
            "    const styles = styledComponentsStyleSheet.getStyleElement()\n"
            "    styledComponentsStyleSheet.instance.clearTag()\n"
            "    return <>{styles}</>\n"
            "  })\n\n"
            "  if (typeof window !== 'undefined') return <>{children}</>\n\n"
            "  return (\n"
            "    <StyleSheetManager sheet={styledComponentsStyleSheet.instance}>\n"
            "      {children}\n"
            "    </StyleSheetManager>\n"
            "  )\n"
            "}\n"
        )

        # 2. Theme types (DefaultTheme augmentation)
        light_tokens = "\n".join(f"    {k}: string" for k in tokens)
        theme_types_code = (
            "import 'styled-components'\n\n"
            "declare module 'styled-components' {\n"
            "  export interface DefaultTheme {\n"
            "    colors: {\n"
            f"{light_tokens}\n"
            "    }\n"
            "    radii: {\n"
            "      sm: string\n"
            "      md: string\n"
            "      lg: string\n"
            "      full: string\n"
            "    }\n"
            "    fonts: {\n"
            "      sans: string\n"
            "      mono: string\n"
            "    }\n"
            "    transitions: {\n"
            "      fast: string\n"
            "      normal: string\n"
            "    }\n"
            "  }\n"
            "}\n"
        )

        # 3. Theme object
        color_entries = "\n".join(f"    {k}: '{v}'," for k, v in tokens.items())
        theme_code = (
            "import type { DefaultTheme } from 'styled-components'\n\n"
            "export const lightTheme: DefaultTheme = {\n"
            "  colors: {\n"
            f"{color_entries}\n"
            "  },\n"
            "  radii: {\n"
            "    sm: '4px', md: '8px', lg: '12px', full: '9999px',\n"
            "  },\n"
            "  fonts: {\n"
            "    sans: 'var(--font-sans, system-ui, sans-serif)',\n"
            "    mono: 'var(--font-mono, monospace)',\n"
            "  },\n"
            "  transitions: {\n"
            "    fast: '150ms ease',\n"
            "    normal: '300ms ease',\n"
            "  },\n"
            "}\n\n"
        )

        if "dark-mode" in feature_list:
            dark_tokens = {
                k: (v.replace("#ffffff", "#0f0f0f").replace("#0f0f0f", "#ffffff")
                    if "background" in k or "text" in k else v)
                for k, v in tokens.items()
            }
            dark_entries = "\n".join(f"    {k}: '{v}'," for k, v in dark_tokens.items())
            theme_code += (
                "export const darkTheme: DefaultTheme = {\n"
                "  ...lightTheme,\n"
                "  colors: {\n"
                f"{dark_entries}\n"
                "  },\n"
                "}\n"
            )

        # 4. GlobalStyles
        global_styles_code = ""
        if "global-styles" in feature_list:
            global_styles_code = (
                '"use client"\n\n'
                "import { createGlobalStyle } from 'styled-components'\n\n"
                "export const GlobalStyles = createGlobalStyle`\n"
                "  *, *::before, *::after {\n"
                "    box-sizing: border-box;\n"
                "    margin: 0;\n"
                "    padding: 0;\n"
                "  }\n\n"
                "  html {\n"
                "    font-size: 16px;\n"
                "    -webkit-font-smoothing: antialiased;\n"
                "    -moz-osx-font-smoothing: grayscale;\n"
                "  }\n\n"
                "  body {\n"
                "    font-family: ${({ theme }) => theme.fonts.sans};\n"
                "    background-color: ${({ theme }) => theme.colors.background};\n"
                "    color: ${({ theme }) => theme.colors.text};\n"
                "    transition: background-color ${({ theme }) => theme.transitions.normal},\n"
                "                color ${({ theme }) => theme.transitions.normal};\n"
                "  }\n\n"
                "  a {\n"
                "    color: ${({ theme }) => theme.colors.primary};\n"
                "    text-decoration: none;\n"
                "    &:hover { text-decoration: underline; }\n"
                "  }\n\n"
                "  img, video { max-width: 100%; display: block; }\n"
                "`\n"
            )

        # 5. Providers wrapper (ThemeProvider + GlobalStyles)
        providers_code = (
            '"use client"\n\n'
            "import { ThemeProvider } from 'styled-components'\n"
            "import { useState } from 'react'\n"
            "import { lightTheme, darkTheme } from '@/styles/theme'\n"
            + ("import { GlobalStyles } from '@/styles/global'\n" if "global-styles" in feature_list else "")
            + "\n"
            "export function StyledProviders({ children }: { children: React.ReactNode }) {\n"
            + ("  const [isDark, setIsDark] = useState(false)\n"
               "  const theme = isDark ? darkTheme : lightTheme\n"
               if "dark-mode" in feature_list else
               "  const theme = lightTheme\n")
            + "\n"
            "  return (\n"
            "    <ThemeProvider theme={theme}>\n"
            + ("      <GlobalStyles />\n" if "global-styles" in feature_list else "")
            + "      {children}\n"
            "    </ThemeProvider>\n"
            "  )\n"
            "}\n"
        )

        # 6. next.config.ts update instruction
        next_config_code = (
            "import type { NextConfig } from 'next'\n\n"
            "const config: NextConfig = {\n"
            "  compiler: {\n"
            "    styledComponents: true,  // Enable SWC transform for styled-components\n"
            "  },\n"
            "}\n\n"
            "export default config\n"
        )

        # 7. Usage example in layout.tsx
        layout_snippet = (
            "// app/layout.tsx — wrap children with both registries:\n"
            "import { StyledComponentsRegistry } from '@/lib/registry'\n"
            "import { StyledProviders } from '@/components/providers/StyledProviders'\n\n"
            "export default function RootLayout({ children }: { children: React.ReactNode }) {\n"
            "  return (\n"
            "    <html lang='pt-BR'>\n"
            "      <body>\n"
            "        <StyledComponentsRegistry>\n"
            "          <StyledProviders>\n"
            "            {children}\n"
            "          </StyledProviders>\n"
            "        </StyledComponentsRegistry>\n"
            "      </body>\n"
            "    </html>\n"
            "  )\n"
            "}\n"
        )

        artifacts = [
            CodeArtifact(filename="lib/registry.tsx", content=registry_code, language="tsx",
                         description="StyledComponentsRegistry for SSR — required for App Router"),
            CodeArtifact(filename="styles/theme.ts", content=theme_code, language="typescript",
                         description="Theme object with all design tokens"),
            CodeArtifact(filename="types/styled.d.ts", content=theme_types_code, language="typescript",
                         description="TypeScript DefaultTheme augmentation"),
            CodeArtifact(filename="components/providers/StyledProviders.tsx", content=providers_code,
                         language="tsx", description="ThemeProvider + GlobalStyles wrapper"),
            CodeArtifact(filename="next.config.ts", content=next_config_code, language="typescript",
                         description="Enable styled-components SWC compiler transform"),
        ]

        if global_styles_code:
            artifacts.insert(3, CodeArtifact(filename="styles/global.ts", content=global_styles_code,
                                             language="typescript", description="Global CSS reset and base styles"))

        return SkillResult(
            success=True,
            summary="Configured styled-components v6 with Next.js 15 App Router SSR",
            artifacts=artifacts,
            dependencies=["styled-components"],
            dev_dependencies=["@types/styled-components"],
            instructions=[
                "npm install styled-components && npm install -D @types/styled-components",
                "Add StyledComponentsRegistry + StyledProviders to app/layout.tsx (see layout snippet artifact)",
                "Set compiler.styledComponents = true in next.config.ts",
            ],
            next_steps=[
                "Run: nextjs.generate_component with styling='styled-components'",
                "Access theme in components: ${({ theme }) => theme.colors.primary}",
                "Use transient props ($propName) to avoid DOM warnings",
            ],
        )


@SkillRegistry.register
class DecomposeIntoComponentsSkill(BaseSkill):
    name = "nextjs.decompose_into_components"
    description = (
        "Analyze a UI description and decompose it into a component hierarchy following "
        "atomic design principles: atoms, molecules, organisms, and generate each component."
    )
    category = SkillCategory.NEXTJS
    tags = ["componentization", "atomic-design", "architecture", "decomposition", "composition"]
    parameters = [
        SkillParameter("ui_description", "Full description of the UI to decompose (e.g. e-commerce product listing page with header, filters sidebar, product grid, product cards, pagination)"),
        SkillParameter(
            "styling", "Styling approach for all generated components", required=False, default="tailwind",
            enum=["tailwind", "tailwind+shadcn", "styled-components", "css-modules"],
        ),
        SkillParameter(
            "granularity", "How deep to decompose", required=False, default="molecules",
            enum=["atoms", "molecules", "organisms"],
        ),
        SkillParameter(
            "generate_code", "Generate actual component code (requires LLM for best results)", required=False, default="true",
            enum=["true", "false"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        ui_description: str,
        styling: str = "tailwind",
        granularity: str = "molecules",
        generate_code: str = "true",
        **_: Any,
    ) -> SkillResult:
        is_styled = styling == "styled-components"
        ctx = STYLED_COMPONENTS_EXPERT if is_styled else NEXTJS_EXPERT

        decompose_prompt = f"""Analyze this UI and decompose it into a React component hierarchy.

UI to decompose: {ui_description}
Styling: {styling}
Decompose down to: {granularity} level

Apply atomic design:
- Atoms: smallest reusable UI units (Button, Badge, Avatar, Icon, Input, Label)
- Molecules: groups of atoms with a specific function (SearchBar = Input + Button, ProductPrice = Price + Badge)
- Organisms: complex UI sections (ProductCard = Image + Title + Price + Button, ProductGrid = list of ProductCards)
- Templates: page layouts (ProductListingTemplate = Header + Sidebar + ProductGrid + Pagination)
- Pages: instances of templates with real data

For each component output:
1. Component name (PascalCase)
2. Level (atom/molecule/organism/template)
3. Props interface (TypeScript)
4. Children/sub-components it uses
5. Which parent uses this component

Format as a clear component tree then generate TypeScript interfaces for all components.
{"Then generate the actual TSX code for each component with " + styling + " styles." if generate_code == "true" else ""}"""

        artifacts: list[CodeArtifact] = []

        if self.llm:
            tree_analysis = await self.llm.chat(decompose_prompt, system_prompt=ctx)

            if generate_code == "true":
                # Generate code for each identified component
                code_prompt = f"""Based on this component decomposition:
{tree_analysis}

Generate the complete TypeScript/TSX code for each component with {styling} styling.
For each component, create a separate file.
Components must import their sub-components correctly.
{"All components using styled-components must have 'use client' at the top." if is_styled else ""}

Generate all component files, starting with atoms, then molecules, then organisms."""

                all_code = await self.llm.generate_code(code_prompt, language="tsx", context=ctx)
                artifacts.append(CodeArtifact(
                    filename="components/DECOMPOSED.tsx",
                    content=all_code,
                    language="tsx",
                    description="All decomposed components — split into individual files",
                ))

            artifacts.insert(0, CodeArtifact(
                filename="COMPONENT_TREE.md",
                content=f"# Component Decomposition\n\n## UI: {ui_description}\n\n{tree_analysis}",
                language="markdown",
                description="Full component hierarchy analysis",
            ))
        else:
            # Template-based decomposition guide
            tree = self._build_template_tree(ui_description, styling, is_styled)
            artifacts.append(CodeArtifact(
                filename="COMPONENT_TREE.md",
                content=tree,
                language="markdown",
                description="Component hierarchy guide — add LLM for actual code generation",
            ))
            artifacts.append(CodeArtifact(
                filename="components/index.ts",
                content=self._build_barrel_exports(ui_description, is_styled),
                language="typescript",
                description="Barrel exports for all components",
            ))

        deps = ["styled-components"] if is_styled else []
        return SkillResult(
            success=True,
            summary=f"Decomposed UI into component hierarchy ({styling})",
            artifacts=artifacts,
            dependencies=deps,
            instructions=[
                "Split DECOMPOSED.tsx into individual files per component",
                "Start with atoms (no dependencies), then molecules, then organisms",
            ] if generate_code == "true" else [
                "Use COMPONENT_TREE.md as the blueprint",
                "Add HUGGINGFACE_TOKEN to generate actual component code",
            ],
            next_steps=[
                "Run nextjs.setup_styled_components first if using styled-components",
                "Create atoms first: they have no component dependencies",
                "Compose molecules from atoms using import statements",
            ],
        )

    def _build_template_tree(self, ui: str, styling: str, is_styled: bool) -> str:
        directive = "'use client' (required for styled-components)" if is_styled else "server or client as needed"
        return f"""# Component Decomposition Guide
## UI: {ui}
## Styling: {styling}
## Directive: {directive}

## Atomic Design Hierarchy

### Atoms (base primitives — no component dependencies)
```
atoms/
├── Button.tsx          # variant: primary|secondary|ghost|destructive, size: sm|md|lg
├── Badge.tsx           # variant: default|success|warning|error
├── Avatar.tsx          # src, alt, size, fallback
├── Icon.tsx            # name, size, color
├── Spinner.tsx         # size, color
├── Divider.tsx         # orientation: horizontal|vertical
└── Typography.tsx      # variant: h1-h6|body|caption|label
```

### Molecules (composed of atoms — one focused function)
```
molecules/
├── SearchBar.tsx       # Input + Button + Icon
├── PriceDisplay.tsx    # Typography + Badge (discount)
├── RatingStars.tsx     # Icon (repeated) + Typography (count)
├── UserMenu.tsx        # Avatar + DropdownMenu
├── Pagination.tsx      # Button (prev/next) + Typography (page info)
└── FilterChip.tsx      # Badge + Icon (close) — selectable
```

### Organisms (complex, self-contained sections)
```
organisms/
├── Header.tsx          # Logo + Navigation + SearchBar + UserMenu
├── Sidebar.tsx         # FilterSection[] (groups of FilterChips)
├── ProductCard.tsx     # Image + Typography + PriceDisplay + RatingStars + Button
├── ProductGrid.tsx     # ProductCard[] in responsive grid
└── Footer.tsx          # Links + Typography + Newsletter form
```

### Templates (page layouts)
```
templates/
└── ProductListingTemplate.tsx   # Header + Sidebar + ProductGrid + Pagination + Footer
```

### Pages (templates with real data)
```
app/
└── products/
    └── page.tsx        # ProductListingTemplate with data fetching
```

## Component Props Convention ({styling})
- All props interfaces: `interface ComponentProps {{ ... }}`
- Optional props use `?`
- Children: `children: React.ReactNode`
{"- Transient styled-components props use $ prefix: `$isActive: boolean`" if is_styled else "- className?: string for custom overrides"}
- Event handlers: `on[Event]: (param: Type) => void`

## Composition Example
```tsx
// organisms/ProductCard.tsx
{"'use client'" if is_styled else "// Server or Client based on interactivity"}
import {{ Badge }} from '@/components/atoms/Badge'
import {{ PriceDisplay }} from '@/components/molecules/PriceDisplay'
import {{ Button }} from '@/components/atoms/Button'

export function ProductCard({{ product }}: ProductCardProps) {{
  return (
    <article>
      <img src={{product.image}} alt={{product.name}} />
      <h3>{{product.name}}</h3>
      <PriceDisplay price={{product.price}} discount={{product.discount}} />
      <Button variant="primary">Add to cart</Button>
    </article>
  )
}}
```
"""

    def _build_barrel_exports(self, ui: str, is_styled: bool) -> str:
        comment = "// Barrel exports — import components from '@/components'\n"
        comment += "// Generated for: " + ui[:60] + "\n\n"
        comment += "// Atoms\nexport * from './atoms/Button'\nexport * from './atoms/Badge'\nexport * from './atoms/Avatar'\n\n"
        comment += "// Molecules\nexport * from './molecules/SearchBar'\nexport * from './molecules/PriceDisplay'\n\n"
        comment += "// Organisms\nexport * from './organisms/ProductCard'\nexport * from './organisms/ProductGrid'\nexport * from './organisms/Header'\n"
        return comment
