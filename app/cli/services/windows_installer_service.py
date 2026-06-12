import pathlib

from fastapi import HTTPException
from fastapi.responses import FileResponse

DIST_DIR = pathlib.Path(__file__).parent.parent / "dist"
WINDOWS_BINARY = DIST_DIR / "agents-windows.exe"


class WindowsInstallerService:
    def download(self) -> FileResponse:
        if not WINDOWS_BINARY.exists():
            raise HTTPException(
                status_code=404,
                detail="Windows installer not available yet. Please check back soon.",
            )
        return FileResponse(
            path=str(WINDOWS_BINARY),
            media_type="application/octet-stream",
            filename="agents.exe",
            headers={"Content-Disposition": "attachment; filename=agents.exe"},
        )

    def is_available(self) -> bool:
        return WINDOWS_BINARY.exists()
