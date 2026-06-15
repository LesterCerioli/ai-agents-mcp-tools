from __future__ import annotations

import json
import re
from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_SYSTEM_PROMPT = """\
You are a senior Next.js 15 / TypeScript engineer specialized in debugging build and type errors.

Given a build error and the source files involved, you will:
1. Identify the root cause of each error
2. Return ONLY the complete fixed source files — never a diff or partial snippet
3. Preserve all existing logic — only fix what is broken
4. Handle TypeScript type errors, missing imports, undefined components, and hydration mismatches
5. Never add features or refactor code beyond what is needed to fix the error

Output ONLY a JSON object with this exact structure (no markdown, no explanation):
{"fixes": [{"path": "relative/path/file.tsx", "content": "full fixed file content"}]}
"""

_FALLBACK_REPORT = """\
## Next.js / TypeScript Diagnostic Report (LLM unavailable)

**Error output captured:**
```
{error_output}
```

**Affected files detected:**
{file_list}

**Common causes for Next.js build failures:**
- TypeScript type mismatch → check prop types match the component signature
- `Module not found` → install the package or check the import path
- Hydration mismatch → wrap client-only code in `useEffect` or use `dynamic(() => ..., {{ssr: false}})`
- Missing `"use client"` directive → add it at the top of files using hooks or browser APIs
- `Cannot find name` → add missing type import from the correct package
- App Router vs Pages Router conflict → check you're using the correct API for your router

Run `npx tsc --noEmit 2>&1` locally to see the full TypeScript error list.
"""


@SkillRegistry.register
class NextJSDiagnoseAndFixSkill(BaseSkill):
    """Analyzes Next.js/TypeScript build errors and returns fixed source files."""

    name = "diagnostic.nextjs_diagnose"
    description = (
        "Analyze Next.js/TypeScript build errors and return fixed source files. "
        "Receives the full `next build` or `tsc --noEmit` stderr output and the content "
        "of affected files. Uses LLM to identify root causes and generate complete corrected files. "
        "Falls back to a structured analysis report when LLM is unavailable."
    )
    category = SkillCategory.DIAGNOSTIC
    tags = ["nextjs", "typescript", "diagnostic", "fix", "debug", "build", "error", "react"]
    parameters = [
        SkillParameter("error_output", "Full output from `next build` or `npx tsc --noEmit`"),
        SkillParameter(
            "source_files",
            'JSON array of affected files: [{"path": "...", "content": "..."}]. '
            "Include all .tsx/.ts files mentioned in the error output.",
        ),
        SkillParameter(
            "next_version",
            "Next.js major version (e.g. 15, 14)",
            required=False,
            default="15",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        error_output: str,
        source_files: str = "[]",
        next_version: str = "15",
        **_: Any,
    ) -> SkillResult:
        try:
            files: list[dict[str, str]] = json.loads(source_files) if source_files else []
        except (json.JSONDecodeError, ValueError):
            files = []

        if self.llm:
            return await self._llm_fix(error_output, files, next_version)

        return self._fallback_report(error_output, files)

    async def _llm_fix(
        self,
        error_output: str,
        files: list[dict[str, str]],
        next_version: str,
    ) -> SkillResult:
        files_block = "\n\n".join(
            f"### {f['path']}\n```tsx\n{f['content']}\n```"
            for f in files
        )
        prompt = (
            f"## Next.js {next_version} / TypeScript Build Error\n\n"
            f"```\n{error_output}\n```\n\n"
            f"## Source Files\n\n{files_block}\n\n"
            'Return the fixed files as JSON: {"fixes": [{"path": "...", "content": "..."}]}'
        )

        raw = await self.llm.chat(prompt, system_prompt=_SYSTEM_PROMPT)
        fixes = _parse_fixes(raw)

        if not fixes:
            return SkillResult.failure(
                f"LLM did not return parseable fixes. Raw response (first 500 chars): {raw[:500]}"
            )

        ext_map = {".ts": "typescript", ".tsx": "tsx", ".js": "javascript", ".jsx": "jsx"}
        artifacts = [
            CodeArtifact(
                filename=fix["path"],
                content=fix["content"],
                language=next((v for k, v in ext_map.items() if fix["path"].endswith(k)), "typescript"),
                description="Fixed by diagnostic.nextjs_diagnose",
            )
            for fix in fixes
        ]

        return SkillResult(
            success=True,
            summary=f"Fixed {len(artifacts)} Next.js/TypeScript file(s) — errors resolved by LLM analysis",
            artifacts=artifacts,
            instructions=[
                "Review each fixed file before committing",
                "Run `npx tsc --noEmit` to confirm TypeScript errors are resolved",
                "Run `next build` to confirm the build passes",
            ],
        )

    def _fallback_report(
        self,
        error_output: str,
        files: list[dict[str, str]],
    ) -> SkillResult:
        file_list = "\n".join(f"- `{f['path']}`" for f in files) if files else "_(none detected)_"
        report = _FALLBACK_REPORT.format(error_output=error_output, file_list=file_list)
        return SkillResult(
            success=True,
            summary="Next.js diagnostic report generated (configure HUGGINGFACE_TOKEN for auto-fix)",
            artifacts=[
                CodeArtifact(
                    filename="diagnostic_report.md",
                    content=report,
                    language="markdown",
                    description="Next.js/TypeScript build error analysis report",
                )
            ],
            instructions=[
                "Set HUGGINGFACE_TOKEN in .env to enable automatic code fixing",
                "Run `npx tsc --noEmit 2>&1` to capture the full TypeScript error list",
            ],
        )


def _parse_fixes(raw: str) -> list[dict[str, str]]:
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "fixes" in data:
            return data["fixes"]
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r'\{.*"fixes"\s*:\s*\[.*\]\s*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group()).get("fixes", [])
        except (json.JSONDecodeError, ValueError):
            pass
    return []
