"""Tests for the OCR module.

Tests marked "needs_tesseract" run the real Tesseract program and are
skipped automatically on a machine where it is not installed.
"""

import pytesseract
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.ingestion.ocr import OCRError, is_tesseract_available, ocr_image

needs_tesseract = pytest.mark.skipif(
    not is_tesseract_available(), reason="Tesseract is not installed"
)


def make_text_image(text: str) -> Image.Image:
    """Draw black text on a white image, like a clean scan."""
    image = Image.new("RGB", (1200, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 60), text, fill="black", font=ImageFont.load_default(size=64))
    return image


@needs_tesseract
def test_ocr_reads_printed_text() -> None:
    """Tesseract recognises clear printed text."""
    text = ocr_image(make_text_image("INVOICE 2026-0042"))

    assert "INVOICE" in text
    assert "2026-0042" in text


@needs_tesseract
def test_ocr_returns_empty_text_for_blank_image() -> None:
    """A blank page gives an empty string, not an error."""
    assert ocr_image(Image.new("RGB", (800, 600), "white")) == ""


@needs_tesseract
def test_missing_language_pack_raises_ocr_error() -> None:
    """An unknown language gives a clear OCRError."""
    with pytest.raises(OCRError, match="Tesseract failed"):
        ocr_image(make_text_image("Hello"), language="zzz")


def test_missing_tesseract_program_raises_ocr_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """If Tesseract is not installed, the error explains how to install it."""

    def fake_image_to_string(*args: object, **kwargs: object) -> str:
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", fake_image_to_string)

    with pytest.raises(OCRError, match="brew install tesseract"):
        ocr_image(Image.new("L", (10, 10), "white"))


def test_timeout_raises_ocr_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A page that takes too long is reported instead of blocking forever."""

    def fake_image_to_string(*args: object, **kwargs: object) -> str:
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(pytesseract, "image_to_string", fake_image_to_string)

    with pytest.raises(OCRError, match="longer than 5 seconds"):
        ocr_image(Image.new("L", (10, 10), "white"), timeout_seconds=5)


def test_original_image_is_left_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the grayscale copy is closed; the caller still owns its image."""
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *args, **kwargs: " text \n")
    image = Image.new("RGB", (10, 10), "white")

    assert ocr_image(image) == "text"
    assert image.getpixel((0, 0)) == (255, 255, 255)