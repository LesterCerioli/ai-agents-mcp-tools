from __future__ import annotations

import json
import re
from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

_SYSTEM_PROMPT = """\
You are a senior Python engineer specialized in debugging runtime and import errors.

Given an error traceback and the source files involved, you will:
1. Identify the root cause of each error
2. Return ONLY the complete fixed source files — never a diff or partial snippet
3. Preserve all existing logic — only fix what is broken
4. Handle ImportError, ModuleNotFoundError, TypeError, AttributeError, IndentationError, and SyntaxError
5. Never add features or refactor code beyond what is needed to fix the error

Output ONLY a JSON object with this exact structure (no markdown, no explanation):
{"fixes": [{"path": "relative/path/file.py", "content": "full fixed file content"}]}
"""

_FALLBACK_REPORT = """\
## Python Diagnostic Report (LLM unavailable)

**Error output captured:**
```
{error_output}
```

**Affected files detected:**
{file_list}

**Common causes for Python startup/runtime failures:**
- `ModuleNotFoundError` → package not installed, run `pip install <package>`
- `ImportError` → circular import or wrong module path
- `IndentationError` / `SyntaxError` → fix the indentation or syntax at the line indicated
- `AttributeError: module has no attribute` → wrong attribute name or missing `__init__.py` export
- `TypeError` → wrong argument count/types passed to a function
- `RuntimeError: no running event loop` → async code called outside an event loop, use `asyncio.run()`
- FastAPI/pydantic validation error → check model field types match what's being passed

Run `python -m py_compile <file.py>` to check for syntax errors without executing.
Run `python -c "import <module>"` to check for import errors.
"""


@SkillRegistry.register
class PythonDiagnoseAndFixSkill(BaseSkill):
    """Analyzes Python runtime/import errors and returns fixed source files."""

    name = "diagnostic.python_diagnose"
    description = (
        "Analyze Python runtime errors, tracebacks, and import failures, then return fixed source files. "
        "Receives the full stderr/traceback output and the content of affected files. "
        "Uses LLM to identify root causes and generate complete corrected files. "
        "Falls back to a structured analysis report when LLM is unavailable."
    )
    category = SkillCategory.DIAGNOSTIC
    tags = ["python", "diagnostic", "fix", "debug", "runtime", "traceback", "error", "fastapi"]
    parameters = [
        SkillParameter(
            "error_output",
            "Full Python traceback or stderr output (e.g. from `python app.py` or `uvicorn main:app`)",
        ),
        SkillParameter(
            "source_files",
            'JSON array of affected files: [{"path": "...", "content": "..."}]. '
            "Include all .py files referenced in the traceback.",
        ),
        SkillParameter(
            "python_version",
            "Python major.minor version (e.g. 3.12)",
            required=False,
            default="3.12",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        error_output: str,
        source_files: str = "[]",
        python_version: str = "3.12",
        **_: Any,
    ) -> SkillResult:
        try:
            files: list[dict[str, str]] = json.loads(source_files) if source_files else []
        except (json.JSONDecodeError, ValueError):
            files = []

        if self.llm:
            return await self._llm_fix(error_output, files, python_version)

        return self._fallback_report(error_output, files)

    async def _llm_fix(
        self,
        error_output: str,
        files: list[dict[str, str]],
        python_version: str,
    ) -> SkillResult:
        files_block = "\n\n".join(
            f"### {f['path']}\n```python\n{f['content']}\n```"
            for f in files
        )
        prompt = (
            f"## Python {python_version} Runtime Error\n\n"
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

        artifacts = [
            CodeArtifact(
                filename=fix["path"],
                content=fix["content"],
                language="python",
                description="Fixed by diagnostic.python_diagnose",
            )
            for fix in fixes
        ]

        return SkillResult(
            success=True,
            summary=f"Fixed {len(artifacts)} Python file(s) — errors resolved by LLM analysis",
            artifacts=artifacts,
            instructions=[
                "Review each fixed file before deploying",
                "Run `python -m py_compile <file.py>` to verify syntax",
                "Run your tests to ensure no regressions",
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
            summary="Python diagnostic report generated (configure HUGGINGFACE_TOKEN for auto-fix)",
            artifacts=[
                CodeArtifact(
                    filename="diagnostic_report.md",
                    content=report,
                    language="markdown",
                    description="Python runtime error analysis report",
                )
            ],
            instructions=[
                "Set HUGGINGFACE_TOKEN in .env to enable automatic code fixing",
                "Run `python -m py_compile <file.py> 2>&1` to capture syntax errors",
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
