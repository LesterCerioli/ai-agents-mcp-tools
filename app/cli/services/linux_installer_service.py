import pathlib

from fastapi import HTTPException
from fastapi.responses import FileResponse

DIST_DIR = pathlib.Path(__file__).parent.parent / "dist"
LINUX_BINARY = DIST_DIR / "agents-linux"


class LinuxInstallerService:
    """Serviço de download Linux — agora Grok-aware no cabeçalho.

    O binário CLI continua o mesmo (agents-linux), mas o servidor que o serve
    agora força Grok (GROCK_API_TOKEN) + Skills. Headers expõem a versão e
    que Grok está forçado, sem nunca expor o valor do token.
    """

    def download(self) -> FileResponse:
        if not LINUX_BINARY.exists():
            raise HTTPException(
                status_code=404,
                detail="Linux installer not available yet. Please check back soon.",
            )
        from app.cli._version import CLI_VERSION

        return FileResponse(
            path=str(LINUX_BINARY),
            media_type="application/octet-stream",
            filename="agents",
            headers={
                "Content-Disposition": "attachment; filename=agents",
                "X-Agents-Version": CLI_VERSION,
                "X-Agents-Provider": "grok",
                "X-Agents-Grok-Forced": "true",
            },
        )

    def is_available(self) -> bool:
        return LINUX_BINARY.exists()

    def status(self) -> dict:
        """Status estendido para /cli/status."""
        from app.cli._version import CLI_VERSION
        import os

        has_grok = bool(os.getenv("GROCK_API_TOKEN") or os.getenv("GROK_API_TOKEN") or os.getenv("XAI_API_KEY"))
        return {
            "available": self.is_available(),
            "version": CLI_VERSION,
            "provider": "grok" if has_grok else "huggingface",
            "grok_forced": has_grok,
        }
