"""Shared pytest fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url
from app.main import app


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A session on a fresh SQLite database, deleted after the test."""
    engine = create_db_engine(sqlite_url(tmp_path))
    init_db(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point DATA_DIR to a temporary folder for the duration of the test."""
    folder = tmp_path / "atlas-data"
    monkeypatch.setenv("DATA_DIR", str(folder))
    get_settings.cache_clear()
    yield folder
    get_settings.cache_clear()


@pytest.fixture
def client(data_dir: Path) -> Iterator[TestClient]:
    """An API client on a fresh database. The startup code runs normally."""
    with TestClient(app) as test_client:
        yield test_client