import os
import pathlib
from typing import Any


class WindowsPlatformAgent:
    """Handles file writing and path resolution on Windows."""

    def resolve_output_path(self, output_dir: str | None, project_name: str) -> pathlib.Path:
        if output_dir:
            base = pathlib.Path(output_dir).expanduser().resolve()
        else:
            # default to current directory on Windows
            base = pathlib.Path(os.getcwd()).resolve()
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

            # normalise separators for Windows
            filename_win = filename.replace("/", os.sep)
            dest = output_path / pathlib.Path(filename_win)
            dest.parent.mkdir(parents=True, exist_ok=True)

            # write with Windows line endings for non-binary files
            dest.write_text(content, encoding="utf-8", newline="\r\n")
            written.append(filename)

        return written

    def current_dir(self) -> pathlib.Path:
        return pathlib.Path(os.getcwd()).resolve()
