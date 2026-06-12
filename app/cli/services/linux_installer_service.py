import pathlib

from fastapi import HTTPException
from fastapi.responses import FileResponse

DIST_DIR = pathlib.Path(__file__).parent.parent / "dist"
LINUX_BINARY = DIST_DIR / "agents-linux"


class LinuxInstallerService:
    def download(self) -> FileResponse:
        if not LINUX_BINARY.exists():
            raise HTTPException(
                status_code=404,
                detail="Linux installer not available yet. Please check back soon.",
            )
        return FileResponse(
            path=str(LINUX_BINARY),
            media_type="application/octet-stream",
            filename="agents",
            headers={"Content-Disposition": "attachment; filename=agents"},
        )

    def is_available(self) -> bool:
        return LINUX_BINARY.exists()
