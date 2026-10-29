"""Online demo settings: the config route and the refused upload."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from tests.builders import CONTRACT_TEXT, make_pdf


def test_demo_settings_are_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Locally, uploads are allowed and Vite or Nginx serves the frontend."""
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("STATIC_DIR", raising=False)

    settings = Settings(_env_file=None)

    assert settings.demo_mode is False
    assert settings.static_dir is None


def test_config_route_without_demo_mode(client: TestClient) -> None:
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {"demo_mode": False, "llm_provider": "ollama"}


def test_config_route_in_the_online_demo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_API_KEY", "secret-value")
    get_settings.cache_clear()

    response = client.get("/api/config")

    assert response.json() == {"demo_mode": True, "llm_provider": "openai_compatible"}
    # Only these two fields: never a URL or a key.
    assert "secret-value" not in response.text


def test_upload_is_refused_in_the_online_demo(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, data_dir: Path
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    pdf = make_pdf(tmp_path / "contract.pdf", [CONTRACT_TEXT])

    with pdf.open("rb") as file:
        response = client.post("/api/documents", files={"file": ("contract.pdf", file)})

    assert response.status_code == 403
    assert response.json() == {"detail": "Uploads are disabled in the online demo."}
    # Nothing is stored: no document, no file.
    assert client.get("/api/documents").json() == []
    assert not (data_dir / "uploads").exists() or not any((data_dir / "uploads").iterdir())