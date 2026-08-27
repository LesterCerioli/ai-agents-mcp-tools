import pathlib

from fastapi import HTTPException
from fastapi.responses import FileResponse

DIST_DIR = pathlib.Path(__file__).parent.parent / "dist"
WINDOWS_BINARY = DIST_DIR / "agents-windows.exe"


class WindowsInstallerService:
    """Serviço de download Windows — Grok-aware."""

    def download(self) -> FileResponse:
        if not WINDOWS_BINARY.exists():
            raise HTTPException(
                status_code=404,
                detail="Windows installer not available yet. Please check back soon.",
            )
        from app.cli._version import CLI_VERSION

        return FileResponse(
            path=str(WINDOWS_BINARY),
            media_type="application/octet-stream",
            filename="agents.exe",
            headers={
                "Content-Disposition": "attachment; filename=agents.exe",
                "X-Agents-Version": CLI_VERSION,
                "X-Agents-Provider": "grok",
                "X-Agents-Grok-Forced": "true",
            },
        )

    def is_available(self) -> bool:
        return WINDOWS_BINARY.exists()

    def status(self) -> dict:
        from app.cli._version import CLI_VERSION
        import os

        has_grok = bool(os.getenv("GROCK_API_TOKEN") or os.getenv("GROK_API_TOKEN") or os.getenv("XAI_API_KEY"))
        return {
            "available": self.is_available(),
            "version": CLI_VERSION,
            "provider": "grok" if has_grok else "huggingface",
            "grok_forced": has_grok,
        }
