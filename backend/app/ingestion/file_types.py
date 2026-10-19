"""Recognise the format of an uploaded file from its name and its content.

The extension alone is not trusted: the first bytes must match it, so that
a renamed file (for example a PDF called "report.docx") is refused.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.models import FileType

PDF_SIGNATURE = b"%PDF-"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
ZIP_SIGNATURE = b"PK\x03\x04"


class UnsupportedFileError(Exception):
    """The file is not one of the accepted formats. Safe to show to the user."""


@dataclass(frozen=True, slots=True)
class DetectedType:
    """What ATLAS knows about a file once its format is confirmed."""

    file_type: FileType
    mime_type: str
    extension: str  # used to name the stored file, e.g. ".pdf"


SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg")


def detect_file_type(path: Path, filename: str) -> DetectedType:
    """Return the confirmed type of the file at path, uploaded as filename."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"Unsupported file type '{extension or 'none'}'. "
            f"Accepted: {', '.join(SUPPORTED_EXTENSIONS)}."
        )

    with path.open("rb") as file:
        header = file.read(8)

    if extension == ".pdf" and header.startswith(PDF_SIGNATURE):
        return DetectedType(FileType.PDF, "application/pdf", ".pdf")
    if extension == ".png" and header.startswith(PNG_SIGNATURE):
        return DetectedType(FileType.IMAGE, "image/png", ".png")
    if extension in (".jpg", ".jpeg") and header.startswith(JPEG_SIGNATURE):
        return DetectedType(FileType.IMAGE, "image/jpeg", ".jpg")
    if extension == ".docx" and _zip_contains(path, header, "word/document.xml"):
        return DetectedType(
            FileType.DOCX,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        )
    if extension == ".pptx" and _zip_contains(path, header, "ppt/presentation.xml"):
        return DetectedType(
            FileType.PPTX,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".pptx",
        )
    raise UnsupportedFileError(
        f"The content of the file does not match its '{extension}' extension."
    )


def _zip_contains(path: Path, header: bytes, member: str) -> bool:
    """DOCX and PPTX files are ZIP archives: check the part that identifies them."""
    if not header.startswith(ZIP_SIGNATURE):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            return member in archive.namelist()
    except zipfile.BadZipFile:
        return False