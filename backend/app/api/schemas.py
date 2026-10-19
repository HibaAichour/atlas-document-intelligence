"""Shapes of the JSON returned by the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import DocumentStatus


class DocumentOut(BaseModel):
    """A document as shown in the document list."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    mime_type: str
    page_count: int
    ocr_used: bool
    status: DocumentStatus
    error: str | None
    created_at: datetime


class PageOut(BaseModel):
    """The extracted text of one page."""

    model_config = ConfigDict(from_attributes=True)

    page_number: int
    text: str
    ocr_used: bool