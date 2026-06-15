from __future__ import annotations

import json
import re
from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry

# ── Pattern-based fixes (no LLM needed) ─────────────────────────────────────

_PATTERN_FIXES: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"go\.mod requires go\s*>=?\s*(\d+\.\d+).*running go\s*(\d+\.\d+)", re.IGNORECASE),
        "go_version_mismatch",
        "Go version mismatch — go.mod requires newer Go than Dockerfile/environment provides",
    ),
    (
        re.compile(r"GOTOOLCHAIN=local.*go\.mod requires|go: go\.mod requires go\s*>=", re.IGNORECASE),
        "go_version_mismatch",
        "Go toolchain version mismatch",
    ),
    (
        re.compile(r"stat .+: directory not found|no such file or directory.*cmd", re.IGNORECASE),
        "dockerfile_build_path",
        "Wrong build path in Dockerfile — entry point directory does not exist",
    ),
    (
        re.compile(r"missing go\.sum entry", re.IGNORECASE),
        "missing_go_sum",
        "Missing go.sum — dependencies not downloaded",
    ),
    (
        re.compile(r"no required module provides|cannot find module|module.*not found", re.IGNORECASE),
        "missing_module",
        "Module not found — dependency missing from go.mod",
    ),
    (
        re.compile(r"go: updates to go\.sum needed", re.IGNORECASE),
        "missing_go_sum",
        "go.sum out of date",
    ),
    (
        re.compile(r"imported and not used", re.IGNORECASE),
        "unused_import",
        "Unused import(s) in source files",
    ),
    (
        re.compile(r"undefined:?\s+\S+", re.IGNORECASE),
        "undefined_symbol",
        "Undefined symbol — missing import or wrong package name",
    ),
    (
        re.compile(r"cannot use .+ as type .+|cannot use .+ \(type .+\) as type", re.IGNORECASE),
        "type_mismatch",
        "Type mismatch — interface not satisfied or wrong argument type",
    ),
    (
        re.compile(r"declared and not used", re.IGNORECASE),
        "unused_variable",
        "Declared and not used — remove unused variable(s)",
    ),
]

_COMMAND_FIXES: dict[str, dict[str, Any]] = {
    "dockerfile_build_path": {
        "title": "Wrong Build Path in Dockerfile",
        "root_cause": (
            "The `go build` command in the Dockerfile references a directory that does not exist "
            "(e.g. `./cmd/server`). The correct path is where `main.go` lives — usually `./cmd`."
        ),
        "commands": [],
        "explanation": (
            "Update the `go build` line in your Dockerfile to use the correct entry point path. "
            "If your `main.go` is in `cmd/`, use `./cmd`. "
            "If it is in `cmd/main/`, use `./cmd/main`."
        ),
    },
    "go_version_mismatch": {
        "title": "Go Version Mismatch — Dockerfile vs go.mod",
        "root_cause": (
            "The `go.mod` file declares a minimum Go version that is newer than "
            "the Go toolchain available in the Docker build stage (or local environment). "
            "Docker cannot satisfy the `go.mod` requirement during `go mod download`."
        ),
        "commands": [],
        "explanation": (
            "Update the `FROM golang:X.Y-alpine` line in your Dockerfile to match "
            "the version declared in go.mod, or lower the go directive in go.mod "
            "to match the available toolchain."
        ),
    },
    "missing_go_sum": {
        "title": "Missing go.sum / Dependencies Not Downloaded",
        "root_cause": (
            "The `go.sum` file is missing or incomplete. This file records the expected "
            "cryptographic hashes of module dependencies. It must be generated before building."
        ),
        "commands": [
            ("go mod tidy", "Downloads all dependencies and regenerates go.sum"),
            ("go mod download", "(Alternative) Downloads modules listed in go.mod"),
        ],
        "explanation": (
            "Run `go mod tidy` from the project root. It will:\n"
            "  1. Download all packages listed in go.mod\n"
            "  2. Create/update go.sum with the correct checksums\n"
            "  3. Remove any unused entries from go.mod\n\n"
            "After that, run `go build ./...` again — it should compile cleanly."
        ),
    },
    "missing_module": {
        "title": "Module Not Found",
        "root_cause": "A required module is not listed in go.mod or has not been downloaded.",
        "commands": [
            ("go mod tidy", "Re-resolve all dependencies"),
            ("go get <module>@<version>", "Add a specific missing module"),
        ],
        "explanation": "Run `go mod tidy` first. If a specific package is still missing, add it with `go get <package-path>`.",
    },
    "unused_import": {
        "title": "Unused Import(s)",
        "root_cause": "Go does not allow unused imports — they must be removed from the source files.",
        "commands": [
            ("goimports -w ./...", "Auto-remove unused imports (recommended)"),
            ("gofmt -w ./...", "Format code (does not remove imports)"),
        ],
        "explanation": "Find the file and line reported in the error and remove the unused import statement.",
    },
    "undefined_symbol": {
        "title": "Undefined Symbol",
        "root_cause": "A function, type, or variable is referenced but not found in the current package or imports.",
        "commands": [
            ("go build ./... 2>&1 | head -20", "See the full list of undefined symbols"),
        ],
        "explanation": "Check the import path is correct and the identifier is exported (starts with uppercase in Go).",
    },
    "type_mismatch": {
        "title": "Type Mismatch / Interface Not Satisfied",
        "root_cause": "A value is being used where a different type is expected, or a struct does not implement an interface.",
        "commands": [],
        "explanation": "Check that all interface methods are implemented with the exact signatures. Use `var _ Interface = (*Struct)(nil)` to verify at compile time.",
    },
    "unused_variable": {
        "title": "Declared and Not Used",
        "root_cause": "Go requires all declared variables to be used.",
        "commands": [],
        "explanation": "Remove unused variables or replace them with `_` if the value must be discarded.",
    },
}


def _detect_pattern(error_output: str) -> str | None:
    for pattern, key, _ in _PATTERN_FIXES:
        if pattern.search(error_output):
            return key
    return None


def _fix_go_version_mismatch(
    error_output: str,
    files: list[dict[str, str]],
) -> CodeArtifact | None:
    """Return a corrected Dockerfile artifact with the Go version updated to match go.mod."""
    # Extract the required version from the error message
    required_match = re.search(
        r"go\.mod requires go\s*>=?\s*(\d+\.\d+)", error_output, re.IGNORECASE
    )
    if not required_match:
        required_match = re.search(r"requires go\s*>=?\s*(\d+\.\d+)", error_output, re.IGNORECASE)

    required_ver = required_match.group(1) if required_match else None

    # Find Dockerfile content from provided files
    dockerfile_content: str | None = None
    for f in files:
        if f.get("path", "").rstrip("/") in ("Dockerfile", "docker/Dockerfile"):
            dockerfile_content = f.get("content", "")
            break

    if not dockerfile_content and not required_ver:
        return None

    if not required_ver:
        # Extract from go.mod in files
        for f in files:
            if f.get("path", "") == "go.mod":
                m = re.search(r"^go\s+(\d+\.\d+)", f.get("content", ""), re.MULTILINE)
                if m:
                    required_ver = m.group(1)
                break

    if not required_ver or not dockerfile_content:
        return None

    # Replace the golang image version in the Dockerfile
    fixed = re.sub(
        r"(FROM\s+golang:)\d+\.\d+(-\S+)?",
        lambda m: f"{m.group(1)}{required_ver}{m.group(2) or ''}",
        dockerfile_content,
    )

    if fixed == dockerfile_content:
        return None

    return CodeArtifact(
        filename="Dockerfile",
        content=fixed,
        language="dockerfile",
        description=f"Updated FROM golang:{required_ver}-alpine to match go.mod requirement",
    )


def _build_command_report(pattern_key: str, error_output: str, module_name: str) -> str:
    fix = _COMMAND_FIXES.get(pattern_key, {})
    title = fix.get("title", pattern_key)
    root_cause = fix.get("root_cause", "")
    explanation = fix.get("explanation", "")
    commands = fix.get("commands", [])

    lines = [
        f"## Go Diagnostic Report — {title}",
        "",
        f"**Root cause:** {root_cause}",
        "",
    ]
    if module_name:
        lines += [f"**Module:** `{module_name}`", ""]

    if commands:
        lines += ["**Fix — run these commands from the project root:**", "```bash"]
        for cmd, desc in commands:
            lines.append(f"# {desc}")
            lines.append(cmd)
        lines += ["```", ""]

    if explanation:
        lines += ["**Explanation:**", explanation, ""]

    lines += [
        "**Error output captured:**",
        "```",
        error_output[:2000],
        "```",
    ]
    return "\n".join(lines)


def _fix_dockerfile_build_path(
    error_output: str,
    files: list[dict[str, str]],
) -> CodeArtifact | None:
    """Return a corrected Dockerfile with the go build entry point fixed."""
    dockerfile_content: str | None = None
    for f in files:
        if f.get("path", "").rstrip("/") in ("Dockerfile", "docker/Dockerfile"):
            dockerfile_content = f.get("content", "")
            break

    if not dockerfile_content:
        return None

    # Extract the wrong path from the error (e.g. "stat /app/cmd/server: directory not found")
    wrong_match = re.search(r"stat /app/(\S+?):\s*(?:directory )?not found", error_output)
    wrong_path = wrong_match.group(1).strip("/") if wrong_match else None

    # Determine the correct entry point:
    # 1. Check files list for Go files in cmd/
    # 2. Default to ./cmd (standard Go layout) — NEVER guess ./cmd/main
    go_cmd_files = [
        f.get("path", "") for f in files
        if f.get("path", "").startswith("cmd/") and f.get("path", "").endswith(".go")
    ]
    correct_path = "./cmd"  # Always default to ./cmd — the standard Go entry point

    if wrong_path:
        # Only fix if the wrong path differs from the correct path
        wrong_full = f"./{wrong_path}"
        if wrong_full == correct_path:
            return None  # Already correct
        fixed = dockerfile_content.replace(wrong_full, correct_path)
        # Also patch the go build line directly with a targeted regex
        fixed = re.sub(
            r"(go build\s[^\n]*?)\." + re.escape(wrong_path.lstrip("./")).replace("/", r"\/"),
            lambda m: m.group(1) + correct_path,
            fixed,
        )
    else:
        # Generic: replace any ./cmd/SUBDIR pattern with ./cmd
        fixed = re.sub(r"\./cmd/[\w/-]+", correct_path, dockerfile_content)

    if fixed == dockerfile_content:
        return None

    return CodeArtifact(
        filename="Dockerfile",
        content=fixed,
        language="dockerfile",
        description=f"Fixed go build entry point → {correct_path}",
    )


_SYSTEM_PROMPT = """\
You are a senior Go engineer specialized in debugging and fixing Go compile/runtime errors.

Given a build error and the source files involved, you will:
1. Identify the root cause of each error
2. Return ONLY the complete fixed source files — never a diff or partial snippet
3. Preserve all existing logic — only fix what is broken
4. If an import is unused, remove it; if missing, add it
5. Never add features or refactor code beyond what is needed to fix the error

Output ONLY a JSON object with this exact structure (no markdown, no explanation):
{"fixes": [{"path": "relative/path/file.go", "content": "full fixed file content"}]}
"""

_FALLBACK_REPORT = """\
## Go Diagnostic Report (LLM unavailable)

**Error output captured:**
```
{error_output}
```

**Affected files detected:**
{file_list}

**Common causes for Go startup/compile failures:**
- Unused imports → remove them
- Missing imports → add the package
- Type mismatch → check struct field types
- `undefined` variable/function → check package names and exported identifiers
- `cannot use X as type Y` → check interface implementation
- Missing `gorm.Model` fields → ensure entity embeds `gorm.Model`

Run `go build ./... 2>&1` locally to see the full error list.
"""


@SkillRegistry.register
class GoDiagnoseAndFixSkill(BaseSkill):
    """Analyzes Go build errors and returns fixed source files."""

    name = "diagnostic.go_diagnose"
    description = (
        "Analyze Go compile/build errors and return fixed source files. "
        "Receives the full `go build` stderr output and the content of affected files. "
        "Uses LLM to identify root causes and generate complete corrected files. "
        "Falls back to a structured analysis report when LLM is unavailable."
    )
    category = SkillCategory.DIAGNOSTIC
    tags = ["go", "diagnostic", "fix", "debug", "compile", "build", "error"]
    parameters = [
        SkillParameter("error_output", "Full output from `go build ./...` or `go run`"),
        SkillParameter(
            "source_files",
            'JSON array of affected files: [{"path": "...", "content": "..."}]. '
            "Include all files mentioned in the error output.",
        ),
        SkillParameter(
            "module_name",
            "Go module name from go.mod (e.g. github.com/org/service)",
            required=False,
            default="",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        error_output: str,
        source_files: str = "[]",
        module_name: str = "",
        **_: Any,
    ) -> SkillResult:
        try:
            files: list[dict[str, str]] = json.loads(source_files) if source_files else []
        except (json.JSONDecodeError, ValueError):
            files = []

        # Pattern-based fix: catches well-known error classes without LLM
        pattern_key = _detect_pattern(error_output)
        if pattern_key in _COMMAND_FIXES:
            return self._command_report(pattern_key, error_output, module_name, files)

        # LLM-based fix for unknown/complex errors
        if self.llm:
            return await self._llm_fix(error_output, files, module_name)

        return self._fallback_report(error_output, files)

    def _command_report(
        self,
        pattern_key: str,
        error_output: str,
        module_name: str,
        files: list[dict[str, str]] | None = None,
    ) -> SkillResult:
        fix = _COMMAND_FIXES[pattern_key]
        report = _build_command_report(pattern_key, error_output, module_name)
        commands = [cmd for cmd, _ in fix.get("commands", [])]
        artifacts: list[CodeArtifact] = [
            CodeArtifact(
                filename="diagnostic_report.md",
                content=report,
                language="markdown",
                description=fix["title"],
            )
        ]

        if pattern_key == "go_version_mismatch":
            fixed = _fix_go_version_mismatch(error_output, files or [])
            if fixed:
                artifacts.append(fixed)

        if pattern_key == "dockerfile_build_path":
            fixed = _fix_dockerfile_build_path(error_output, files or [])
            if fixed:
                artifacts.append(fixed)

        return SkillResult(
            success=True,
            summary=f"Diagnosed: {fix['title']}",
            artifacts=artifacts,
            instructions=commands or [fix.get("explanation", "Check the diagnostic report for details")],
        )

    async def _llm_fix(
        self,
        error_output: str,
        files: list[dict[str, str]],
        module_name: str,
    ) -> SkillResult:
        files_block = "\n\n".join(
            f"### {f['path']}\n```go\n{f['content']}\n```"
            for f in files
        )
        module_hint = f"\nModule: `{module_name}`" if module_name else ""
        prompt = (
            f"## Go Build Error{module_hint}\n\n"
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
                language="go",
                description=f"Fixed by diagnostic.go_diagnose",
            )
            for fix in fixes
        ]

        return SkillResult(
            success=True,
            summary=f"Fixed {len(artifacts)} Go file(s) — errors resolved by LLM analysis",
            artifacts=artifacts,
            instructions=[
                "Review each fixed file before committing",
                "Run `go build ./...` to confirm all errors are resolved",
                "Run `go test ./...` to ensure no regressions",
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
            summary="Go diagnostic report generated (configure HUGGINGFACE_TOKEN for auto-fix)",
            artifacts=[
                CodeArtifact(
                    filename="diagnostic_report.md",
                    content=report,
                    language="markdown",
                    description="Go build error analysis report",
                )
            ],
            instructions=[
                "Set HUGGINGFACE_TOKEN in .env to enable automatic code fixing",
                "Run `go build ./... 2>&1` to capture the full error list",
            ],
        )


def _parse_fixes(raw: str) -> list[dict[str, str]]:
    """Extract fixes list from LLM response, trying JSON then regex fallbacks."""
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()

    # Try direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "fixes" in data:
            return data["fixes"]
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting the first JSON object from the text
    match = re.search(r'\{.*"fixes"\s*:\s*\[.*\]\s*\}', cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return data.get("fixes", [])
        except (json.JSONDecodeError, ValueError):
            pass

    return []
