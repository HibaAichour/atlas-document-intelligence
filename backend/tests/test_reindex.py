"""Tests for the re-indexing script (fake embeddings, real Chroma, no Ollama)."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.ingestion.models import PageText
from app.retrieval.indexing import DocumentIndexer
from scripts.reindex import reindex_documents


def ready_document(repository: DocumentRepository, filename: str, text: str) -> Document:
    """Create a document in "ready" with one page, as an old upload would be."""
    document = repository.create(filename, "application/pdf")
    repository.mark_ready(document, [PageText(page_number=1, text=text)])
    return document


def test_ready_documents_are_indexed_and_others_skipped(
    db_session: Session, indexer: DocumentIndexer
) -> None:
    repository = DocumentRepository(db_session)
    contract = ready_document(repository, "contract.pdf", "Termination requires 30 days notice.")
    ready_document(repository, "invoice.pdf", "Invoice total: 1,200 EUR.")
    broken = repository.create("broken.pdf", "application/pdf")
    repository.mark_failed(broken, "Cannot read the file.")
    messages: list[str] = []

    report = reindex_documents(db_session, indexer, log=messages.append)

    assert sorted(report.indexed) == [("contract.pdf", 1), ("invoice.pdf", 1)]
    assert report.skipped == ["broken.pdf"]
    assert report.failed == []
    assert indexer.vector_store.count() == 2
    assert len(repository.list_chunks(contract.id)) == 1
    assert len(messages) == 3


def test_running_twice_gives_the_same_index_size(
    db_session: Session, indexer: DocumentIndexer
) -> None:
    repository = DocumentRepository(db_session)
    ready_document(repository, "contract.pdf", "Termination requires 30 days notice.")

    reindex_documents(db_session, indexer, log=lambda _: None)
    reindex_documents(db_session, indexer, log=lambda _: None)

    assert indexer.vector_store.count() == 1


def test_a_failure_is_reported_and_keeps_the_existing_index(
    db_session: Session, make_indexer: Callable[..., DocumentIndexer]
) -> None:
    repository = DocumentRepository(db_session)
    contract = ready_document(repository, "contract.pdf", "Termination requires 30 days notice.")
    working = make_indexer(name="shared")
    reindex_documents(db_session, working, log=lambda _: None)
    old_ids = [chunk.id for chunk in repository.list_chunks(contract.id)]

    report = reindex_documents(
        db_session, make_indexer(unavailable=True, name="shared"), log=lambda _: None
    )

    assert report.indexed == []
    assert report.failed[0][0] == "contract.pdf"
    assert "connection refused" in report.failed[0][1]
    assert [chunk.id for chunk in repository.list_chunks(contract.id)] == old_ids
    assert working.vector_store.count() == 1