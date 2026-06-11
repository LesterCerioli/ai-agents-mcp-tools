
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class SetupI18nSkill(BaseSkill):
    name = "frontend.setup_i18n"
    description = "Set up next-intl for internationalization with locale routing, message files, and type-safe translations."
    category = SkillCategory.FRONTEND
    tags = ["i18n", "next-intl", "localization", "translations"]
    parameters = [
        SkillParameter("locales", "Comma-separated locales (e.g. en,pt-BR,es,fr)"),
        SkillParameter("default_locale", "Default locale (e.g. en)", required=False, default="en"),
        SkillParameter("namespaces", "Translation namespaces (e.g. common,auth,dashboard)", required=False, default="common"),
    ]

    async def execute(  # type: ignore[override]
        self,
        locales: str,
        default_locale: str = "en",
        namespaces: str = "common",
        **_: Any,
    ) -> SkillResult:
        locale_list = [l.strip() for l in locales.split(",") if l.strip()]
        ns_list = [n.strip() for n in namespaces.split(",") if n.strip()]

        i18n_config = (
            "import { notFound } from 'next/navigation'\n"
            "import { getRequestConfig } from 'next-intl/server'\n\n"
            f"export const locales = [{', '.join(repr(l) for l in locale_list)}] as const\n"
            f"export type Locale = typeof locales[number]\n\n"
            "export default getRequestConfig(async ({ locale }) => {\n"
            "  if (!locales.includes(locale as Locale)) notFound()\n\n"
            "  return {\n"
            "    messages: (await import(`../messages/${locale}.json`)).default,\n"
            "  }\n"
            "})\n"
        )

        middleware = (
            "import createMiddleware from 'next-intl/middleware'\n"
            f"import {{ locales }} from './i18n'\n\n"
            "export default createMiddleware({\n"
            f"  locales,\n"
            f"  defaultLocale: '{default_locale}',\n"
            "  localePrefix: 'as-needed',\n"
            "})\n\n"
            "export const config = {\n"
            "  matcher: ['/((?!_next|.*\\\\..*).*)'],\n"
            "}\n"
        )

        en_messages: dict[str, dict] = {ns: {} for ns in ns_list}
        if "common" in en_messages:
            en_messages["common"] = {
                "nav": {"home": "Home", "about": "About", "contact": "Contact"},
                "actions": {"save": "Save", "cancel": "Cancel", "delete": "Delete", "edit": "Edit"},
                "status": {"loading": "Loading...", "error": "An error occurred", "success": "Success!"},
            }
        if "auth" in en_messages:
            en_messages["auth"] = {
                "login": {"title": "Sign in", "email": "Email", "password": "Password", "submit": "Sign in", "forgot": "Forgot password?"},
                "register": {"title": "Create account", "submit": "Create account"},
            }

        import json
        en_json = json.dumps(en_messages, indent=2)

        return SkillResult(
            success=True,
            summary=f"Set up next-intl for {len(locale_list)} locales: {', '.join(locale_list)}",
            artifacts=[
                CodeArtifact(filename="i18n.ts", content=i18n_config, language="typescript"),
                CodeArtifact(filename="middleware.ts", content=middleware, language="typescript"),
                CodeArtifact(filename="messages/en.json", content=en_json, language="json"),
            ],
            dependencies=["next-intl"],
            instructions=[
                "Move app/ pages to app/[locale]/ folder",
                f"Create messages/{default_locale}.json with translations",
                "Wrap app/[locale]/layout.tsx with NextIntlClientProvider",
            ],
        )
