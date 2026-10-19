"""Tests for the database layer: tables, repository and application startup."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentStatus, Page
from app.db.repositories import MAX_ERROR_LENGTH, DocumentRepository
from app.db.session import DATABASE_FILENAME
from app.ingestion.models import PageText
from app.main import app

PAGES = [
    PageText(page_number=1, text="First page text."),
    PageText(page_number=2, text="Scanned page text.", ocr_used=True),
]


def test_create_registers_an_uploaded_document(db_session: Session) -> None:
    """A new document gets an id, the "uploaded" status and a UTC timestamp."""
    repository = DocumentRepository(db_session)

    document = repository.create("contract.pdf", "application/pdf")

    assert len(document.id) == 36
    assert document.status == DocumentStatus.UPLOADED
    assert document.page_count == 0
    assert document.ocr_used is False
    assert document.error is None
    assert document.created_at.tzinfo is not None


def test_status_is_stored_as_readable_text(db_session: Session) -> None:
    """The status column contains "uploaded", not an internal enum name."""
    DocumentRepository(db_session).create("a.pdf", "application/pdf")

    raw_status = db_session.connection().exec_driver_sql(
        "SELECT status FROM documents"
    ).scalar_one()

    assert raw_status == "uploaded"


def test_created_at_stays_timezone_aware_after_reload(db_session: Session) -> None:
    """Dates read back from SQLite are still marked as UTC."""
    document = DocumentRepository(db_session).create("a.pdf", "application/pdf")
    db_session.expire_all()

    reloaded = db_session.get(Document, document.id)

    assert reloaded is not None
    assert reloaded.created_at.tzinfo == UTC


def test_get_returns_none_for_unknown_id(db_session: Session) -> None:
    """An unknown id gives None instead of raising."""
    assert DocumentRepository(db_session).get("does-not-exist") is None


def test_list_all_returns_newest_first(db_session: Session) -> None:
    """The document list is sorted from newest to oldest."""
    repository = DocumentRepository(db_session)
    older = repository.create("older.pdf", "application/pdf")
    newer = repository.create("newer.pdf", "application/pdf")
    older.created_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    documents = repository.list_all()

    assert [document.id for document in documents] == [newer.id, older.id]


def test_mark_ready_stores_pages_in_order(db_session: Session) -> None:
    """Pages are saved with their text and the document summary is updated."""
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    repository.mark_processing(document)

    repository.mark_ready(document, list(reversed(PAGES)))

    assert document.status == DocumentStatus.READY
    assert document.page_count == 2
    assert document.ocr_used is True
    pages = repository.list_pages(document.id)
    assert [(page.page_number, page.text, page.ocr_used) for page in pages] == [
        (1, "First page text.", False),
        (2, "Scanned page text.", True),
    ]


def test_mark_ready_twice_replaces_previous_pages(db_session: Session) -> None:
    """Processing a document again replaces its pages instead of duplicating them."""
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    repository.mark_ready(document, PAGES)

    repository.mark_ready(document, [PageText(page_number=1, text="New text.")])

    pages = repository.list_pages(document.id)
    assert [(page.page_number, page.text) for page in pages] == [(1, "New text.")]
    assert document.page_count == 1
    assert document.ocr_used is False


def test_mark_failed_records_error_and_removes_pages(db_session: Session) -> None:
    """A failure keeps a readable message, truncated to a safe length."""
    repository = DocumentRepository(db_session)
    document = repository.create("broken.pdf", "application/pdf")
    repository.mark_ready(document, PAGES)

    repository.mark_failed(document, "x" * (MAX_ERROR_LENGTH + 500))

    assert document.status == DocumentStatus.FAILED
    assert document.error is not None
    assert len(document.error) == MAX_ERROR_LENGTH
    assert document.page_count == 0
    assert repository.list_pages(document.id) == []


def test_deleting_a_document_deletes_its_pages(db_session: Session) -> None:
    """Pages never outlive their document."""
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    repository.mark_ready(document, PAGES)

    db_session.delete(document)
    db_session.commit()

    assert db_session.scalars(select(Page)).all() == []


def test_foreign_keys_are_enforced(db_session: Session) -> None:
    """SQLite rejects a page that points to a missing document."""
    db_session.add(Page(document_id="missing", page_number=1, text="orphan"))

    with pytest.raises(Exception, match="FOREIGN KEY"):
        db_session.commit()


def test_app_startup_creates_the_database(data_dir: Path) -> None:
    """Starting the application creates the data folder and the SQLite file."""
    # Using the client as a context manager runs the startup code.
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    assert (data_dir / DATABASE_FILENAME).is_file()