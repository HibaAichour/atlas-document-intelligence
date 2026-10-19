"""Tests for file type detection and upload storage helpers."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.ingestion.file_types import UnsupportedFileError, detect_file_type
from app.ingestion.models import FileType
from app.ingestion.storage import (
    FileTooLargeError,
    safe_display_name,
    save_to_temporary_file,
)
from tests.builders import CONTRACT_TEXT, make_docx, make_pdf, make_pptx, make_scan


def test_each_supported_format_is_recognised(tmp_path: Path) -> None:
    """PDF, DOCX, PPTX, PNG and JPEG are recognised from their content."""
    scan = make_scan(tmp_path / "scan.png", "Invoice")
    jpeg = tmp_path / "photo.jpg"
    with Image.open(scan) as image:
        image.save(jpeg, "JPEG")

    cases = [
        (make_pdf(tmp_path / "a.pdf", [CONTRACT_TEXT]), "a.pdf", FileType.PDF, "application/pdf"),
        (make_docx(tmp_path / "a.docx"), "a.docx", FileType.DOCX, None),
        (make_pptx(tmp_path / "a.pptx"), "a.pptx", FileType.PPTX, None),
        (scan, "scan.PNG", FileType.IMAGE, "image/png"),
        (jpeg, "photo.jpeg", FileType.IMAGE, "image/jpeg"),
    ]
    for path, filename, file_type, mime_type in cases:
        detected = detect_file_type(path, filename)
        assert detected.file_type == file_type
        if mime_type is not None:
            assert detected.mime_type == mime_type


def test_unsupported_extension_is_refused(tmp_path: Path) -> None:
    """Formats outside the V1 scope are refused with the accepted list."""
    path = tmp_path / "notes.txt"
    path.write_text("hello")

    with pytest.raises(UnsupportedFileError, match="Accepted: .pdf"):
        detect_file_type(path, "notes.txt")


def test_renamed_file_is_refused(tmp_path: Path) -> None:
    """A PDF renamed to .docx does not pass: content must match the extension."""
    pdf = make_pdf(tmp_path / "real.pdf", [CONTRACT_TEXT])

    with pytest.raises(UnsupportedFileError, match="does not match"):
        detect_file_type(pdf, "fake.docx")


def test_docx_renamed_to_pptx_is_refused(tmp_path: Path) -> None:
    """Both formats are ZIP archives; their inner structure tells them apart."""
    document = make_docx(tmp_path / "real.docx")

    with pytest.raises(UnsupportedFileError, match="does not match"):
        detect_file_type(document, "fake.pptx")


def test_upload_within_limit_is_saved(tmp_path: Path) -> None:
    """The copy has exactly the uploaded bytes."""
    saved = save_to_temporary_file(io.BytesIO(b"x" * 3000), tmp_path, max_bytes=5000)

    assert saved.read_bytes() == b"x" * 3000


def test_upload_over_limit_is_refused_and_removed(tmp_path: Path) -> None:
    """No partial file is left behind when the limit is exceeded."""
    with pytest.raises(FileTooLargeError):
        save_to_temporary_file(io.BytesIO(b"x" * 3000), tmp_path, max_bytes=1000)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("contract.pdf", "contract.pdf"),
        ("C:\\fakepath\\contract.pdf", "contract.pdf"),
        ("../../etc/passwd", "passwd"),
        ("", "unnamed"),
        (None, "unnamed"),
    ],
)
def test_display_name_never_contains_a_path(raw: str | None, expected: str) -> None:
    """Only the file name is kept, whatever the browser sends."""
    assert safe_display_name(raw) == expected