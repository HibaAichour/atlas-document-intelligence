"""Data types shared by the ingestion pipeline."""

from dataclasses import dataclass
from enum import StrEnum


class FileType(StrEnum):
    """The document formats ATLAS can read."""

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    IMAGE = "image"


class ParseError(Exception):
    """A file could not be read. The message is safe to show to the user."""


@dataclass(frozen=True, slots=True)
class PageText:
    """The text extracted from one page of a document.

    A "page" is a real page for PDF files, a slide for PPTX files,
    a heading-based section for DOCX files, and page 1 for images.
    """

    page_number: int  # 1-based, as shown to the user in citations
    text: str
    ocr_used: bool = False


@dataclass(frozen=True, slots=True)
class ParseOptions:
    """Settings that control text extraction."""

    ocr_language: str = "eng"
    ocr_timeout_seconds: float = 60.0
    # Resolution used to turn a scanned PDF page into an image for OCR.
    # 300 DPI is the usual value for printed text.
    ocr_dpi: int = 300
    # A PDF page with fewer visible characters than this is treated as scanned.
    min_text_chars: int = 20
    # Processing is synchronous in V1, so very long documents are refused.
    max_pages: int = 50