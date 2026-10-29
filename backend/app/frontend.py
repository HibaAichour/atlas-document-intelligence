"""Serve the compiled frontend from FastAPI, for the single-container deployment."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


class FrontendNotBuiltError(RuntimeError):
    """STATIC_DIR is set but holds no compiled frontend."""


def mount_frontend(app: FastAPI, static_dir: Path | None) -> bool:
    """Serve the files of static_dir on "/" (index.html for "/"), after the API routes.

    Does nothing when static_dir is None (development, Docker Compose).
    Must be called after the API routes are included: the routes declared
    first are matched first, so /api/... never reaches the static files.

    Raises:
        FrontendNotBuiltError: If static_dir has no index.html (a wrong path
            would otherwise start a server that answers 404 on "/").
    """
    if static_dir is None:
        return False
    if not (static_dir / "index.html").is_file():
        raise FrontendNotBuiltError(f"No index.html in STATIC_DIR ({static_dir})")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return True