from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

STATIC_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


def mount_dashboard(app: FastAPI, static_dir: str | Path) -> None:
    static_path = Path(static_dir)
    index_path = static_path / "index.html"

    if not index_path.is_file():
        return

    assets_path = static_path / "assets"
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_path), name="dashboard-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{path:path}", include_in_schema=False)
    def dashboard(path: str = "") -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        requested_path = (static_path / path).resolve()
        static_root = static_path.resolve()
        if requested_path.is_file() and requested_path.is_relative_to(static_root):
            return FileResponse(requested_path, headers=STATIC_HEADERS)

        return FileResponse(index_path, headers=STATIC_HEADERS)
