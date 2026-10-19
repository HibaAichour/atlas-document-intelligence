"""End-to-end tests of the document routes: upload, list, detail and pages."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.ingestion.ocr import is_tesseract_available
from tests.builders import CONTRACT_TEXT, make_docx, make_pdf, make_pptx, make_scan

needs_tesseract = pytest.mark.skipif(
    not is_tesseract_available(), reason="Tesseract is not installed"
)


def upload(client: TestClient, path: Path, filename: str | None = None) -> dict:
    """Send a file to the upload route and return the JSON response."""
    with path.open("rb") as file:
        response = client.post(
            "/api/documents", files={"file": (filename or path.name, file)}
        )
    assert response.status_code == 201, response.text
    return response.json()


def test_pdf_upload_extracts_pages(client: TestClient, tmp_path: Path, data_dir: Path) -> None:
    """A text PDF is stored, read page by page and marked as ready."""
    pdf = make_pdf(tmp_path / "contract.pdf", [CONTRACT_TEXT, "Payment is due within 15 days."])

    document = upload(client, pdf)

    assert document["status"] == "ready"
    assert document["filename"] == "contract.pdf"
    assert document["mime_type"] == "application/pdf"
    assert document["page_count"] == 2
    assert document["ocr_used"] is False
    assert document["error"] is None
    assert (data_dir / "uploads" / f"{document['id']}.pdf").is_file()

    pages = client.get(f"/api/documents/{document['id']}/pages").json()
    assert [page["page_number"] for page in pages] == [1, 2]
    assert pages[0]["text"] == CONTRACT_TEXT


def test_docx_and_pptx_uploads_are_ready(client: TestClient, tmp_path: Path) -> None:
    """Office formats go through the same workflow."""
    assert upload(client, make_docx(tmp_path / "agreement.docx"))["page_count"] == 3
    assert upload(client, make_pptx(tmp_path / "review.pptx"))["page_count"] == 3


@needs_tesseract
def test_scanned_image_upload_uses_ocr(client: TestClient, tmp_path: Path) -> None:
    """An image is read with OCR and flagged as such."""
    document = upload(client, make_scan(tmp_path / "invoice.png", "INVOICE 2026-0042"))

    assert document["status"] == "ready"
    assert document["ocr_used"] is True
    pages = client.get(f"/api/documents/{document['id']}/pages").json()
    assert "2026-0042" in pages[0]["text"]


def test_unreadable_document_is_recorded_as_failed(client: TestClient, tmp_path: Path) -> None:
    """A damaged PDF is accepted, then marked as failed with the reason."""
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7 this is not really a PDF")

    document = upload(client, broken)

    assert document["status"] == "failed"
    assert "Cannot open the PDF" in document["error"]
    assert client.get(f"/api/documents/{document['id']}/pages").json() == []


def test_unsupported_file_is_refused_and_not_stored(
    client: TestClient, tmp_path: Path, data_dir: Path
) -> None:
    """A refused file leaves no document and no file behind."""
    notes = tmp_path / "notes.txt"
    notes.write_text("hello")

    with notes.open("rb") as file:
        response = client.post("/api/documents", files={"file": ("notes.txt", file)})

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
    assert client.get("/api/documents").json() == []
    assert list((data_dir / "uploads").iterdir()) == []


def test_file_over_size_limit_is_refused(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Files above MAX_UPLOAD_MB get a 413 answer."""
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-" + b"0" * (1024 * 1024))

    with big.open("rb") as file:
        response = client.post("/api/documents", files={"file": ("big.pdf", file)})

    assert response.status_code == 413
    assert "1 MB limit" in response.json()["detail"]


def test_list_and_detail_routes(client: TestClient, tmp_path: Path) -> None:
    """Uploaded documents appear in the list and can be fetched by id."""
    first = upload(client, make_pdf(tmp_path / "a.pdf", [CONTRACT_TEXT]))
    second = upload(client, make_docx(tmp_path / "b.docx"))

    listed = client.get("/api/documents").json()
    detail = client.get(f"/api/documents/{first['id']}").json()

    assert {item["id"] for item in listed} == {first["id"], second["id"]}
    assert detail == first


def test_unknown_document_gives_404(client: TestClient) -> None:
    """Unknown ids are reported as not found."""
    assert client.get("/api/documents/unknown").status_code == 404
    assert client.get("/api/documents/unknown/pages").status_code == 404