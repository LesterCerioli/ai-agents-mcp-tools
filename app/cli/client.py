import os
import pathlib
from typing import Any

import httpx

try:
    from app.cli._build_config import AGENTS_API_URL as _BAKED_URL
except ImportError:
    _BAKED_URL = ""

API_BASE_URL = os.getenv("AGENTS_API_URL", _BAKED_URL).rstrip("/")

if not API_BASE_URL:
    raise RuntimeError(
        "AGENTS_API_URL is not set. "
        "Set this environment variable before running the CLI."
    )

TIMEOUT = 120.0


class AgentsClient:
    def __init__(self, base_url: str = API_BASE_URL) -> None:
        self._base = base_url

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(f"{self._base}/health")
            r.raise_for_status()
            return r.json()

    def list_skills(self, agent: str | None = None) -> list[dict[str, Any]]:
        params = {"agent": agent} if agent else {}
        with httpx.Client(timeout=10.0) as c:
            r = c.get(f"{self._base}/skills", params=params)
            r.raise_for_status()
            return r.json().get("skills", [])

    def execute_skill(self, agent: str, skill: str, params: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(
                f"{self._base}/skills/execute",
                json={"agent": agent, "skill": skill, "params": params},
            )
            r.raise_for_status()
            return r.json()

    def generate(
        self,
        objective: str,
        project_name: str,
        language: str = "go",
        framework: str = "fiber",
        scope: str = "backend",
    ) -> dict[str, Any]:
        # output_dir is always /tmp on the server — the CLI writes files locally
        # from the artifacts returned in the response
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(
                f"{self._base}/workflow/scaffold",
                json={
                    "objective": objective,
                    "project_name": project_name,
                    "output_dir": "/tmp",
                    "scope": scope,
                    "backend_language": language,
                    "backend_framework": framework,
                },
            )
            r.raise_for_status()
            return r.json()

    def improve(
        self,
        instruction: str,
        project_context: dict[str, Any],
    ) -> dict[str, Any]:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(
                f"{self._base}/workflow/improve",
                json={
                    "instruction": instruction,
                    "project_files": project_context.get("files", []),
                    "project_type": project_context.get("project_type", "unknown"),
                },
            )
            r.raise_for_status()
            return r.json()

    def route_intent(
        self,
        query: str,
        project_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(
                f"{self._base}/workflow/ask",
                json={"query": query, "project_context": project_context or {}},
            )
            r.raise_for_status()
            return r.json()

    def cli_version(self) -> dict[str, Any]:
        """Latest CLI version published by the API currently deployed."""
        with httpx.Client(timeout=5.0) as c:
            r = c.get(f"{self._base}/cli/version")
            r.raise_for_status()
            return r.json()

    def download_cli_binary(self, dest_path: pathlib.Path, target_os: str = "linux") -> None:
        """Stream the latest CLI binary for `target_os` ('linux' or 'windows') to dest_path."""
        with httpx.stream("GET", f"{self._base}/cli/download/{target_os}", timeout=180.0, follow_redirects=True) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def diagnose(
        self,
        language: str,
        error_output: str,
        source_files: list[dict[str, str]],
        module_name: str = "",
        version: str = "",
    ) -> dict[str, Any]:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.post(
                f"{self._base}/workflow/diagnose",
                json={
                    "language": language,
                    "error_output": error_output,
                    "source_files": source_files,
                    "module_name": module_name,
                    "version": version,
                },
            )
            r.raise_for_status()
            return r.json()
