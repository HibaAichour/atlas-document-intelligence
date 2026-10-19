"""Read images (PNG, JPEG) with OCR. An image is always page 1."""

from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.ingestion.models import PageText, ParseError, ParseOptions
from app.ingestion.ocr import ocr_image
from app.ingestion.text import clean_text


def parse_image(path: Path, options: ParseOptions) -> list[PageText]:
    """Return the OCR text of the image as a single page."""
    try:
        with Image.open(path) as image:
            # Phone photos are often stored sideways with a rotation tag:
            # apply it, otherwise Tesseract reads rotated text badly.
            upright = ImageOps.exif_transpose(image)
            try:
                text = ocr_image(
                    upright,
                    language=options.ocr_language,
                    timeout_seconds=options.ocr_timeout_seconds,
                )
            finally:
                if upright is not image:
                    upright.close()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as error:
        raise ParseError(f"Cannot open the image file ({error}).") from error

    return [PageText(page_number=1, text=clean_text(text), ocr_used=True)]