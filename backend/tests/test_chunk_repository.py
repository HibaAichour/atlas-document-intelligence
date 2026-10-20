"""Tests for storing and reading chunks in SQLite."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, DocumentStatus
from app.db.repositories import DocumentRepository
from app.ingestion.chunking import TextChunk
from app.ingestion.models import PageText


def sample_chunks() -> list[TextChunk]:
    """Two chunks on page 1 and one on page 2, given out of order on purpose."""
    return [
        TextChunk(page_number=2, position=0, text="Payment is due within 30 days."),
        TextChunk(page_number=1, position=1, text="Either party may terminate the contract."),
        TextChunk(page_number=1, position=0, text="This agreement starts on 1 January."),
    ]


def count_chunks(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Chunk)) or 0


def test_replace_chunks_stores_chunks_with_ids(db_session: Session) -> None:
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")

    stored = repository.replace_chunks(document, sample_chunks())

    assert len(stored) == 3
    assert all(len(chunk.id) == 36 for chunk in stored)
    assert len({chunk.id for chunk in stored}) == 3
    assert all(chunk.document_id == document.id for chunk in stored)


def test_list_chunks_returns_page_then_position_order(db_session: Session) -> None:
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    repository.replace_chunks(document, sample_chunks())

    chunks = repository.list_chunks(document.id)

    assert [(chunk.page_number, chunk.position) for chunk in chunks] == [(1, 0), (1, 1), (2, 0)]
    assert chunks[0].text == "This agreement starts on 1 January."
    assert chunks[0].created_at.tzinfo is not None


def test_replace_chunks_twice_keeps_only_the_new_chunks(db_session: Session) -> None:
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    first = repository.replace_chunks(document, sample_chunks())

    second = repository.replace_chunks(
        document, [TextChunk(page_number=1, position=0, text="New text.")]
    )

    chunks = repository.list_chunks(document.id)
    assert [chunk.text for chunk in chunks] == ["New text."]
    assert chunks[0].id == second[0].id
    assert chunks[0].id not in {chunk.id for chunk in first}
    assert count_chunks(db_session) == 1


def test_replace_chunks_does_not_touch_other_documents(db_session: Session) -> None:
    repository = DocumentRepository(db_session)
    contract = repository.create("contract.pdf", "application/pdf")
    invoice = repository.create("invoice.png", "image/png")
    repository.replace_chunks(contract, sample_chunks())
    repository.replace_chunks(invoice, [TextChunk(page_number=1, position=0, text="Total: 120 EUR")])

    repository.replace_chunks(contract, [])

    assert repository.list_chunks(contract.id) == []
    assert [chunk.text for chunk in repository.list_chunks(invoice.id)] == ["Total: 120 EUR"]


def test_get_chunks_keeps_the_requested_order_and_skips_unknown_ids(
    db_session: Session,
) -> None:
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    stored = repository.replace_chunks(document, sample_chunks())
    wanted = [stored[2].id, "unknown-id", stored[0].id]

    chunks = repository.get_chunks(wanted)

    assert [chunk.id for chunk in chunks] == [stored[2].id, stored[0].id]
    assert chunks[0].document.filename == "contract.pdf"


def test_get_chunks_with_no_ids_returns_an_empty_list(db_session: Session) -> None:
    assert DocumentRepository(db_session).get_chunks([]) == []


def test_mark_failed_removes_chunks(db_session: Session) -> None:
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    repository.mark_ready(document, [PageText(page_number=1, text="Some text.")])
    repository.replace_chunks(document, sample_chunks())

    repository.mark_failed(document, "Embedding service unavailable.")

    assert document.status == DocumentStatus.FAILED
    assert repository.list_chunks(document.id) == []
    assert repository.list_pages(document.id) == []


def test_deleting_a_document_deletes_its_chunks(db_session: Session) -> None:
    repository = DocumentRepository(db_session)
    document = repository.create("contract.pdf", "application/pdf")
    repository.replace_chunks(document, sample_chunks())

    db_session.delete(document)
    db_session.commit()

    assert count_chunks(db_session) == 0