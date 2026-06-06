
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class SetupSentrySkill(BaseSkill):
    name = "frontend.setup_sentry"
    description = "Set up Sentry error monitoring for Next.js with source maps, user context, and custom error boundaries."
    category = SkillCategory.FRONTEND
    tags = ["sentry", "monitoring", "error-tracking", "observability"]
    parameters = [
        SkillParameter("dsn_env", "Environment variable name for DSN", required=False, default="NEXT_PUBLIC_SENTRY_DSN"),
        SkillParameter("features", "Comma-separated features: replay, profiling, tracing, user-context", required=False, default="replay,tracing"),
    ]

    async def execute(  # type: ignore[override]
        self,
        dsn_env: str = "NEXT_PUBLIC_SENTRY_DSN",
        features: str = "replay,tracing",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        client_config = (
            'import * as Sentry from "@sentry/nextjs"\n\n'
            "Sentry.init({\n"
            f"  dsn: process.env.{dsn_env},\n"
            "  environment: process.env.NODE_ENV,\n"
            "  tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,\n"
            + ("  replaysSessionSampleRate: 0.1,\n  replaysOnErrorSampleRate: 1.0,\n" if "replay" in feature_list else "")
            + ("  integrations: [\n"
               + ("    Sentry.replayIntegration(),\n" if "replay" in feature_list else "")
               + "  ],\n" if any(f in feature_list for f in ["replay"]) else "")
            + "})\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated Sentry setup with: {', '.join(feature_list)}",
            artifacts=[
                CodeArtifact(filename="sentry.client.config.ts", content=client_config, language="typescript"),
            ],
            dependencies=["@sentry/nextjs"],
            instructions=[
                "npx @sentry/wizard@latest -i nextjs",
                f"Add {dsn_env} to .env",
                "Sentry will auto-capture unhandled errors and route performance",
            ],
        )


@SkillRegistry.register
class ImplementToastSystemSkill(BaseSkill):
    name = "frontend.implement_toast_system"
    description = "Set up a toast notification system with Sonner including success, error, loading, and custom toasts."
    category = SkillCategory.FRONTEND
    tags = ["toast", "notifications", "sonner", "ux", "feedback"]
    parameters = [
        SkillParameter("theme", "Toast theme", required=False, default="system", enum=["light", "dark", "system"]),
        SkillParameter("position", "Toast position", required=False, default="bottom-right",
            enum=["top-left", "top-center", "top-right", "bottom-left", "bottom-center", "bottom-right"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        theme: str = "system",
        position: str = "bottom-right",
        **_: Any,
    ) -> SkillResult:
        setup_code = (
            "// In app/layout.tsx, add inside body:\n"
            'import { Toaster } from "sonner"\n\n'
            f"<Toaster\n"
            f'  theme="{theme}"\n'
            f'  position="{position}"\n'
            f"  richColors\n"
            f"  expand\n"
            f"  closeButton\n"
            f"/>\n"
        )

        usage_code = (
            'import { toast } from "sonner"\n\n'
            "// Success\n"
            "toast.success('Product created successfully')\n\n"
            "// Error\n"
            "toast.error('Failed to save', {\n"
            "  description: 'Please check your connection and try again.',\n"
            "  action: { label: 'Retry', onClick: handleRetry },\n"
            "})\n\n"
            "// Loading → then update\n"
            "const id = toast.loading('Saving...')\n"
            "// After async op:\n"
            "toast.success('Saved!', { id })\n"
            "// Or on error:\n"
            "toast.error('Failed', { id })\n\n"
            "// With Server Action\n"
            "async function handleSubmit(formData: FormData) {\n"
            "  const result = await myServerAction(formData)\n"
            "  if (result.success) {\n"
            "    toast.success('Done!')\n"
            "  } else {\n"
            "    toast.error(result.error)\n"
            "  }\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Configured Sonner toast system ({position}, {theme} theme)",
            artifacts=[
                CodeArtifact(filename="TOAST_SETUP.md", content=f"```tsx\n{setup_code}\n```\n\n```tsx\n{usage_code}\n```", language="markdown"),
            ],
            dependencies=["sonner"],
        )
