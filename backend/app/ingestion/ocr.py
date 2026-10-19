"""Optical character recognition (OCR) with Tesseract.

Tesseract is a separate program, installed with Homebrew on macOS and with
apt in the Docker image; pytesseract only runs it and reads its output.
"""

import shutil

import pytesseract
from PIL import Image


class OCRError(Exception):
    """OCR could not be performed. The message is safe to show to the user."""


def is_tesseract_available() -> bool:
    """Return True if the tesseract program can be found on this machine."""
    return shutil.which(pytesseract.pytesseract.tesseract_cmd) is not None


def ocr_image(image: Image.Image, language: str = "eng", timeout_seconds: float = 60.0) -> str:
    """Return the text recognised in the image, with surrounding blank space removed.

    The image is converted to grayscale first: colour brings no useful
    information for printed text and triples the memory used.
    """
    grayscale = image if image.mode == "L" else image.convert("L")
    try:
        text = pytesseract.image_to_string(
            grayscale, lang=language, timeout=timeout_seconds
        )
    except pytesseract.TesseractNotFoundError as error:
        raise OCRError(
            "Tesseract is not installed or not on the PATH "
            "(macOS: brew install tesseract)."
        ) from error
    except pytesseract.TesseractError as error:
        # Raised for example when the language pack is missing.
        raise OCRError(f"Tesseract failed: {error.message.strip()}") from error
    except RuntimeError as error:
        # pytesseract raises a plain RuntimeError when the timeout is reached.
        raise OCRError(f"OCR took longer than {timeout_seconds:g} seconds.") from error
    finally:
        if grayscale is not image:
            grayscale.close()
    return text.strip()