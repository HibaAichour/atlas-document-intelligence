"""Single entry point of text extraction: pick the parser for the file type."""

from collections.abc import Callable
from pathlib import Path

from app.ingestion.docx_parser import parse_docx
from app.ingestion.image_parser import parse_image
from app.ingestion.models import FileType, PageText, ParseError, ParseOptions
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.pptx_parser import parse_pptx

Parser = Callable[[Path, ParseOptions], list[PageText]]

PARSERS: dict[FileType, Parser] = {
    FileType.PDF: parse_pdf,
    FileType.DOCX: parse_docx,
    FileType.PPTX: parse_pptx,
    FileType.IMAGE: parse_image,
}


def parse_document(path: Path, file_type: FileType, options: ParseOptions) -> list[PageText]:
    """Extract the text of a document, page by page.

    Raises ParseError if the file cannot be read or contains no text at all,
    and OCRError if OCR was needed but failed.
    """
    pages = PARSERS[file_type](path, options)
    if not any(page.text for page in pages):
        raise ParseError("No text could be extracted from this document.")
    return pages