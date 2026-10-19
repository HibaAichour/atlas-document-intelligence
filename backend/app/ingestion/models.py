"""Data types shared by the ingestion pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageText:
    """The text extracted from one page of a document.

    A "page" is a real page for PDF files, a slide for PPTX files,
    a heading-based section for DOCX files, and page 1 for images.
    """

    page_number: int  # 1-based, as shown to the user in citations
    text: str
    ocr_used: bool = False