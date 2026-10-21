"""Tests for storing sessions, their messages and their documents in SQLite."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    ChatSession,
    Message,
    MessageMode,
    MessageRole,
    SessionDocument,
)
from app.db.repositories import (
    MAX_TITLE_LENGTH,
    AssistantReply,
    DocumentRepository,
    SessionRepository,
    make_session_title,
)
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url

SOURCE = {
    "label": "S1",
    "display": "[contract.pdf, p. 4]",
    "chunk_id": "chunk-1",
    "document_id": "doc-1",
    "filename": "contract.pdf",
    "page_number": 4,
    "position": 0,
    "text": "Either party may terminate with sixty (60) days' written notice.",
    "score": 0.71,
}

ANSWER = AssistantReply(
    content="The notice period is 60 days [contract.pdf, p. 4].",
    status="answered",
    sources=[SOURCE],
    best_score=0.71,
)

REFUSAL = AssistantReply(
    content="The documents do not contain this information.",
    status="refused",
    refusal_reason="no_relevant_passages",
    best_score=0.54,
)


def count_rows(session: Session, table: type) -> int:
    return session.scalar(select(func.count()).select_from(table)) or 0


def test_create_registers_an_empty_session(db_session: Session) -> None:
    """A new session has an id, no title yet and UTC timestamps."""
    chat_session = SessionRepository(db_session).create()

    assert len(chat_session.id) == 36
    assert chat_session.title is None
    assert chat_session.created_at.tzinfo is not None
    assert chat_session.updated_at.tzinfo is not None
    assert chat_session.messages == []


def test_get_returns_none_for_unknown_id(db_session: Session) -> None:
    """An unknown id gives None instead of raising."""
    assert SessionRepository(db_session).get("does-not-exist") is None


def test_add_exchange_saves_question_and_answer_in_order(db_session: Session) -> None:
    """The question comes first, then its answer with every answer detail."""
    repository = SessionRepository(db_session)
    chat_session = repository.create()

    question, answer = repository.add_exchange(
        chat_session, question="What is the notice period?", document_ids=[], reply=ANSWER
    )

    messages = repository.list_messages(chat_session.id)
    assert [message.id for message in messages] == [question.id, answer.id]
    assert [(m.position, m.role, m.mode) for m in messages] == [
        (0, MessageRole.USER, MessageMode.ASK),
        (1, MessageRole.ASSISTANT, MessageMode.ASK),
    ]
    assert question.content == "What is the notice period?"
    assert question.status is None
    assert question.sources == []
    assert answer.content == ANSWER.content
    assert answer.status == "answered"
    assert answer.refusal_reason is None
    assert answer.best_score == 0.71
    assert answer.agent_trace == []


def test_sources_survive_a_reload_from_the_database(db_session: Session) -> None:
    """The full copy of each source (text, file, page) is read back unchanged."""
    repository = SessionRepository(db_session)
    chat_session = repository.create()
    _, answer = repository.add_exchange(
        chat_session, question="Notice period?", document_ids=[], reply=ANSWER
    )
    db_session.expire_all()

    reloaded = db_session.get(Message, answer.id)

    assert reloaded is not None
    assert reloaded.sources == [SOURCE]
    assert reloaded.created_at.tzinfo == UTC


def test_a_refusal_keeps_its_reason(db_session: Session) -> None:
    """A refused answer is saved with the reason the frontend needs."""
    repository = SessionRepository(db_session)
    chat_session = repository.create()

    _, answer = repository.add_exchange(
        chat_session, question="What is the CEO's salary?", document_ids=[], reply=REFUSAL
    )

    assert answer.status == "refused"
    assert answer.refusal_reason == "no_relevant_passages"
    assert answer.sources == []


def test_roles_are_stored_as_readable_text(db_session: Session) -> None:
    """The role and mode columns contain "user" and "ask", not enum names."""
    repository = SessionRepository(db_session)
    repository.add_exchange(repository.create(), question="Q?", document_ids=[], reply=ANSWER)

    rows = db_session.connection().exec_driver_sql(
        "SELECT role, mode FROM messages ORDER BY position"
    ).all()

    assert [tuple(row) for row in rows] == [("user", "ask"), ("assistant", "ask")]


def test_later_exchanges_continue_the_numbering(db_session: Session) -> None:
    """A second question gets positions 2 and 3."""
    repository = SessionRepository(db_session)
    chat_session = repository.create()
    repository.add_exchange(chat_session, question="First?", document_ids=[], reply=ANSWER)

    repository.add_exchange(chat_session, question="Second?", document_ids=[], reply=REFUSAL)

    messages = repository.list_messages(chat_session.id)
    assert [message.position for message in messages] == [0, 1, 2, 3]
    assert messages[2].content == "Second?"


def test_the_first_question_becomes_the_title(db_session: Session) -> None:
    """The title comes from the first question and never changes afterwards."""
    repository = SessionRepository(db_session)
    chat_session = repository.create()

    repository.add_exchange(
        chat_session, question="  What is the\nnotice period?  ", document_ids=[], reply=ANSWER
    )
    repository.add_exchange(chat_session, question="Another one?", document_ids=[], reply=ANSWER)

    assert chat_session.title == "What is the notice period?"


def test_add_exchange_moves_updated_at_forward(db_session: Session) -> None:
    """Using a session marks it as recently used."""
    repository = SessionRepository(db_session)
    chat_session = repository.create()
    an_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    chat_session.updated_at = an_hour_ago
    db_session.commit()

    repository.add_exchange(chat_session, question="Q?", document_ids=[], reply=ANSWER)

    assert chat_session.updated_at > an_hour_ago


def test_add_exchange_replaces_the_selected_documents(db_session: Session) -> None:
    """The session keeps the documents of its latest question."""
    documents = DocumentRepository(db_session)
    contract = documents.create("contract.pdf", "application/pdf")
    invoice = documents.create("invoice.png", "image/png")
    repository = SessionRepository(db_session)
    chat_session = repository.create()
    repository.add_exchange(
        chat_session, question="Q1?", document_ids=[contract.id, invoice.id], reply=ANSWER
    )

    repository.add_exchange(chat_session, question="Q2?", document_ids=[invoice.id], reply=ANSWER)

    assert repository.document_ids(chat_session.id) == [invoice.id]


def test_unknown_and_duplicate_document_ids_are_ignored(db_session: Session) -> None:
    """An id that matches no document is skipped instead of breaking the save."""
    contract = DocumentRepository(db_session).create("contract.pdf", "application/pdf")
    repository = SessionRepository(db_session)
    chat_session = repository.create()

    repository.add_exchange(
        chat_session,
        question="Q?",
        document_ids=[contract.id, "missing-id", contract.id],
        reply=ANSWER,
    )

    assert repository.document_ids(chat_session.id) == [contract.id]
    assert count_rows(db_session, Message) == 2


def test_list_all_returns_most_recently_used_first(db_session: Session) -> None:
    """The session list is sorted by last use and counts the messages."""
    repository = SessionRepository(db_session)
    older = repository.create()
    newer = repository.create()
    empty = repository.create()
    repository.add_exchange(older, question="Old?", document_ids=[], reply=ANSWER)
    repository.add_exchange(newer, question="New?", document_ids=[], reply=ANSWER)
    repository.add_exchange(newer, question="New again?", document_ids=[], reply=ANSWER)
    empty.updated_at = datetime.now(UTC) - timedelta(days=1)
    older.updated_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    summaries = repository.list_all()

    assert [(s.session.id, s.message_count) for s in summaries] == [
        (newer.id, 4),
        (older.id, 2),
        (empty.id, 0),
    ]


def test_list_all_with_no_session_returns_an_empty_list(db_session: Session) -> None:
    assert SessionRepository(db_session).list_all() == []


def test_list_messages_does_not_mix_sessions(db_session: Session) -> None:
    repository = SessionRepository(db_session)
    first = repository.create()
    second = repository.create()
    repository.add_exchange(first, question="First?", document_ids=[], reply=ANSWER)
    repository.add_exchange(second, question="Second?", document_ids=[], reply=ANSWER)

    messages = repository.list_messages(second.id)

    assert [message.content for message in messages] == ["Second?", ANSWER.content]


def test_deleting_a_session_deletes_its_messages_and_links(db_session: Session) -> None:
    """Messages and document links never outlive their session; documents stay."""
    contract = DocumentRepository(db_session).create("contract.pdf", "application/pdf")
    repository = SessionRepository(db_session)
    chat_session = repository.create()
    repository.add_exchange(chat_session, question="Q?", document_ids=[contract.id], reply=ANSWER)

    db_session.delete(chat_session)
    db_session.commit()

    assert count_rows(db_session, Message) == 0
    assert count_rows(db_session, SessionDocument) == 0
    assert DocumentRepository(db_session).get(contract.id) is not None


def test_deleting_a_document_removes_it_from_sessions(db_session: Session) -> None:
    """A deleted document disappears from the session, its messages stay."""
    documents = DocumentRepository(db_session)
    contract = documents.create("contract.pdf", "application/pdf")
    repository = SessionRepository(db_session)
    chat_session = repository.create()
    repository.add_exchange(chat_session, question="Q?", document_ids=[contract.id], reply=ANSWER)

    db_session.delete(contract)
    db_session.commit()

    assert repository.document_ids(chat_session.id) == []
    assert count_rows(db_session, Message) == 2
    assert count_rows(db_session, ChatSession) == 1


def test_short_title_is_kept_as_is() -> None:
    assert make_session_title("What is the notice period?") == "What is the notice period?"


def test_title_collapses_spaces_and_line_breaks() -> None:
    assert make_session_title("  Notice\n\tperiod   please ") == "Notice period please"


def test_long_title_is_cut_on_a_whole_word() -> None:
    """A long question is cut before a word, never in the middle of it."""
    question = "Please summarise every obligation of the service provider regarding data protection"

    title = make_session_title(question)

    assert len(title) <= MAX_TITLE_LENGTH
    assert title.endswith("…")
    assert question.startswith(title.removesuffix("…"))
    assert title.removesuffix("…").split()[-1] in question.split()


def test_one_very_long_word_is_cut_anyway() -> None:
    title = make_session_title("x" * 200)

    assert title == "x" * (MAX_TITLE_LENGTH - 1) + "…"


def test_an_existing_database_gains_the_session_tables(tmp_path: Path) -> None:
    """A database from step 7 (no session tables) gets them at startup, data kept."""
    engine = create_db_engine(sqlite_url(tmp_path))
    old_tables = [Base.metadata.tables[name] for name in ("documents", "pages", "chunks")]
    Base.metadata.create_all(engine, tables=old_tables)
    with create_session_factory(engine)() as session:
        DocumentRepository(session).create("contract.pdf", "application/pdf")

    init_db(engine)

    assert {"sessions", "messages", "session_documents"} <= set(inspect(engine).get_table_names())
    with create_session_factory(engine)() as session:
        assert [d.filename for d in DocumentRepository(session).list_all()] == ["contract.pdf"]
    engine.dispose()