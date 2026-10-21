"""Startup adds the new optional columns to an existing database, data kept."""

from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, inspect

from app.db.repositories import AssistantReply, SessionRepository
from app.db.session import (
    SchemaUpgradeError,
    add_missing_columns,
    create_db_engine,
    create_session_factory,
    init_db,
    sqlite_url,
)

ANSWER = AssistantReply(content="It is 60 days [contract.pdf, p. 4].", status="answered")


def message_columns(engine) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns("messages")}


def test_a_database_from_step_8_gets_the_review_and_extraction_columns(tmp_path: Path) -> None:
    """The columns added at step 9 appear at startup; saved messages are kept."""
    engine = create_db_engine(sqlite_url(tmp_path))
    init_db(engine)
    with create_session_factory(engine)() as db:
        repository = SessionRepository(db)
        chat_session = repository.create()
        repository.add_exchange(chat_session, question="Notice?", document_ids=[], reply=ANSWER)
        session_id = chat_session.id
    # Make the database look like step 8: without the two new columns.
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE messages DROP COLUMN review")
        connection.exec_driver_sql("ALTER TABLE messages DROP COLUMN extraction")
    assert {"review", "extraction"}.isdisjoint(message_columns(engine))

    init_db(engine)

    assert {"review", "extraction"} <= message_columns(engine)
    with create_session_factory(engine)() as db:
        messages = SessionRepository(db).list_messages(session_id)
        assert [message.content for message in messages] == ["Notice?", ANSWER.content]
        assert messages[1].review is None
        assert messages[1].extraction is None
    engine.dispose()


def test_an_up_to_date_database_is_left_unchanged(tmp_path: Path) -> None:
    engine = create_db_engine(sqlite_url(tmp_path))
    init_db(engine)

    assert add_missing_columns(engine) == []
    engine.dispose()


def test_only_the_missing_columns_are_reported(tmp_path: Path) -> None:
    engine = create_db_engine(sqlite_url(tmp_path))
    init_db(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE messages DROP COLUMN extraction")

    assert add_missing_columns(engine) == ["messages.extraction"]
    engine.dispose()


def test_a_required_column_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    """A NOT NULL column would need a value for existing rows: no silent guess."""
    engine = create_db_engine(sqlite_url(tmp_path))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE notes (id INTEGER PRIMARY KEY)")
    metadata = MetaData()
    Table(
        "notes",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String(50), nullable=False),
    )

    with pytest.raises(SchemaUpgradeError, match=r"notes\.title is required"):
        add_missing_columns(engine, metadata)
    engine.dispose()