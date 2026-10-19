"""Shared pytest fixtures."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A session on a fresh SQLite database, deleted after the test."""
    engine = create_db_engine(sqlite_url(tmp_path))
    init_db(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
    engine.dispose()