"""Read PDF files page by page, with OCR for pages that have no text layer."""

from pathlib import Path

import pypdfium2 as pdfium

from app.ingestion.models import PageText, ParseError, ParseOptions
from app.ingestion.ocr import ocr_image
from app.ingestion.text import clean_text, visible_char_count

# PDF coordinates use 72 points per inch: scale = DPI / 72.
POINTS_PER_INCH = 72


def parse_pdf(path: Path, options: ParseOptions) -> list[PageText]:
    """Return the text of every page, in order. Scanned pages go through OCR."""
    try:
        pdf = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as error:
        raise ParseError(
            f"Cannot open the PDF file ({error}). "
            "It may be damaged or protected by a password."
        ) from error

    try:
        page_count = len(pdf)
        if page_count > options.max_pages:
            raise ParseError(
                f"The PDF has {page_count} pages; the limit is {options.max_pages}."
            )
        return [_read_page(pdf, index, options) for index in range(page_count)]
    finally:
        pdf.close()


def _read_page(pdf: pdfium.PdfDocument, index: int, options: ParseOptions) -> PageText:
    page = pdf[index]
    try:
        text_page = page.get_textpage()
        try:
            native_text = clean_text(text_page.get_text_range())
        finally:
            text_page.close()

        if visible_char_count(native_text) >= options.min_text_chars:
            return PageText(page_number=index + 1, text=native_text)

        ocr_text = clean_text(_ocr_page(page, options))
        # Keep the text layer if OCR found nothing better (e.g. a nearly empty page).
        if visible_char_count(ocr_text) > visible_char_count(native_text):
            return PageText(page_number=index + 1, text=ocr_text, ocr_used=True)
        return PageText(page_number=index + 1, text=native_text)
    finally:
        page.close()


def _ocr_page(page: pdfium.PdfPage, options: ParseOptions) -> str:
    # Render one page at a time, in grayscale, to keep memory use low
    # (about 9 MB for an A4 page at 300 DPI).
    bitmap = page.render(scale=options.ocr_dpi / POINTS_PER_INCH, grayscale=True)
    try:
        image = bitmap.to_pil()
        try:
            return ocr_image(
                image,
                language=options.ocr_language,
                timeout_seconds=options.ocr_timeout_seconds,
            )
        finally:
            image.close()
    finally:
        bitmap.close()