
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class SetupVercelAnalyticsSkill(BaseSkill):
    name = "vercel.setup_analytics"
    description = "Set up Vercel Analytics and Speed Insights with custom event tracking."
    category = SkillCategory.VERCEL
    tags = ["analytics", "speed-insights", "web-vitals", "vercel", "monitoring"]
    parameters = [
        SkillParameter(
            "features",
            "Comma-separated features to enable: analytics, speed-insights, custom-events",
            required=False, default="analytics,speed-insights",
        ),
        SkillParameter("custom_events", "Comma-separated custom events to track (e.g. signup,purchase,download)", required=False, default=""),
    ]

    async def execute(  # type: ignore[override]
        self,
        features: str = "analytics,speed-insights",
        custom_events: str = "",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
        event_list = [e.strip() for e in custom_events.split(",") if e.strip()] if custom_events else []

        layout_imports = ""
        layout_components = ""

        if "analytics" in feature_list:
            layout_imports += "import { Analytics } from '@vercel/analytics/react'\n"
            layout_components += "      <Analytics />\n"

        if "speed-insights" in feature_list:
            layout_imports += "import { SpeedInsights } from '@vercel/speed-insights/next'\n"
            layout_components += "      <SpeedInsights />\n"

        layout_snippet = (
            f"// Add to app/layout.tsx — inside <body>:\n"
            f"{layout_imports}\n"
            f"// Inside return:\n"
            f"{layout_components}"
        )

        deps = []
        if "analytics" in feature_list:
            deps.append("@vercel/analytics")
        if "speed-insights" in feature_list:
            deps.append("@vercel/speed-insights")

        artifacts = [
            CodeArtifact(filename="ANALYTICS_SETUP.md", content=f"```tsx\n{layout_snippet}\n```", language="markdown"),
        ]

        if event_list:
            events_code = (
                "'use client'\n\n"
                "import { track } from '@vercel/analytics'\n\n"
                "// Custom event tracking functions\n"
                + "\n".join(
                    f"export function track{event.title().replace('-', '')}(properties?: Record<string, unknown>) {{\n"
                    f"  track('{event}', properties)\n"
                    f"}}\n"
                    for event in event_list
                )
                + "\n// Usage:\n"
                + "\n".join(f"// track{e.title().replace('-', '')}({{ userId, plan }})" for e in event_list)
                + "\n"
            )
            artifacts.append(CodeArtifact(filename="lib/analytics.ts", content=events_code, language="typescript"))

        return SkillResult(
            success=True,
            summary=f"Configured Vercel Analytics with: {', '.join(feature_list)}",
            artifacts=artifacts,
            dependencies=deps,
            next_steps=[
                "Enable Analytics in Vercel dashboard (Project → Analytics tab)",
                "Deploy to see data (no data in development)",
                "Custom events appear under the 'Events' tab in Analytics",
            ],
        )
