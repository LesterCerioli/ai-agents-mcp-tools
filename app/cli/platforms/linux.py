import os
import pathlib
import stat
from typing import Any


class LinuxPlatformAgent:
    """Handles file writing and path resolution on Linux."""

    def resolve_output_path(self, output_dir: str | None, project_name: str) -> pathlib.Path:
        base = pathlib.Path(output_dir).expanduser().resolve() if output_dir else pathlib.Path.cwd()
        return base / project_name

    def write_artifacts(self, artifacts: list[dict[str, Any]], output_path: pathlib.Path) -> list[str]:
        written: list[str] = []
        seen: set[str] = set()

        for artifact in artifacts:
            filename = artifact.get("filename", "")
            content = artifact.get("content", "")
            if not filename or filename in seen:
                continue
            seen.add(filename)

            dest = output_path / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

            # make shell scripts executable
            if filename.endswith(".sh"):
                dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            written.append(filename)

        return written

    def current_dir(self) -> pathlib.Path:
        return pathlib.Path(os.getcwd()).resolve()
