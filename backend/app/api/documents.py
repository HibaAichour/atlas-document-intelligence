"""Routes to upload documents and read their extracted text."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_indexer
from app.api.schemas import DocumentOut, PageOut
from app.core.config import Settings, get_settings
from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.ingestion.file_types import UnsupportedFileError
from app.ingestion.service import ingest_document
from app.ingestion.storage import FileTooLargeError
from app.retrieval.indexing import DocumentIndexer

router = APIRouter(prefix="/documents", tags=["documents"])

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
Indexer = Annotated[DocumentIndexer, Depends(get_indexer)]


# Plain "def" (not "async def"): parsing, OCR and embeddings block, so FastAPI
# runs these routes in a thread pool and the server stays responsive.
@router.post("", status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile, db: DbSession, settings: AppSettings, indexer: Indexer
) -> DocumentOut:
    """Upload a file, extract its text and index it for search. A file that
    cannot be read or indexed is still recorded, with the status "failed"
    and the reason."""
    try:
        document = ingest_document(db, file.file, file.filename, settings, indexer)
    except FileTooLargeError as error:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(error)) from error
    except UnsupportedFileError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    return DocumentOut.model_validate(document)


@router.get("")
def list_documents(db: DbSession) -> list[DocumentOut]:
    """List every document, newest first."""
    return [DocumentOut.model_validate(item) for item in DocumentRepository(db).list_all()]


@router.get("/{document_id}")
def get_document(document_id: str, db: DbSession) -> DocumentOut:
    """Return one document."""
    return DocumentOut.model_validate(_get_or_404(db, document_id))


@router.get("/{document_id}/pages")
def get_document_pages(document_id: str, db: DbSession) -> list[PageOut]:
    """Return the extracted text of a document, page by page."""
    document = _get_or_404(db, document_id)
    pages = DocumentRepository(db).list_pages(document.id)
    return [PageOut.model_validate(page) for page in pages]


def _get_or_404(db: Session, document_id: str) -> Document:
    document = DocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return document