"""Database engine and session factory."""

from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

DATABASE_FILENAME = "atlas.db"


def sqlite_url(data_dir: Path) -> str:
    """Return the URL of the SQLite file inside data_dir, creating the folder if needed."""
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / DATABASE_FILENAME}"


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    """Turn on foreign key checks, which SQLite disables by default.

    Without this, deleting a document would leave its pages behind.
    """
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_db_engine(database_url: str) -> Engine:
    """Create the engine for the given database URL."""
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        # FastAPI runs sync routes in a thread pool, so a connection may be
        # used by a thread other than the one that opened it.
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args)
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def init_db(engine: Engine) -> None:
    """Create the missing tables. Existing tables and data are left untouched."""
    Base.metadata.create_all(engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a factory of sessions bound to the engine.

    expire_on_commit=False keeps objects readable after a commit (for example
    to return them in an API response) without reloading them from the database.
    """
    return sessionmaker(engine, expire_on_commit=False)