"""Database engine and session factory."""

from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine, event, inspect
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


class SchemaUpgradeError(RuntimeError):
    """An existing table lacks a column that cannot be added automatically."""


def add_missing_columns(engine: Engine, metadata: MetaData = Base.metadata) -> list[str]:
    """Add to existing tables the columns the models declare but the tables lack.

    create_all creates missing tables but never changes an existing one. This
    covers the only change V1 needs: a new optional (nullable) column, added
    empty with ALTER TABLE, existing rows kept. Any other change (a required
    column) raises, rather than guessing a value for the existing rows.
    Returns the added columns, as "table.column".
    """
    inspector = inspect(engine)
    added: list[str] = []
    with engine.begin() as connection:
        for table in metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  # created by create_all, with every column
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                if not column.nullable or column.primary_key:
                    raise SchemaUpgradeError(
                        f"Column {table.name}.{column.name} is required and cannot be added "
                        "to an existing database: recreate the database."
                    )
                column_type = column.type.compile(dialect=engine.dialect)
                connection.exec_driver_sql(
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'
                )
                added.append(f"{table.name}.{column.name}")
    return added


def init_db(engine: Engine) -> None:
    """Create the missing tables, then add the missing optional columns.

    Existing tables and data are kept.
    """
    Base.metadata.create_all(engine)
    add_missing_columns(engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a factory of sessions bound to the engine.

    expire_on_commit=False keeps objects readable after a commit (for example
    to return them in an API response) without reloading them from the database.
    """
    return sessionmaker(engine, expire_on_commit=False)