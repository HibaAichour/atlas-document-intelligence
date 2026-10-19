"""Read and write documents and pages. Routes and services never write SQL directly."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentStatus, Page
from app.ingestion.models import PageText

MAX_ERROR_LENGTH = 1000


class DocumentRepository:
    """Every database operation on documents and their pages."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, filename: str, mime_type: str) -> Document:
        """Register a newly uploaded document with the status "uploaded"."""
        document = Document(filename=filename, mime_type=mime_type)
        self._session.add(document)
        self._session.commit()
        return document

    def get(self, document_id: str) -> Document | None:
        """Return the document, or None if the id is unknown."""
        return self._session.get(Document, document_id)

    def list_all(self) -> list[Document]:
        """Return every document, newest first."""
        statement = select(Document).order_by(Document.created_at.desc())
        return list(self._session.scalars(statement))

    def list_pages(self, document_id: str) -> list[Page]:
        """Return the pages of a document, in page order."""
        statement = (
            select(Page).where(Page.document_id == document_id).order_by(Page.page_number)
        )
        return list(self._session.scalars(statement))

    def mark_processing(self, document: Document) -> None:
        """Record that text extraction has started."""
        document.status = DocumentStatus.PROCESSING
        document.error = None
        self._session.commit()

    def mark_ready(self, document: Document, pages: Sequence[PageText]) -> None:
        """Store the extracted pages and mark the document as ready."""
        self._replace_pages(document, pages)
        document.page_count = len(pages)
        document.ocr_used = any(page.ocr_used for page in pages)
        document.status = DocumentStatus.READY
        document.error = None
        self._session.commit()

    def mark_failed(self, document: Document, error: str) -> None:
        """Record why processing failed. Any partial pages are removed."""
        self._replace_pages(document, [])
        document.page_count = 0
        document.ocr_used = False
        document.status = DocumentStatus.FAILED
        document.error = error[:MAX_ERROR_LENGTH]
        self._session.commit()

    def _replace_pages(self, document: Document, pages: Sequence[PageText]) -> None:
        # Delete the old pages first: inserting a page number that still
        # exists would break the (document_id, page_number) uniqueness rule.
        document.pages.clear()
        self._session.flush()
        document.pages.extend(
            Page(page_number=page.page_number, text=page.text, ocr_used=page.ocr_used)
            for page in pages
        )