
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class ImplementFeatureFlagsSkill(BaseSkill):
    name = "vercel.implement_feature_flags"
    description = "Implement feature flags using Vercel Edge Config for instant rollouts without redeployment."
    category = SkillCategory.VERCEL
    tags = ["feature-flags", "edge-config", "rollout", "a-b-testing", "vercel"]
    parameters = [
        SkillParameter("flags", "Comma-separated feature flag names (e.g. new-checkout, ai-assistant, dark-mode-v2)"),
        SkillParameter("flag_type", "Flag type", required=False, default="boolean", enum=["boolean", "percentage", "user-segment"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        flags: str,
        flag_type: str = "boolean",
        **_: Any,
    ) -> SkillResult:
        flag_list = [f.strip() for f in flags.split(",") if f.strip()]

        client_code = (
            "import { createClient } from '@vercel/edge-config'\n\n"
            "const edgeConfig = createClient(process.env.EDGE_CONFIG)\n\n"
        )

        if flag_type == "boolean":
            client_code += (
                "export async function isFeatureEnabled(flag: string, defaultValue = false): Promise<boolean> {\n"
                "  try {\n"
                "    return await edgeConfig.get<boolean>(flag) ?? defaultValue\n"
                "  } catch {\n"
                "    return defaultValue\n"
                "  }\n"
                "}\n\n"
            )
        elif flag_type == "percentage":
            client_code += (
                "export async function isInPercentage(flag: string, userId: string): Promise<boolean> {\n"
                "  const percentage = await edgeConfig.get<number>(flag) ?? 0\n"
                "  // Deterministic hash of userId so same user always gets same result\n"
                "  const hash = userId.split('').reduce((a, c) => a + c.charCodeAt(0), 0)\n"
                "  return (hash % 100) < percentage\n"
                "}\n\n"
            )

        
        client_code += "// Feature flag keys — typed constants\nexport const FLAGS = {\n"
        for flag in flag_list:
            client_code += f"  {flag.upper().replace('-', '_')}: '{flag}',\n"
        client_code += "} as const\n\n"

        
        client_code += (
            "// Usage in a Server Component:\n"
            "// const isEnabled = await isFeatureEnabled(FLAGS.NEW_CHECKOUT)\n"
            "// if (!isEnabled) redirect('/old-checkout')\n\n"
            "// Usage in middleware.ts:\n"
            "// const enabled = await edgeConfig.get<boolean>('new-feature')\n"
        )

        edge_config_json = "{\n" + "\n".join(f'  "{flag}": false,' for flag in flag_list) + "\n}\n"

        return SkillResult(
            success=True,
            summary=f"Implemented {flag_type} feature flags for: {', '.join(flag_list)}",
            artifacts=[
                CodeArtifact(filename="lib/feature-flags.ts", content=client_code, language="typescript"),
                CodeArtifact(filename="edge-config.json", content=edge_config_json, language="json", description="Initial Edge Config values — import in Vercel dashboard"),
            ],
            dependencies=["@vercel/edge-config"],
            instructions=[
                "Add EDGE_CONFIG env var from Vercel dashboard",
                "Import the Edge Config JSON in your Vercel project settings",
                "Changes to flags take effect instantly (no redeploy needed)",
            ],
        )
