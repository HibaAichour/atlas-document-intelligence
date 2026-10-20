"""Ingestion workflow: check, store, extract, index and record an uploaded document."""

import logging
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.ingestion.file_types import detect_file_type
from app.ingestion.models import ParseError, ParseOptions
from app.ingestion.ocr import OCRError
from app.ingestion.parsing import parse_document
from app.ingestion.storage import (
    move_into_place,
    safe_display_name,
    save_to_temporary_file,
    uploads_dir,
)
from app.retrieval.indexing import DocumentIndexer, IndexingError
from app.retrieval.vector_store import VectorStoreError

logger = logging.getLogger(__name__)


def parse_options_from_settings(settings: Settings) -> ParseOptions:
    """Build the extraction options from the application settings."""
    return ParseOptions(
        ocr_language=settings.ocr_language,
        ocr_timeout_seconds=settings.ocr_timeout_seconds,
        max_pages=settings.max_pages,
        max_ocr_pages=settings.max_ocr_pages,
    )


def ingest_document(
    session: Session,
    source: BinaryIO,
    filename: str | None,
    settings: Settings,
    indexer: DocumentIndexer,
) -> Document:
    """Store an uploaded file, extract its text page by page and index it.

    Raises FileTooLargeError or UnsupportedFileError when the file is refused;
    nothing is stored in that case. Once the file is accepted, the document is
    always returned, with the status "ready" or "failed" (and the reason).
    The status stays "processing" until the document is searchable.
    """
    folder = uploads_dir(settings.data_dir)
    display_name = safe_display_name(filename)
    temporary = save_to_temporary_file(source, folder, settings.max_upload_mb * 1024 * 1024)
    try:
        detected = detect_file_type(temporary, display_name)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    repository = DocumentRepository(session)
    document = repository.create(display_name, detected.mime_type)
    stored_path = move_into_place(temporary, folder, document.id, detected.extension)

    repository.mark_processing(document)
    try:
        pages = parse_document(
            stored_path, detected.file_type, parse_options_from_settings(settings)
        )
        indexer.index(repository, document, pages)
    except (ParseError, OCRError, IndexingError) as error:
        _mark_failed(session, repository, indexer, document, str(error))
    except Exception:
        # A bug must not leave the document stuck in "processing".
        logger.exception("Unexpected error while processing document %s", document.id)
        _mark_failed(
            session, repository, indexer, document, "Unexpected error while reading the document."
        )
    else:
        repository.mark_ready(document, pages)
    return document


def _mark_failed(
    session: Session,
    repository: DocumentRepository,
    indexer: DocumentIndexer,
    document: Document,
    error: str,
) -> None:
    """Remove everything stored for the document, then record why it failed."""
    # Drop any database change left half-done by the error.
    session.rollback()
    try:
        indexer.remove(document.id)
    except VectorStoreError:
        # The failure is still recorded; leftover vectors are harmless because
        # search results are always matched against chunks in SQLite.
        logger.exception("Could not remove the vectors of document %s", document.id)
    repository.mark_failed(document, error)