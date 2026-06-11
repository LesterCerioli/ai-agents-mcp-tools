
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class GenerateEnvValidationSkill(BaseSkill):
    name = "vercel.generate_env_validation"
    description = "Generate environment variable validation with Zod that fails at startup if required vars are missing."
    category = SkillCategory.VERCEL
    tags = ["environment", "env-vars", "validation", "zod", "type-safe"]
    parameters = [
        SkillParameter(
            "server_vars",
            "Comma-separated server-only env vars with types (e.g. DATABASE_URL:url, AUTH_SECRET:string, STRIPE_KEY:string)",
        ),
        SkillParameter(
            "public_vars",
            "Comma-separated public env vars (NEXT_PUBLIC_*) (e.g. NEXT_PUBLIC_BASE_URL:url, NEXT_PUBLIC_ANALYTICS_ID:string)",
            required=False, default="",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        server_vars: str,
        public_vars: str = "",
        **_: Any,
    ) -> SkillResult:
        server_list = [v.strip() for v in server_vars.split(",") if v.strip()]
        public_list = [v.strip() for v in public_vars.split(",") if v.strip()] if public_vars else []

        def var_to_zod(var_def: str) -> tuple[str, str]:
            parts = var_def.split(":")
            name = parts[0].strip()
            type_hint = parts[1].strip() if len(parts) > 1 else "string"
            if type_hint == "url":
                return name, "z.string().url()"
            elif type_hint == "number":
                return name, "z.coerce.number().positive()"
            elif type_hint == "boolean":
                return name, "z.enum(['true', 'false']).transform(v => v === 'true')"
            elif type_hint == "port":
                return name, "z.coerce.number().min(1).max(65535).default(3000)"
            else:
                return name, "z.string().min(1)"

        server_schema = "\n".join(f"  {var_to_zod(v)[0]}: {var_to_zod(v)[1]}," for v in server_list)
        public_schema = "\n".join(f"  {var_to_zod(v)[0]}: {var_to_zod(v)[1]}," for v in public_list)

        code = (
            "import { z } from 'zod'\n\n"
            "const serverEnvSchema = z.object({\n"
            f"{server_schema}\n"
            "})\n\n"
        )

        if public_list:
            code += (
                "const clientEnvSchema = z.object({\n"
                f"{public_schema}\n"
                "})\n\n"
            )

        code += (
            "function validateEnv() {\n"
            "  const serverResult = serverEnvSchema.safeParse(process.env)\n"
            "  if (!serverResult.success) {\n"
            "    console.error('❌ Invalid environment variables:')\n"
            "    console.error(serverResult.error.flatten().fieldErrors)\n"
            "    throw new Error('Invalid environment variables')\n"
            "  }\n"
        )

        if public_list:
            code += (
                "\n  const clientResult = clientEnvSchema.safeParse(process.env)\n"
                "  if (!clientResult.success) {\n"
                "    console.error('❌ Invalid public environment variables:')\n"
                "    console.error(clientResult.error.flatten().fieldErrors)\n"
                "    throw new Error('Invalid public environment variables')\n"
                "  }\n"
                "  return { ...serverResult.data, ...clientResult.data }\n"
            )
        else:
            code += "  return serverResult.data\n"

        code += "}\n\nexport const env = validateEnv()\n"

        env_example = "\n".join(
            f"{v.split(':')[0]}=" for v in server_list + public_list
        )

        return SkillResult(
            success=True,
            summary=f"Generated env validation for {len(server_list)} server + {len(public_list)} public vars",
            artifacts=[
                CodeArtifact(filename="lib/env.ts", content=code, language="typescript"),
                CodeArtifact(filename=".env.example", content=env_example, language="bash"),
            ],
            dependencies=["zod"],
            instructions=[
                "Import env in server code: import { env } from '@/lib/env'",
                "Fails at build time if required vars are missing",
            ],
        )
