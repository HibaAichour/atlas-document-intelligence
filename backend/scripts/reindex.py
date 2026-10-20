"""Rebuild the search index of every ready document from the pages stored in SQLite.

Run from the backend folder, with the virtual environment active and the
backend server STOPPED (embedded Chroma must not be written by two programs
at the same time):

    python -m scripts.reindex

Use it for documents uploaded before indexing existed, or after changing the
embedding model, the embedding prefixes or the chunk size. No OCR is redone.
If the embedding service is down, the existing index is left unchanged.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.providers import build_document_indexer
from app.db.models import DocumentStatus
from app.db.repositories import DocumentRepository
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url
from app.ingestion.models import PageText
from app.retrieval.indexing import DocumentIndexer, IndexingError
from app.retrieval.vector_store import VectorStoreError


@dataclass
class ReindexReport:
    """What happened to each document."""

    indexed: list[tuple[str, int]] = field(default_factory=list)  # (filename, chunks)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (filename, reason)
    skipped: list[str] = field(default_factory=list)  # filenames not in "ready"


def reindex_documents(
    session: Session, indexer: DocumentIndexer, log: Callable[[str], None] = print
) -> ReindexReport:
    """Index every ready document again. A failure does not stop the others."""
    repository = DocumentRepository(session)
    report = ReindexReport()
    for document in repository.list_all():
        if document.status != DocumentStatus.READY:
            report.skipped.append(document.filename)
            log(f"[SKIP] {document.filename} (status: {document.status.value})")
            continue

        pages = [
            PageText(page_number=page.page_number, text=page.text, ocr_used=page.ocr_used)
            for page in repository.list_pages(document.id)
        ]
        try:
            count = indexer.index(repository, document, pages)
        except IndexingError as error:
            session.rollback()
            report.failed.append((document.filename, str(error)))
            log(f"[FAIL] {document.filename}: {error}")
        else:
            report.indexed.append((document.filename, count))
            log(f"[OK]   {document.filename}: {count} chunks")
    return report


def main() -> int:
    """Re-index every ready document and return a process exit code (0 means success)."""
    settings = Settings()
    print(
        f"Embeddings: {settings.embedding_provider} | {settings.embedding_model} "
        f"| {settings.embedding_base_url}"
    )
    print(f"Data:       {settings.data_dir.resolve()}\n")

    try:
        indexer = build_document_indexer(settings)
    except VectorStoreError as error:
        print(f"[FAIL] {error}")
        return 1

    engine = create_db_engine(sqlite_url(settings.data_dir))
    init_db(engine)
    try:
        with create_session_factory(engine)() as session:
            report = reindex_documents(session, indexer)
    finally:
        engine.dispose()

    print(
        f"\nIndexed: {len(report.indexed)} | Failed: {len(report.failed)} "
        f"| Skipped: {len(report.skipped)}"
    )
    print(f"Vectors in the index: {indexer.vector_store.count()}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())