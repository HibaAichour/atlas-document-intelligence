"""The compiled frontend served by FastAPI (single-container deployment)."""

from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.frontend import FrontendNotBuiltError, mount_frontend


def build(folder: Path) -> Path:
    """A minimal compiled frontend: index.html and one asset."""
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text("<!doctype html><title>ATLAS</title>", encoding="utf-8")
    (folder / "assets" / "app.js").write_text("console.log('atlas')", encoding="utf-8")
    return folder


def app_with_api() -> FastAPI:
    app = FastAPI()
    router = APIRouter(prefix="/api")

    @router.get("/ping")
    def ping() -> dict[str, str]:
        return {"pong": "yes"}

    app.include_router(router)
    return app


def test_frontend_is_served_after_the_api(tmp_path: Path) -> None:
    app = app_with_api()
    assert mount_frontend(app, build(tmp_path / "dist")) is True
    client = TestClient(app)

    page = client.get("/")
    assert page.status_code == 200
    assert "<title>ATLAS</title>" in page.text
    assert page.headers["content-type"].startswith("text/html")

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "atlas" in asset.text

    # The API routes, declared first, are still reached.
    assert client.get("/api/ping").json() == {"pong": "yes"}
    assert client.get("/missing.js").status_code == 404


def test_nothing_is_mounted_without_static_dir() -> None:
    app = app_with_api()

    assert mount_frontend(app, None) is False
    assert TestClient(app).get("/").status_code == 404


def test_a_folder_without_index_html_is_an_error(tmp_path: Path) -> None:
    """A wrong STATIC_DIR stops the server instead of answering 404 on "/"."""
    with pytest.raises(FrontendNotBuiltError, match="No index.html"):
        mount_frontend(app_with_api(), tmp_path)