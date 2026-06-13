from pathlib import Path
from typing import Any

_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", ".venv", "env",
    "dist", "build", ".next", ".pytest_cache", ".mypy_cache", ".tox",
    "coverage", ".coverage", "htmlcov",
}
_SKIP_SUFFIXES = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".avi",
    ".zip", ".tar", ".gz", ".bz2", ".rar",
    ".lock",
}
_MAX_FILE_BYTES = 10_000
_MAX_TOTAL_BYTES = 150_000


def scan_project(path: str) -> dict[str, Any]:
    root = Path(path).resolve()
    files: list[dict[str, Any]] = []
    total_bytes = 0

    for filepath in sorted(root.rglob("*")):
        if not filepath.is_file():
            continue

        rel = filepath.relative_to(root)

        if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue

        if filepath.suffix.lower() in _SKIP_SUFFIXES:
            continue

        if ".egg-info" in str(rel):
            continue

        rel_str = str(rel)

        try:
            size = filepath.stat().st_size
        except OSError:
            continue

        if size > _MAX_FILE_BYTES or total_bytes + size > _MAX_TOTAL_BYTES:
            files.append({"path": rel_str, "content": None, "truncated": True})
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            files.append({"path": rel_str, "content": None, "truncated": True})
            continue

        files.append({"path": rel_str, "content": content, "truncated": False})
        total_bytes += size

    return {
        "root": str(root),
        "files": files,
        "file_count": len(files),
        "project_type": _detect_project_type(files),
    }


def _detect_project_type(files: list[dict[str, Any]]) -> str:
    paths = {f["path"] for f in files}

    if "go.mod" in paths:
        return "go"

    if "package.json" in paths:
        for f in files:
            if f["path"] == "package.json" and f.get("content"):
                if '"next"' in f["content"]:
                    return "nextjs"
        return "node"

    if "requirements.txt" in paths or "pyproject.toml" in paths:
        return "python"

    if "Cargo.toml" in paths:
        return "rust"

    return "unknown"
